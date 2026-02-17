"""
Voice intent endpoint (synchronous).

Twilio <Gather> needs a fast response (TwiML). For that reason, this endpoint:
- verifies Voice Gateway signature
- triggers n8n call workflow synchronously
- returns responseText/endCall so Voice Gateway can render TwiML
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.voice_security import verify_voice_gateway_request_dependency
from app.db.session import get_db
from app.models.call import Call, CallTranscript
from app.models.tenant import Tenant
from app.services.n8n_client import N8NClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["Voice (Gateway)"])


class VoiceIntentRequest(BaseModel):
    tenant_id: UUID = Field(..., alias="tenantId")
    event_type: str = Field(..., alias="eventType")
    event_id: str = Field(..., alias="eventId")
    from_id: str = Field(..., alias="from")
    to_id: str | None = Field(default=None, alias="to")
    text: str = Field(..., min_length=1, max_length=4000)
    timestamp: str | None = None
    correlation_id: str | None = Field(default=None, alias="correlationId")
    call: dict | None = None
    metadata: dict | None = None

    class Config:
        populate_by_name = True


class VoiceIntentResponse(BaseModel):
    ok: bool = True
    run_id: str | None = Field(default=None, alias="runId")
    response_text: str = Field(..., alias="responseText")
    end_call: bool = Field(default=False, alias="endCall")
    raw: dict | None = None

    class Config:
        populate_by_name = True


@router.post("/intent", response_model=VoiceIntentResponse)
async def voice_intent(
    request: Request,
    body: VoiceIntentRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_voice_gateway_request_dependency),
) -> VoiceIntentResponse:
    tenant = db.query(Tenant).filter(Tenant.id == body.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    n8n = N8NClient(db)
    if not n8n.should_use_n8n(body.tenant_id):
        return VoiceIntentResponse(ok=True, runId=None, responseText="Bu tenant için otomasyon kapalı.", endCall=True)

    workflow_id = n8n.get_workflow_id(body.tenant_id, channel="call")
    if not workflow_id:
        return VoiceIntentResponse(ok=True, runId=None, responseText="Voice workflow yapılandırılmamış.", endCall=True)

    timestamp = body.timestamp or datetime.now(timezone.utc).isoformat()
    call_payload = body.call or {}
    provider = str(call_payload.get("provider") or "unknown").strip()[:50]
    provider_call_id = str(call_payload.get("provider_call_id") or call_payload.get("providerCallId") or "").strip()
    turn_index = int((body.metadata or {}).get("turn") or 0)

    call_row: Call | None = None
    if provider_call_id:
        call_row = db.query(Call).filter(
            Call.tenant_id == body.tenant_id,
            Call.provider == provider,
            Call.provider_call_id == provider_call_id,
        ).first()

    run, is_new = n8n.create_automation_run(
        tenant_id=body.tenant_id,
        channel="call",
        from_number=body.from_id,
        to_number=body.to_id,
        message_id=body.event_id,
        message_content=body.text,
        workflow_id=workflow_id,
        correlation_id=body.correlation_id,
    )

    # Transcript write (user turn) best-effort, idempotent by segment_index.
    if call_row is not None and body.text:
        user_segment_index = max(0, turn_index * 2)
        existing = db.query(CallTranscript).filter(
            CallTranscript.call_id == call_row.id,
            CallTranscript.tenant_id == body.tenant_id,
            CallTranscript.segment_index == user_segment_index,
        ).first()
        if existing is None:
            db.add(
                CallTranscript(
                    tenant_id=body.tenant_id,
                    call_id=call_row.id,
                    segment_index=user_segment_index,
                    speaker="user",
                    text=body.text,
                    ts_iso=timestamp,
                )
            )
            db.commit()

    # If duplicated and we already have a response payload, reuse it.
    if not is_new and run.response_payload:
        response_data = run.response_payload or {}
        response_text = str(response_data.get("responseText") or response_data.get("response_text") or "").strip()
        if not response_text:
            response_text = "Bir saniye lütfen."
        end_call = bool(response_data.get("endCall") or response_data.get("end_call") or False)
        return VoiceIntentResponse(ok=True, runId=str(run.id), responseText=response_text, endCall=end_call, raw=response_data)

    payload = n8n.build_event_payload(
        tenant_id=body.tenant_id,
        run_id=str(run.id),
        event_type=body.event_type,
        channel="call",
        external_event_id=body.event_id,
        from_id=body.from_id,
        to_id=body.to_id,
        text=body.text,
        timestamp=timestamp,
        correlation_id=body.correlation_id,
        contact_name=None,
        raw_payload={"call": body.call or {}, "metadata": body.metadata or {}},
        metadata={"call": body.call or {}, **(body.metadata or {})},
    )

    try:
        response_data = await n8n.trigger_with_retry(workflow_id, payload, body.tenant_id, run) or {}
    except Exception as exc:
        logger.warning("voice intent n8n trigger failed: %s", exc, exc_info=True)
        response_data = {"responseText": "Şu anda yardımcı olamıyorum. Lütfen daha sonra tekrar deneyin.", "endCall": True}

    response_text = str(response_data.get("responseText") or response_data.get("response_text") or "").strip()
    if not response_text:
        response_text = "Anladım. Devam edelim."
    end_call = bool(response_data.get("endCall") or response_data.get("end_call") or False)

    # Transcript write (agent turn) best-effort.
    if call_row is not None and response_text:
        agent_segment_index = max(0, turn_index * 2 + 1)
        existing = db.query(CallTranscript).filter(
            CallTranscript.call_id == call_row.id,
            CallTranscript.tenant_id == body.tenant_id,
            CallTranscript.segment_index == agent_segment_index,
        ).first()
        if existing is None:
            db.add(
                CallTranscript(
                    tenant_id=body.tenant_id,
                    call_id=call_row.id,
                    segment_index=agent_segment_index,
                    speaker="agent",
                    text=response_text,
                    ts_iso=datetime.now(timezone.utc).isoformat(),
                )
            )
            db.commit()

    return VoiceIntentResponse(ok=True, runId=str(run.id), responseText=response_text, endCall=end_call, raw=response_data)
