"""
Voice intent endpoint (synchronous).

Twilio <Gather> needs a fast response (TwiML). For that reason, this endpoint:
- verifies Voice Gateway signature
- generates a tenant-aware response with the configured AI provider
- returns responseText/endCall so Voice Gateway can render TwiML
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.voice_security import verify_voice_gateway_request_dependency
from app.db.session import get_db
from app.models.call import Call, CallTranscript
from app.models.tenant import Tenant
from app.services.ai_service import ai_service
from app.services.appointment_availability_service import AppointmentAvailabilityService
from app.services.assistant_knowledge_service import AssistantKnowledgeService
from app.services.assistant_profile_service import AssistantProfileService
from app.services.audit_log_service import AuditLogService
from app.services.n8n_client import N8NClient
from app.services.push_notification_service import send_tenant_push_notification
from app.services.voice_appointment_service import VoiceAppointmentService
from app.services.voice_automation_service import VoiceAutomationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["Voice (Gateway)"])


class VoiceIntentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

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


class VoiceIntentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    run_id: str | None = Field(default=None, alias="runId")
    response_text: str = Field(..., alias="responseText")
    end_call: bool = Field(default=False, alias="endCall")
    transfer_to: str | None = Field(default=None, alias="transferTo")
    raw: dict | None = None



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

    run_service = N8NClient(db)
    run, is_new = run_service.create_automation_run(
        tenant_id=body.tenant_id,
        channel="call",
        from_number=body.from_id,
        to_number=body.to_id,
        message_id=body.event_id,
        message_content=body.text,
        workflow_id="direct-voice-ai",
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

    try:
        profile_service = AssistantProfileService(db)
        bot = profile_service.ensure_primary(tenant)
        segments: list[tuple[str, str]] = []
        if call_row is not None:
            rows = db.query(CallTranscript).filter(
                CallTranscript.call_id == call_row.id,
                CallTranscript.tenant_id == body.tenant_id,
            ).order_by(CallTranscript.segment_index.desc()).limit(12).all()
            segments = [(row.speaker, row.text) for row in reversed(rows)]
        appointment = None
        voice_settings = VoiceAutomationService(db).get_or_create_settings(body.tenant_id)
        appointment_enabled = (
            voice_settings.allow_appointment_booking
            and profile_service.capability_enabled(bot, "appointment_management")
        )
        human_request = any(
            phrase in body.text.casefold()
            for phrase in (
                "insanla konuş",
                "yetkiliyle görüş",
                "müşteri temsilcisi",
                "birine bağla",
                "yetkiliye bağla",
            )
        )
        transfer_to = (
            str(voice_settings.transfer_number or "").strip()
            if human_request
            else ""
        )
        booking_result = None
        if transfer_to:
            response_text = "Sizi şimdi bir yetkiliye bağlıyorum."
        elif human_request:
            response_text = (
                "Şu anda canlı aktarım numarası tanımlı değil. "
                "İşletmeyle Vatsap üzerinden iletişime geçebilirsiniz."
            )
        elif call_row is not None and appointment_enabled:
            booking_result = VoiceAppointmentService(db).handle_turn(
                tenant=tenant,
                call=call_row,
                user_text=body.text,
            )
        if booking_result is not None and booking_result.handled:
            response_text = booking_result.response_text
            appointment = booking_result.appointment
        else:
            response_text = await ai_service.generate_voice_reply(
                bot=bot,
                knowledge_items=AssistantKnowledgeService.list_effective(db, bot),
                user_text=body.text,
                transcript=segments,
                bot_settings=bot.settings,
                runtime_context=profile_service.build_runtime_context(tenant, bot),
            )
            if call_row is not None and appointment_enabled:
                response_text, appointment = AppointmentAvailabilityService(db).apply_ai_action(
                    tenant=tenant,
                    call=call_row,
                    reply=response_text,
                )
        if appointment is not None:
            call_row.meta_json = {
                **(call_row.meta_json or {}),
                "appointment_id": str(appointment.id),
            }
            db.commit()
            AuditLogService(db).safe_log(
                action="voice.appointment.create",
                tenant_id=body.tenant_id,
                user_id=None,
                resource_type="appointment",
                resource_id=str(appointment.id),
                payload={
                    "call_id": str(call_row.id),
                    "starts_at": appointment.starts_at.isoformat(),
                    "source": appointment.source,
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent"),
            )
            await send_tenant_push_notification(
                tenant_id=body.tenant_id,
                event_type="appointment",
                title="Sesli asistandan yeni randevu",
                body=f"{appointment.customer_name} için {appointment.subject} randevusu oluşturuldu.",
                url="/dashboard/appointments",
                tag="svontai-voice-appointment",
                extra={
                    "appointment_id": str(appointment.id),
                    "call_id": str(call_row.id),
                },
            )
        end_call = any(
            phrase in body.text.casefold()
            for phrase in ("görüşürüz", "hoşça kal", "kapatabiliriz", "teşekkürler bu kadar")
        )
        response_data = {
            "responseText": response_text,
            "endCall": end_call,
            "provider": ai_service.provider,
            "appointmentCreated": appointment is not None,
            "appointmentId": str(appointment.id) if appointment is not None else None,
            "transferTo": transfer_to or None,
        }
        run.mark_success(response_data)
        db.commit()
    except Exception as exc:
        logger.warning("voice intent AI generation failed: %s", exc, exc_info=True)
        response_data = {"responseText": "Şu anda yardımcı olamıyorum. Lütfen daha sonra tekrar deneyin.", "endCall": True}
        run.mark_failed(str(exc), response_data)
        db.commit()

    response_text = str(response_data.get("responseText") or response_data.get("response_text") or "").strip()
    if not response_text:
        response_text = "Anladım. Devam edelim."
    end_call = bool(response_data.get("endCall") or response_data.get("end_call") or False)
    transfer_to = str(response_data.get("transferTo") or response_data.get("transfer_to") or "").strip() or None

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

    return VoiceIntentResponse(
        ok=True,
        runId=str(run.id),
        responseText=response_text,
        endCall=end_call,
        transferTo=transfer_to,
        raw=response_data,
    )
