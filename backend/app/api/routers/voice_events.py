"""
Voice Gateway event ingest router.

Voice Gateway (realtime service) posts normalized call events here.
SvontAI validates signature, applies tenant scoping, writes audit/usage,
then forwards to n8n router workflow.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.voice_security import verify_voice_gateway_request_dependency
from app.db.session import get_db
from app.models.call import Call, CallDirection, CallStatus
from app.models.tenant import Tenant
from app.services.audit_log_service import AuditLogService
from app.services.n8n_client import N8NClient
from app.services.usage_counter_service import UsageCounterService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["Voice (Gateway)"])


class VoiceEvent(BaseModel):
    tenant_id: UUID = Field(..., alias="tenantId")
    event_type: str = Field(..., alias="eventType", min_length=3, max_length=80)
    event_id: str = Field(..., alias="eventId", min_length=8, max_length=255)

    from_id: str = Field(..., alias="from", min_length=3, max_length=255)
    to_id: str | None = Field(default=None, alias="to", max_length=255)

    text: str | None = Field(default=None, max_length=4000)
    timestamp: str | None = None
    correlation_id: str | None = Field(default=None, alias="correlationId", max_length=100)

    call: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    class Config:
        populate_by_name = True


class VoiceIngestResponse(BaseModel):
    accepted: bool
    run_id: str | None = Field(default=None, alias="runId")
    message: str | None = None

    class Config:
        populate_by_name = True


@router.post("/events", response_model=VoiceIngestResponse)
async def ingest_voice_event(
    request: Request,
    body: VoiceEvent,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_voice_gateway_request_dependency),
) -> VoiceIngestResponse:
    tenant = db.query(Tenant).filter(Tenant.id == body.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    call_payload = body.call or {}
    provider = str(call_payload.get("provider") or "unknown").strip()[:50]
    provider_call_id = str(call_payload.get("provider_call_id") or call_payload.get("providerCallId") or "").strip()

    call_row: Call | None = None
    if provider_call_id:
        call_row = db.query(Call).filter(
            Call.tenant_id == body.tenant_id,
            Call.provider == provider,
            Call.provider_call_id == provider_call_id,
        ).first()

        if call_row is None:
            call_row = Call(
                tenant_id=body.tenant_id,
                provider=provider,
                provider_call_id=provider_call_id,
                direction=str(call_payload.get("direction") or CallDirection.INBOUND.value),
                status=str(call_payload.get("status") or CallStatus.STARTED.value),
                from_number=body.from_id,
                to_number=body.to_id or "",
                meta_json={"call": call_payload},
            )
            db.add(call_row)
        else:
            # update minimal state
            call_row.status = str(call_payload.get("status") or call_row.status)
            call_row.meta_json = {**(call_row.meta_json or {}), "call": call_payload}

        duration_seconds = call_payload.get("duration_seconds") or call_payload.get("durationSeconds")
        try:
            if duration_seconds is not None:
                call_row.duration_seconds = int(duration_seconds)
        except Exception:
            pass

        # best-effort timestamps
        started_at = call_payload.get("started_at") or call_payload.get("startedAt")
        ended_at = call_payload.get("ended_at") or call_payload.get("endedAt")
        if started_at and isinstance(started_at, str):
            try:
                call_row.started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass
        if ended_at and isinstance(ended_at, str):
            try:
                call_row.ended_at = datetime.fromisoformat(ended_at.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass

        # Persist call row changes
        db.commit()
        db.refresh(call_row)

        AuditLogService(db).safe_log(
            action="voice.event.ingest",
            tenant_id=str(body.tenant_id),
            user_id=None,
            resource_type="call",
            resource_id=str(call_row.id),
            payload={"event_type": body.event_type, "event_id": body.event_id, "provider": provider},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )

        if body.event_type == "voice_call_completed" and call_row.duration_seconds:
            UsageCounterService(db).increment_voice_seconds(body.tenant_id, call_row.duration_seconds)

    n8n = N8NClient(db)
    if not n8n.should_use_n8n(body.tenant_id):
        return VoiceIngestResponse(accepted=False, message="n8n is not enabled for this tenant")

    workflow_id = n8n.get_workflow_id(body.tenant_id, channel="call")
    if not workflow_id:
        return VoiceIngestResponse(accepted=False, message="No n8n workflow configured for call channel")

    raw_payload: dict[str, Any] | None = None
    try:
        raw_payload = await request.json()
    except Exception:
        raw_payload = None

    timestamp = body.timestamp
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()

    async def _dispatch() -> None:
        try:
            run = await n8n.trigger_event(
                tenant_id=body.tenant_id,
                channel="call",
                workflow_id=workflow_id,
                event_type=body.event_type,
                external_event_id=body.event_id,
                from_id=body.from_id,
                to_id=body.to_id,
                text=body.text,
                timestamp=timestamp,
                correlation_id=body.correlation_id,
                contact_name=None,
                raw_payload=raw_payload,
                metadata={"call": body.call or {}, **(body.metadata or {})},
            )
            logger.info("Voice event accepted: tenant=%s run=%s type=%s", body.tenant_id, run.id, body.event_type)
        except Exception as exc:
            logger.error("Voice event dispatch failed: %s", exc, exc_info=True)

    background_tasks.add_task(_dispatch)

    # We don't have run id synchronously (background). Use event id as reference.
    return VoiceIngestResponse(accepted=True, runId=body.event_id, message="Queued")
