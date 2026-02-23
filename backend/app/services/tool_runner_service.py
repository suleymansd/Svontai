"""Tool runner service for Marketplace tools."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.plans import (
    PLAN_DEFAULT_TOOL_RATE_LIMITS,
    normalize_plan_code,
    plan_meets_requirement,
)
from app.core.n8n_security import generate_svontai_to_n8n_headers
from app.models.artifact import Artifact
from app.models.tenant_tool import TenantTool
from app.models.tool import Tool
from app.models.tool_run import ToolRun
from app.schemas.tool_runner import (
    ToolRegistryItem,
    ToolRunArtifact,
    ToolRunDetailResponse,
    ToolRunError,
    ToolRunListItem,
    ToolRunRequest,
    ToolRunResponse,
    ToolRunUsage,
)
from app.services.artifact_service import ArtifactService
from app.services.audit_log_service import AuditLogService
from app.services.billing_service import BillingService
from app.services.subscription_service import SubscriptionService
from app.services.usage_counter_service import UsageCounterService

logger = logging.getLogger(__name__)


class PlanLimitExceededError(Exception):
    def __init__(self, message: str, *, used: int, limit: int):
        super().__init__(message)
        self.code = "PLAN_LIMIT_EXCEEDED"
        self.used = used
        self.limit = limit


class ToolRunnerService:
    def __init__(self, db: Session):
        self.db = db
        self.artifact_service = ArtifactService(db)
        self.billing_service = BillingService(db)
        self._subscription_service = SubscriptionService(db)
        self._plan_cache: dict[uuid.UUID, tuple[str, dict]] = {}

    def _build_request_id(self, request_id: str | None) -> str:
        value = (request_id or "").strip()
        return value or str(uuid.uuid4())

    def _find_tool(self, tool_slug: str) -> Tool | None:
        slug = (tool_slug or "").strip()
        if not slug:
            return None

        tool = self.db.query(Tool).filter(Tool.slug == slug).first()
        if tool:
            return tool

        return self.db.query(Tool).filter(Tool.key == slug).first()

    def _get_tenant_plan_context(self, tenant_id: uuid.UUID) -> tuple[str, dict]:
        cached = self._plan_cache.get(tenant_id)
        if cached is not None:
            return cached

        subscription = self._subscription_service.get_subscription(tenant_id)
        if subscription is None:
            subscription = self._subscription_service.create_subscription(tenant_id, "free")

        plan_type = normalize_plan_code(subscription.plan.plan_type)
        features = dict(subscription.plan.feature_flags or {})
        result = (plan_type, features)
        self._plan_cache[tenant_id] = result
        return result

    def _default_plan_rate_limit(self, tenant_id: uuid.UUID) -> int:
        plan_type, _ = self._get_tenant_plan_context(tenant_id)
        return PLAN_DEFAULT_TOOL_RATE_LIMITS.get(plan_type, PLAN_DEFAULT_TOOL_RATE_LIMITS["free"])

    @staticmethod
    def _resolve_tool_required_plan(tool: Tool) -> str:
        raw_required = normalize_plan_code(tool.required_plan)
        if raw_required != "free":
            return raw_required
        if tool.is_premium:
            return "premium"
        return "free"

    def _resolve_tenant_tool_access(self, tenant_id: uuid.UUID, tool: Tool) -> tuple[bool, int | None, str]:
        tool_slug = tool.slug or tool.key
        plan_type, _ = self._get_tenant_plan_context(tenant_id)
        default_rate_limit = self._default_plan_rate_limit(tenant_id)
        required_plan = self._resolve_tool_required_plan(tool)
        access_by_plan = plan_meets_requirement(plan_type, required_plan)

        tenant_tool = self.db.query(TenantTool).filter(
            TenantTool.tenant_id == tenant_id,
            TenantTool.tool_slug == tool_slug,
        ).first()

        if tenant_tool is not None:
            return (
                bool(tenant_tool.enabled and access_by_plan),
                tenant_tool.rate_limit_per_minute if tenant_tool.rate_limit_per_minute is not None else default_rate_limit,
                required_plan,
            )

        return bool(
            tool.is_public and tool.status == "active" and not tool.coming_soon and access_by_plan
        ), default_rate_limit, required_plan

    def list_tools_for_tenant(self, tenant_id: uuid.UUID) -> list[ToolRegistryItem]:
        tenant_settings = self.db.query(TenantTool).filter(TenantTool.tenant_id == tenant_id).all()
        by_slug = {row.tool_slug: row for row in tenant_settings}

        tools = self.db.query(Tool).order_by(Tool.created_at.desc()).all()
        items: list[ToolRegistryItem] = []
        for tool in tools:
            slug = tool.slug or tool.key
            tenant_tool = by_slug.get(slug)
            enabled, rate_limit, required_plan = self._resolve_tenant_tool_access(tenant_id, tool)
            if tenant_tool is not None and tenant_tool.rate_limit_per_minute is not None:
                rate_limit = tenant_tool.rate_limit_per_minute

            items.append(
                ToolRegistryItem(
                    slug=slug,
                    key=tool.key,
                    name=tool.name,
                    description=tool.description,
                    category=tool.category,
                    status=tool.status,
                    isPublic=tool.is_public,
                    isPremium=tool.is_premium,
                    enabled=enabled,
                    requiredPlan=required_plan,
                    requiredIntegrations=list(tool.required_integrations_json or []),
                    n8nWorkflowId=tool.n8n_workflow_id,
                    rateLimitPerMinute=rate_limit,
                )
            )
        return items

    def upsert_tenant_tool(
        self,
        *,
        tenant_id: uuid.UUID,
        tool_slug: str,
        enabled: bool,
        rate_limit_per_minute: int | None,
        config: dict | None,
        user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TenantTool:
        tool = self._find_tool(tool_slug)
        if tool is None:
            raise ValueError("Tool not found")

        resolved_slug = tool.slug or tool.key
        record = self.db.query(TenantTool).filter(
            TenantTool.tenant_id == tenant_id,
            TenantTool.tool_slug == resolved_slug,
        ).first()
        if record is None:
            record = TenantTool(
                tenant_id=tenant_id,
                tool_slug=resolved_slug,
            )
            self.db.add(record)

        record.enabled = enabled
        record.rate_limit_per_minute = rate_limit_per_minute
        record.config_json = dict(config or {})
        self.db.commit()
        self.db.refresh(record)

        AuditLogService(self.db).safe_log(
            action="tool.tenant.upsert",
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None,
            resource_type="tool",
            resource_id=resolved_slug,
            payload={
                "enabled": enabled,
                "rate_limit_per_minute": rate_limit_per_minute,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return record

    def _check_rate_limit(self, tenant_id: uuid.UUID, tool_slug: str, per_minute_limit: int | None) -> None:
        if not per_minute_limit or per_minute_limit <= 0:
            return

        window_start = datetime.utcnow() - timedelta(minutes=1)
        current_count = self.db.query(ToolRun).filter(
            ToolRun.tenant_id == tenant_id,
            ToolRun.tool_slug == tool_slug,
            ToolRun.created_at >= window_start,
        ).count()
        if current_count >= per_minute_limit:
            raise ValueError("Tool rate limit exceeded")

    @staticmethod
    def _runner_timeout_seconds() -> int:
        if settings.N8N_TOOL_RUNNER_TIMEOUT_SECONDS and settings.N8N_TOOL_RUNNER_TIMEOUT_SECONDS > 0:
            return settings.N8N_TOOL_RUNNER_TIMEOUT_SECONDS
        return settings.N8N_TIMEOUT_SECONDS

    @staticmethod
    def _runner_retry_count() -> int:
        if settings.N8N_TOOL_RUNNER_RETRIES is not None and settings.N8N_TOOL_RUNNER_RETRIES >= 0:
            return settings.N8N_TOOL_RUNNER_RETRIES
        return settings.N8N_RETRY_COUNT

    @staticmethod
    def _is_retryable_http_status(status_code: int) -> bool:
        return 500 <= status_code < 600

    async def _call_n8n_runner(
        self,
        runner_workflow_id: str,
        payload: dict,
        tenant_id: uuid.UUID,
        request_id: str,
    ) -> dict:
        endpoint = settings.N8N_INTERNAL_RUN_ENDPOINT_TEMPLATE.format(workflow_id=runner_workflow_id)
        run_url = f"{settings.N8N_BASE_URL.rstrip('/')}{endpoint}"
        headers = generate_svontai_to_n8n_headers(payload, str(tenant_id))
        headers["Content-Type"] = "application/json"
        if settings.N8N_API_KEY:
            headers["X-N8N-API-KEY"] = settings.N8N_API_KEY
            headers["Authorization"] = f"Bearer {settings.N8N_API_KEY}"

        retry_count = max(0, self._runner_retry_count())
        timeout_seconds = self._runner_timeout_seconds()
        backoff_base = max(0.1, float(settings.N8N_TOOL_RUNNER_BACKOFF_SECONDS or 0.5))

        logger.info(
            "Tool runner n8n request request_id=%s url=%s tenant_id=%s retry_count=%s timeout=%ss",
            request_id,
            run_url,
            tenant_id,
            retry_count,
            timeout_seconds,
        )
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            for attempt in range(retry_count + 1):
                try:
                    response = await client.post(run_url, json=payload, headers=headers)
                    response.raise_for_status()
                    return response.json() if response.content else {}
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    if attempt >= retry_count:
                        raise RuntimeError(f"n8n runner transport error: {exc}") from exc
                    sleep_seconds = backoff_base * (2 ** attempt)
                    logger.warning(
                        "Tool runner retrying transport error request_id=%s attempt=%s sleep=%.2fs error=%s",
                        request_id,
                        attempt + 1,
                        sleep_seconds,
                        exc,
                    )
                    await asyncio.sleep(sleep_seconds)
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    if self._is_retryable_http_status(status_code) and attempt < retry_count:
                        sleep_seconds = backoff_base * (2 ** attempt)
                        logger.warning(
                            "Tool runner retrying http error request_id=%s status=%s attempt=%s sleep=%.2fs",
                            request_id,
                            status_code,
                            attempt + 1,
                            sleep_seconds,
                        )
                        await asyncio.sleep(sleep_seconds)
                        continue
                    body_preview = (exc.response.text or "")[:300]
                    raise RuntimeError(f"n8n runner http error {status_code}: {body_preview}") from exc

    @staticmethod
    def _normalize_response(request_id: str, raw: dict | None) -> ToolRunResponse:
        payload = raw or {}
        success = bool(payload.get("success", True))
        data = payload.get("data", payload if isinstance(payload, dict) else {"result": payload})
        error_payload = payload.get("error")
        error_obj = None
        if error_payload:
            error_obj = ToolRunError(
                message=str(error_payload.get("message", "Tool run failed")),
                code=error_payload.get("code"),
                node=error_payload.get("node"),
            )

        usage_payload = payload.get("usage") or {}
        usage = ToolRunUsage(
            timeMs=int(usage_payload.get("time_ms") or usage_payload.get("timeMs") or 0),
            tokens=usage_payload.get("tokens"),
            cost=usage_payload.get("cost"),
        )

        artifacts = payload.get("artifacts") or []
        if not isinstance(artifacts, list):
            artifacts = []

        normalized_artifacts: list[ToolRunArtifact] = []
        for artifact in artifacts:
            if isinstance(artifact, dict):
                normalized_artifacts.append(ToolRunArtifact(**artifact))

        return ToolRunResponse(
            requestId=request_id,
            success=success,
            data=data if isinstance(data, dict) else {"result": data},
            error=error_obj,
            usage=usage,
            artifacts=normalized_artifacts,
        )

    def _response_from_run(self, run: ToolRun, *, refresh_signed_urls: bool = False) -> ToolRunResponse:
        artifacts: list[ToolRunArtifact] = []
        if run.artifacts_json and not refresh_signed_urls:
            artifacts = [ToolRunArtifact(**item) for item in (run.artifacts_json or []) if isinstance(item, dict)]
        else:
            persisted_artifacts = self.artifact_service.get_artifacts_for_request(run.tenant_id, run.request_id)
            if persisted_artifacts:
                artifacts = [self.artifact_service.to_response_artifact(item) for item in persisted_artifacts]
            else:
                artifacts = [ToolRunArtifact(**item) for item in (run.artifacts_json or []) if isinstance(item, dict)]

        return ToolRunResponse(
            requestId=run.request_id,
            success=run.status == "success",
            data=dict(run.output_json or {}),
            error=ToolRunError(**run.error_json) if run.error_json else None,
            usage=ToolRunUsage(**(run.usage_json or {})),
            artifacts=artifacts,
        )

    def list_runs_for_tenant(self, tenant_id: uuid.UUID, limit: int = 20, offset: int = 0) -> list[ToolRunListItem]:
        rows = self.db.query(ToolRun).filter(
            ToolRun.tenant_id == tenant_id
        ).order_by(ToolRun.created_at.desc()).offset(offset).limit(limit).all()

        items: list[ToolRunListItem] = []
        for row in rows:
            artifact_count = self.db.query(Artifact).filter(
                Artifact.tenant_id == tenant_id,
                Artifact.request_id == row.request_id,
            ).count()
            if artifact_count == 0:
                artifact_count = len(row.artifacts_json or [])
            items.append(
                ToolRunListItem(
                    requestId=row.request_id,
                    toolSlug=row.tool_slug,
                    status=row.status,
                    success=row.status == "success",
                    n8nExecutionId=row.n8n_execution_id,
                    createdAt=row.created_at,
                    finishedAt=row.finished_at,
                    artifactsCount=artifact_count,
                )
            )
        return items

    def get_run_for_tenant(self, tenant_id: uuid.UUID, request_id: str) -> ToolRunDetailResponse | None:
        run = self.db.query(ToolRun).filter(
            ToolRun.tenant_id == tenant_id,
            ToolRun.request_id == request_id,
        ).first()
        if not run:
            return None
        response = self._response_from_run(run, refresh_signed_urls=True)
        return ToolRunDetailResponse(
            requestId=response.request_id,
            success=response.success,
            data=response.data,
            error=response.error,
            usage=response.usage,
            artifacts=response.artifacts,
            toolSlug=run.tool_slug,
            status=run.status,
            correlationId=run.correlation_id,
            n8nExecutionId=run.n8n_execution_id,
            createdAt=run.created_at,
            startedAt=run.started_at,
            finishedAt=run.finished_at,
        )

    async def run_tool(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ToolRunRequest,
        correlation_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ToolRunResponse:
        request_id = self._build_request_id(payload.request_id)
        tool = self._find_tool(payload.tool_slug)
        if tool is None:
            raise ValueError("Tool not found")

        tool_slug = tool.slug or tool.key
        tenant_plan_type, _ = self._get_tenant_plan_context(tenant_id)
        required_plan = self._resolve_tool_required_plan(tool)
        if not plan_meets_requirement(tenant_plan_type, required_plan):
            if required_plan == "enterprise":
                raise PermissionError("Enterprise plan required for this tool")
            if required_plan == "premium":
                raise PermissionError("Premium plan required for this tool")
            if required_plan == "pro":
                raise PermissionError("Pro plan required for this tool")
            raise PermissionError("Current plan does not allow this tool")

        runner_workflow_id = (tool.n8n_workflow_id or settings.N8N_TOOL_RUNNER_WORKFLOW_ID or "").strip()
        if not runner_workflow_id:
            raise RuntimeError("Runner workflow id is not configured")
        allowed, rate_limit_per_minute, _ = self._resolve_tenant_tool_access(tenant_id, tool)
        if not allowed:
            raise PermissionError("Tool is disabled for tenant")

        existing = self.db.query(ToolRun).filter(
            ToolRun.tenant_id == tenant_id,
            ToolRun.request_id == request_id,
        ).first()
        if existing:
            return self._response_from_run(existing)

        within_monthly_limit, used_runs, monthly_limit = self.billing_service.check_monthly_limit(tenant_id)
        if not within_monthly_limit:
            raise PlanLimitExceededError(
                f"Aylık tool çalıştırma limitiniz doldu ({used_runs}/{monthly_limit}). Planınızı yükseltin.",
                used=used_runs,
                limit=monthly_limit,
            )

        self._check_rate_limit(tenant_id, tool_slug, rate_limit_per_minute)

        run = ToolRun(
            request_id=request_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            tool_slug=tool_slug,
            status="running",
            tool_input_json=dict(payload.tool_input or {}),
            context_json=payload.context.model_dump(),
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        started_at = datetime.utcnow()
        try:
            if not settings.USE_N8N:
                raise RuntimeError("n8n is disabled")

            n8n_payload = {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "request_id": request_id,
                "tool_slug": tool_slug,
                "tool_input": payload.tool_input,
                "context": payload.context.model_dump(),
            }
            raw_response = await self._call_n8n_runner(
                runner_workflow_id,
                n8n_payload,
                tenant_id,
                request_id,
            )
            normalized = self._normalize_response(request_id, raw_response if isinstance(raw_response, dict) else {})
            persisted_artifacts: list[ToolRunArtifact] = []
            if normalized.artifacts:
                try:
                    persisted_artifacts = self.artifact_service.persist_tool_artifacts(
                        tenant_id=tenant_id,
                        request_id=request_id,
                        tool_slug=tool_slug,
                        artifacts=normalized.artifacts,
                    )
                except Exception as artifact_exc:
                    logger.warning(
                        "Artifact persistence skipped request_id=%s tool_slug=%s reason=%s",
                        request_id,
                        tool_slug,
                        artifact_exc,
                    )
            if "executionId" in (raw_response or {}):
                run.n8n_execution_id = str(raw_response["executionId"])
            logger.info(
                "Tool runner completed request_id=%s tenant_id=%s tool_slug=%s n8n_execution_id=%s success=%s",
                request_id,
                tenant_id,
                tool_slug,
                run.n8n_execution_id,
                normalized.success,
            )
            run.status = "success" if normalized.success else "failed"
            run.output_json = normalized.data
            run.error_json = normalized.error.model_dump() if normalized.error else None
            run.usage_json = normalized.usage.model_dump(by_alias=True)
            run.artifacts_json = [a.model_dump(by_alias=True) for a in (persisted_artifacts or normalized.artifacts)]
            run.finished_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(run)
            return ToolRunResponse(
                requestId=normalized.request_id,
                success=normalized.success,
                data=normalized.data,
                error=normalized.error,
                usage=normalized.usage,
                artifacts=persisted_artifacts or normalized.artifacts,
            )
        except Exception as exc:
            elapsed_ms = max(0, int((datetime.utcnow() - started_at).total_seconds() * 1000))
            error_obj = ToolRunError(message=str(exc), code="TOOL_RUN_FAILED")
            response = ToolRunResponse(
                requestId=request_id,
                success=False,
                data={},
                error=error_obj,
                usage=ToolRunUsage(timeMs=elapsed_ms),
                artifacts=[],
            )
            run.status = "failed"
            run.error_json = error_obj.model_dump()
            run.usage_json = response.usage.model_dump(by_alias=True)
            run.finished_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(run)
            return response
        finally:
            UsageCounterService(self.db).increment(
                tenant_id=tenant_id,
                tool_calls=1,
                extra={"last_tool": tool_slug},
            )
            AuditLogService(self.db).safe_log(
                action="tool.run",
                tenant_id=str(tenant_id),
                user_id=str(user_id),
                resource_type="tool",
                resource_id=tool_slug,
                payload={"request_id": request_id, "correlation_id": correlation_id},
                ip_address=ip_address,
                user_agent=user_agent,
            )
