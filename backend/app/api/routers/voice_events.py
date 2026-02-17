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
from app.models.tenant import Tenant
from app.services.n8n_client import N8NClient

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

