"""Autonomous outbound voice orchestration."""

from __future__ import annotations

import re
import uuid
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.time import utc_now_naive
from app.models.call import Call, CallDirection, CallStatus
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.telephony import TelephonyNumber
from app.models.voice_automation import (
    CallIntent,
    CallIntentStatus,
    OutboundCallJob,
    OutboundCallJobStatus,
    TenantVoiceSettings,
)
from app.services.system_event_service import SystemEventService
from app.services.usage_counter_service import UsageCounterService


CALL_REQUEST_PATTERNS = (
    "ara",
    "arayın",
    "arasın",
    "telefon",
    "görüşelim",
    "konuşalım",
    "beni arar",
    "beni arayın",
    "call me",
)
APPOINTMENT_PATTERNS = (
    "randevu",
    "rezervasyon",
    "müsait",
    "uygun saat",
    "yarın",
    "bugün",
)
PRICE_PATTERNS = (
    "fiyat",
    "ücret",
    "kaç para",
    "tutar",
    "kampanya",
)


def _normalize_phone(value: str | None) -> str:
    return re.sub(r"[^\d+]", "", value or "").strip()


class VoiceAutomationService:
    """Coordinates call intent creation and outbound call job execution."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_settings(self, tenant_id: uuid.UUID) -> TenantVoiceSettings:
        settings = self.db.query(TenantVoiceSettings).filter(TenantVoiceSettings.tenant_id == tenant_id).first()
        if settings is not None:
            return settings

        number = self.db.query(TelephonyNumber).filter(
            TelephonyNumber.tenant_id == tenant_id,
            TelephonyNumber.is_active.is_(True),
        ).order_by(TelephonyNumber.created_at.asc()).first()
        settings = TenantVoiceSettings(
            tenant_id=tenant_id,
            enabled=False,
            provider=(number.provider if number else "vapi"),
            from_number=(number.phone_number if number else None),
            business_hours_json={
                "timezone": "Europe/Istanbul",
                "days": [1, 2, 3, 4, 5],
                "start": "09:00",
                "end": "18:00",
            },
            allowed_triggers_json=["explicit_call_request", "appointment_intent"],
            handoff_rules_json=["complaint", "unknown_question", "human_request"],
        )
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update_settings(self, tenant_id: uuid.UUID, payload: dict[str, Any]) -> TenantVoiceSettings:
        settings = self.get_or_create_settings(tenant_id)
        allowed = {
            "enabled",
            "provider",
            "from_number",
            "allow_appointment_booking",
            "require_explicit_call_request",
            "business_hours_json",
            "allowed_triggers_json",
            "handoff_rules_json",
            "max_attempts_per_lead",
            "cooldown_minutes",
            "daily_call_limit",
            "meta_json",
        }
        for key, value in payload.items():
            if key in allowed and value is not None:
                setattr(settings, key, value)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def evaluate_whatsapp_message(
        self,
        *,
        tenant_id: uuid.UUID,
        bot_id: uuid.UUID | None,
        conversation_id: uuid.UUID | None,
        customer_phone: str,
        customer_name: str | None,
        message_content: str,
        external_message_id: str | None,
        correlation_id: str | None,
    ) -> CallIntent | None:
        settings = self.get_or_create_settings(tenant_id)
        if not settings.enabled:
            return None

        customer_phone = _normalize_phone(customer_phone)
        if not customer_phone:
            return None

        existing = None
        if external_message_id:
            existing = self.db.query(CallIntent).filter(
                CallIntent.tenant_id == tenant_id,
                CallIntent.external_message_id == external_message_id,
            ).first()
        if existing is not None:
            return existing

        trigger = self._detect_trigger(message_content, settings)
        if trigger is None:
            return None

        if self._recent_pending_or_completed_intent(tenant_id, customer_phone, settings.cooldown_minutes):
            self._log(
                tenant_id,
                "VOICE_CALL_INTENT_SKIPPED_COOLDOWN",
                "Voice call intent skipped because customer is in cooldown",
                {"customer_phone": customer_phone, "trigger": trigger},
                correlation_id,
            )
            return None

        lead = self._get_or_create_lead(tenant_id, bot_id, conversation_id, customer_phone, customer_name)
        now = utc_now_naive()
        intent = CallIntent(
            tenant_id=tenant_id,
            bot_id=bot_id,
            conversation_id=conversation_id,
            lead_id=lead.id if lead else None,
            customer_phone=customer_phone,
            customer_name=customer_name,
            external_message_id=external_message_id,
            trigger=trigger,
            reason=self._reason_for_trigger(trigger),
            status=CallIntentStatus.PENDING.value,
            confidence=90 if trigger == "explicit_call_request" else 75,
            next_attempt_at=now,
            meta_json={
                "source": "whatsapp",
                "message_content": message_content[:1000],
                "correlation_id": correlation_id,
            },
        )
        self.db.add(intent)
        self.db.commit()
        self.db.refresh(intent)

        self.enqueue_intent(intent, settings=settings)
        return intent

    def enqueue_intent(
        self,
        intent: CallIntent,
        *,
        settings: TenantVoiceSettings | None = None,
    ) -> OutboundCallJob | None:
        settings = settings or self.get_or_create_settings(intent.tenant_id)
        if not settings.enabled:
            intent.status = CallIntentStatus.SKIPPED.value
            intent.processed_at = utc_now_naive()
            self.db.commit()
            return None

        from_number = _normalize_phone(settings.from_number)
        if not from_number:
            active_number = self.db.query(TelephonyNumber).filter(
                TelephonyNumber.tenant_id == intent.tenant_id,
                TelephonyNumber.is_active.is_(True),
            ).order_by(TelephonyNumber.created_at.asc()).first()
            from_number = _normalize_phone(active_number.phone_number if active_number else None)
            if active_number:
                settings.from_number = from_number
                settings.provider = active_number.provider or settings.provider

        if not from_number:
            intent.status = CallIntentStatus.SKIPPED.value
            intent.processed_at = utc_now_naive()
            intent.meta_json = {**(intent.meta_json or {}), "skip_reason": "missing_from_number"}
            self.db.commit()
            self._log(
                intent.tenant_id,
                "VOICE_CALL_INTENT_SKIPPED_NO_NUMBER",
                "Voice call intent skipped because tenant has no active outbound number",
                {"intent_id": str(intent.id)},
                (intent.meta_json or {}).get("correlation_id"),
            )
            return None

        existing_job = self.db.query(OutboundCallJob).filter(
            OutboundCallJob.call_intent_id == intent.id,
        ).first()
        if existing_job is not None:
            return existing_job

        job = OutboundCallJob(
            tenant_id=intent.tenant_id,
            call_intent_id=intent.id,
            provider=settings.provider or "vapi",
            from_number=from_number,
            to_number=intent.customer_phone,
            status=OutboundCallJobStatus.PENDING.value,
            max_attempts=max(1, int(settings.max_attempts_per_lead or 1)),
            next_attempt_at=intent.next_attempt_at or utc_now_naive(),
            meta_json={
                "trigger": intent.trigger,
                "reason": intent.reason,
                "customer_name": intent.customer_name,
                "conversation_id": str(intent.conversation_id) if intent.conversation_id else None,
                "lead_id": str(intent.lead_id) if intent.lead_id else None,
            },
        )
        intent.status = CallIntentStatus.QUEUED.value
        intent.processed_at = utc_now_naive()
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        self._log(
            intent.tenant_id,
            "VOICE_CALL_JOB_QUEUED",
            "Autonomous outbound voice call queued",
            {"intent_id": str(intent.id), "job_id": str(job.id), "trigger": intent.trigger},
            (intent.meta_json or {}).get("correlation_id"),
        )
        return job

    def run_due_outbound_jobs(self, limit: int = 20) -> dict[str, int]:
        now = utc_now_naive()
        jobs = self.db.query(OutboundCallJob).filter(
            OutboundCallJob.status == OutboundCallJobStatus.PENDING.value,
            (OutboundCallJob.next_attempt_at.is_(None)) | (OutboundCallJob.next_attempt_at <= now),
        ).order_by(OutboundCallJob.created_at.asc()).limit(limit).all()

        started = 0
        failed = 0
        skipped = 0
        for job in jobs:
            try:
                global_limit_reason = (
                    self._global_limit_reason()
                    if app_settings.VOICE_OUTBOUND_MODE == "live"
                    else None
                )
                if global_limit_reason:
                    job.next_attempt_at = now + timedelta(hours=12)
                    job.meta_json = {**(job.meta_json or {}), "cost_guard_skip_reason": global_limit_reason}
                    self.db.commit()
                    skipped += 1
                    self._log(
                        job.tenant_id,
                        "VOICE_GLOBAL_COST_LIMIT_REACHED",
                        "Outbound voice call delayed by the global cost guard",
                        {"job_id": str(job.id), "reason": global_limit_reason},
                        None,
                    )
                    continue
                if self._daily_limit_reached(job.tenant_id):
                    job.next_attempt_at = now + timedelta(hours=12)
                    job.meta_json = {**(job.meta_json or {}), "cost_guard_skip_reason": "tenant_daily_limit"}
                    self.db.commit()
                    skipped += 1
                    continue
                self._start_job(job)
                started += 1
            except Exception as exc:
                failed += 1
                self._mark_job_failure(job, exc)
        return {"scanned": len(jobs), "started": started, "failed": failed, "skipped": skipped}

    def _start_job(self, job: OutboundCallJob) -> None:
        job.status = OutboundCallJobStatus.RUNNING.value
        job.attempts += 1
        request_payload = self._build_provider_payload(job)
        job.request_payload_json = request_payload

        live_response: dict[str, Any] | None = None
        provider_call_id = f"{job.provider}_{job.id.hex}"
        is_live = app_settings.VOICE_OUTBOUND_MODE == "live"
        if is_live:
            if (job.provider or "").lower() != "twilio":
                raise RuntimeError(f"Unsupported live voice provider: {job.provider}")
            live_response = self._start_twilio_call(job, request_payload)
            provider_call_id = str(live_response.get("sid") or provider_call_id)

        lead_id = None
        raw_lead_id = (job.meta_json or {}).get("lead_id")
        if raw_lead_id:
            try:
                lead_id = uuid.UUID(str(raw_lead_id))
            except ValueError:
                lead_id = None

        call = Call(
            tenant_id=job.tenant_id,
            lead_id=lead_id,
            provider=job.provider,
            provider_call_id=provider_call_id,
            direction=CallDirection.OUTBOUND.value,
            status=CallStatus.STARTED.value,
            from_number=job.from_number,
            to_number=job.to_number,
            started_at=utc_now_naive(),
            meta_json={
                "outbound_job_id": str(job.id),
                "call_intent_id": str(job.call_intent_id) if job.call_intent_id else None,
                "provider_payload": request_payload,
                "dry_run": not is_live,
                "voice_outbound_mode": app_settings.VOICE_OUTBOUND_MODE,
            },
        )
        self.db.add(call)
        self.db.flush()

        job.call_id = call.id
        job.provider_call_id = provider_call_id
        job.response_payload_json = live_response or {
            "status": "queued",
            "provider_call_id": provider_call_id,
            "mode": "dry_run_provider_adapter",
        }
        job.status = OutboundCallJobStatus.RUNNING.value if is_live else OutboundCallJobStatus.COMPLETED.value
        self.db.commit()

        UsageCounterService(self.db).increment_outbound_calls(job.tenant_id, 1)
        self._log(
            job.tenant_id,
            "VOICE_OUTBOUND_CALL_CREATED",
            "Outbound voice call record created",
            {"job_id": str(job.id), "call_id": str(call.id), "provider": job.provider},
            None,
        )

    def _build_provider_payload(self, job: OutboundCallJob) -> dict[str, Any]:
        callback_base = "/api/v1/voice"
        gateway_base = (app_settings.VOICE_GATEWAY_PUBLIC_URL or "").rstrip("/")
        outbound_twiml_url = (
            f"{gateway_base}/twilio/voice/outbound?tenantId={job.tenant_id}&jobId={job.id}"
            if gateway_base
            else ""
        )
        status_callback_url = (
            f"{gateway_base}/twilio/voice/status?tenantId={job.tenant_id}&jobId={job.id}&direction=outbound"
            if gateway_base
            else ""
        )
        return {
            "provider": job.provider,
            "from_number": job.from_number,
            "to_number": job.to_number,
            "mode": app_settings.VOICE_OUTBOUND_MODE,
            "twilio": {
                "url": outbound_twiml_url,
                "status_callback": status_callback_url,
                "status_callback_events": ["initiated", "ringing", "answered", "completed"],
            },
            "metadata": {
                "tenant_id": str(job.tenant_id),
                "outbound_job_id": str(job.id),
                "call_intent_id": str(job.call_intent_id) if job.call_intent_id else None,
                **(job.meta_json or {}),
            },
            "callbacks": {
                "events": f"{callback_base}/events",
                "intent": f"{callback_base}/intent",
                "summary": f"{callback_base}/calls/summary",
            },
        }

    def _start_twilio_call(self, job: OutboundCallJob, payload: dict[str, Any]) -> dict[str, Any]:
        account_sid = app_settings.TWILIO_ACCOUNT_SID.strip()
        auth_token = app_settings.TWILIO_AUTH_TOKEN.strip()
        twilio_payload = payload.get("twilio") or {}
        twiml_url = str(twilio_payload.get("url") or "").strip()
        status_callback = str(twilio_payload.get("status_callback") or "").strip()
        if not account_sid or not auth_token:
            raise RuntimeError("Twilio credentials are missing")
        if not app_settings.VOICE_GATEWAY_PUBLIC_URL.strip() or not twiml_url:
            raise RuntimeError("VOICE_GATEWAY_PUBLIC_URL is required for live outbound calls")
        if not self._destination_allowed(job.to_number):
            raise RuntimeError("Destination country is not allowed by VOICE_ALLOWED_DESTINATION_PREFIXES")

        form_data = {
            "To": job.to_number,
            "From": job.from_number,
            "Url": twiml_url,
            "Method": "POST",
            "TimeLimit": str(app_settings.VOICE_MAX_CALL_DURATION_SECONDS),
        }
        if status_callback:
            form_data.update({
                "StatusCallback": status_callback,
                "StatusCallbackMethod": "POST",
                "StatusCallbackEvent": twilio_payload.get("status_callback_events") or ["initiated", "ringing", "answered", "completed"],
            })

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
        with httpx.Client(timeout=20) as client:
            response = client.post(url, data=form_data, auth=(account_sid, auth_token))
        if response.status_code >= 400:
            raise RuntimeError(f"Twilio call create failed: status={response.status_code} body={response.text[:500]}")
        data = response.json()
        return {
            "status": data.get("status") or "queued",
            "provider_call_id": data.get("sid"),
            "sid": data.get("sid"),
            "mode": "twilio_live",
        }

    def _detect_trigger(self, text: str, settings: TenantVoiceSettings) -> str | None:
        lowered = (text or "").lower()
        allowed = set(settings.allowed_triggers_json or [])
        has_explicit = any(pattern in lowered for pattern in CALL_REQUEST_PATTERNS)
        if has_explicit and (not allowed or "explicit_call_request" in allowed):
            return "explicit_call_request"

        if settings.require_explicit_call_request:
            return None

        if any(pattern in lowered for pattern in APPOINTMENT_PATTERNS) and (
            not allowed or "appointment_intent" in allowed
        ):
            return "appointment_intent"
        if any(pattern in lowered for pattern in PRICE_PATTERNS) and (
            not allowed or "price_intent" in allowed
        ):
            return "price_intent"
        return None

    def _reason_for_trigger(self, trigger: str) -> str:
        return {
            "explicit_call_request": "Müşteri WhatsApp konuşmasında aranmak istediğini belirtti.",
            "appointment_intent": "Müşteri randevu niyeti gösterdi.",
            "price_intent": "Müşteri fiyat/teklif niyeti gösterdi.",
        }.get(trigger, "Müşteri için telefon görüşmesi daha uygun göründü.")

    def _recent_pending_or_completed_intent(self, tenant_id: uuid.UUID, phone: str, cooldown_minutes: int) -> bool:
        cutoff = utc_now_naive() - timedelta(minutes=max(1, cooldown_minutes))
        return self.db.query(CallIntent).filter(
            CallIntent.tenant_id == tenant_id,
            CallIntent.customer_phone == phone,
            CallIntent.created_at >= cutoff,
            CallIntent.status.in_([
                CallIntentStatus.PENDING.value,
                CallIntentStatus.QUEUED.value,
                CallIntentStatus.COMPLETED.value,
            ]),
        ).first() is not None

    def _daily_limit_reached(self, tenant_id: uuid.UUID) -> bool:
        settings = self.get_or_create_settings(tenant_id)
        start = utc_now_naive().replace(hour=0, minute=0, second=0, microsecond=0)
        count = self.db.query(func.count(OutboundCallJob.id)).filter(
            OutboundCallJob.tenant_id == tenant_id,
            OutboundCallJob.created_at >= start,
            OutboundCallJob.status.in_([
                OutboundCallJobStatus.RUNNING.value,
                OutboundCallJobStatus.COMPLETED.value,
            ]),
        ).scalar() or 0
        return int(count) >= int(settings.daily_call_limit or 0)

    def _global_limit_reason(self) -> str | None:
        now = utc_now_naive()
        statuses = [OutboundCallJobStatus.RUNNING.value, OutboundCallJobStatus.COMPLETED.value]
        live_call_filter = or_(
            OutboundCallJob.status == OutboundCallJobStatus.RUNNING.value,
            OutboundCallJob.provider_call_id.like("CA%"),
        )
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = self.db.query(func.count(OutboundCallJob.id)).filter(
            OutboundCallJob.created_at >= day_start,
            OutboundCallJob.status.in_(statuses),
            live_call_filter,
        ).scalar() or 0
        if int(daily_count) >= app_settings.VOICE_GLOBAL_DAILY_CALL_LIMIT:
            return "global_daily_limit"

        month_start = day_start.replace(day=1)
        monthly_count = self.db.query(func.count(OutboundCallJob.id)).filter(
            OutboundCallJob.created_at >= month_start,
            OutboundCallJob.status.in_(statuses),
            live_call_filter,
        ).scalar() or 0
        if int(monthly_count) >= app_settings.VOICE_GLOBAL_MONTHLY_CALL_LIMIT:
            return "global_monthly_limit"
        return None

    @staticmethod
    def _destination_allowed(phone: str) -> bool:
        normalized = _normalize_phone(phone)
        prefixes = [
            item.strip()
            for item in app_settings.VOICE_ALLOWED_DESTINATION_PREFIXES.split(",")
            if item.strip()
        ]
        return bool(normalized and any(normalized.startswith(prefix) for prefix in prefixes))

    def _get_or_create_lead(
        self,
        tenant_id: uuid.UUID,
        bot_id: uuid.UUID | None,
        conversation_id: uuid.UUID | None,
        phone: str,
        name: str | None,
    ) -> Lead | None:
        lead = self.db.query(Lead).filter(
            Lead.tenant_id == tenant_id,
            Lead.phone == phone,
            Lead.is_deleted.is_(False),
        ).first()
        if lead is not None:
            if conversation_id and not lead.conversation_id:
                lead.conversation_id = conversation_id
            if name and not lead.name:
                lead.name = name
            self.db.commit()
            return lead

        lead = Lead(
            tenant_id=tenant_id,
            bot_id=bot_id,
            conversation_id=conversation_id,
            name=name,
            phone=phone,
            status=LeadStatus.NEW.value,
            source=LeadSource.WHATSAPP.value,
            is_auto_detected=True,
            detection_confidence=0.95,
            detected_fields={"phone": phone, "name": name},
            tags=["voice_candidate"],
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)

        return lead

    def _mark_job_failure(self, job: OutboundCallJob, exc: Exception) -> None:
        job.last_error = str(exc)[:4000]
        if job.attempts >= job.max_attempts:
            job.status = OutboundCallJobStatus.FAILED.value
        else:
            job.status = OutboundCallJobStatus.PENDING.value
            job.next_attempt_at = utc_now_naive() + timedelta(minutes=10 * max(1, job.attempts))
        self.db.commit()

    def _log(
        self,
        tenant_id: uuid.UUID,
        code: str,
        message: str,
        meta: dict[str, Any],
        correlation_id: str | None,
    ) -> None:
        SystemEventService(self.db).log(
            tenant_id=str(tenant_id),
            source="voice_automation",
            level="info",
            code=code,
            message=message,
            meta_json=meta,
            correlation_id=correlation_id,
        )
