"""Marketplace tool runner endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tool_runner import (
    TenantToolUpsertRequest,
    ToolRegistryItem,
    ToolRunDetailResponse,
    ToolRunListItem,
    ToolRunRequest,
    ToolRunResponse,
)
from app.services.artifact_service import ArtifactService
from app.services.tool_runner_service import PlanLimitExceededError, ToolRunnerService


router = APIRouter(prefix="/tools", tags=["Tool Runner"])


@router.get("", response_model=list[ToolRegistryItem])
async def list_tool_registry(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> list[ToolRegistryItem]:
    return ToolRunnerService(db).list_tools_for_tenant(current_tenant.id)


@router.get("/registry", response_model=list[ToolRegistryItem], include_in_schema=False)
async def list_tool_registry_legacy(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> list[ToolRegistryItem]:
    return ToolRunnerService(db).list_tools_for_tenant(current_tenant.id)


@router.put("/{tool_slug}/settings", response_model=ToolRegistryItem)
async def upsert_tool_settings(
    tool_slug: str,
    payload: TenantToolUpsertRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"])),
) -> ToolRegistryItem:
    service = ToolRunnerService(db)
    try:
        service.upsert_tenant_tool(
            tenant_id=current_tenant.id,
            tool_slug=tool_slug,
            enabled=payload.enabled,
            rate_limit_per_minute=payload.rate_limit_per_minute,
            config=payload.config,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
        items = service.list_tools_for_tenant(current_tenant.id)
        for item in items:
            if item.slug == tool_slug or item.key == tool_slug:
                return item
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/run", response_model=ToolRunResponse)
async def run_tool(
    payload: ToolRunRequest,
    request: Request,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> ToolRunResponse:
    service = ToolRunnerService(db)
    try:
        return await service.run_tool(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            payload=payload,
            correlation_id=x_correlation_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PlanLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": exc.code,
                "message": str(exc),
                "used": exc.used,
                "limit": exc.limit,
            },
        )
    except ValueError as exc:
        message = str(exc)
        if message == "Tool not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        if message == "Tool rate limit exceeded":
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


@router.get("/runs", response_model=list[ToolRunListItem])
async def list_tool_runs(
    limit: int = 20,
    offset: int = 0,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> list[ToolRunListItem]:
    bounded_limit = max(1, min(limit, 200))
    bounded_offset = max(0, offset)
    return ToolRunnerService(db).list_runs_for_tenant(current_tenant.id, limit=bounded_limit, offset=bounded_offset)


@router.get("/runs/{request_id}", response_model=ToolRunDetailResponse)
async def get_tool_run_detail(
    request_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> ToolRunDetailResponse:
    detail = ToolRunnerService(db).get_run_for_tenant(current_tenant.id, request_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool run not found")
    return detail


@router.get("/artifacts/{artifact_id}/download", include_in_schema=False)
async def download_artifact(
    artifact_id: uuid.UUID,
    expires: int,
    sig: str,
    db: Session = Depends(get_db),
) -> Response:
    service = ArtifactService(db)
    return service.build_download_response(artifact_id=artifact_id, expires=expires, sig=sig)
