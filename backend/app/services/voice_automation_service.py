"""Autonomous outbound voice orchestration."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.time import utc_now_naive
from app.models.call import Call, CallDirection, CallStatus, CallSummary, CallTranscript
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.telephony import TelephonyNumber
from app.models.voice_automation import (
    CallIntent,
    CallIntentStatus,
    OutboundCallJob,
    OutboundCallJobStatus,
    TenantVoiceSettings,
    VoiceContactPolicy,
)
from app.services.ai_service import ai_service
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
DNC_PATTERNS = (
    "beni aramayın",
    "beni arama",
    "telefonla aramayın",
    "telefonla arama",
    "arama istemiyorum",
    "aramayın artık",
    "numaramı sil",
)
CONSENT_PATTERNS = (
    "beni arayabilirsiniz",
    "beni ara",
    "telefonla ulaşabilirsiniz",
    "aramayı kabul ediyorum",
)
TERMINAL_PROVIDER_STATUSES = {"completed", "failed", "busy", "no_answer", "cancelled"}
RETRYABLE_PROVIDER_STATUSES = {"failed", "busy", "no_answer"}
PROVIDER_STATUS_MAP = {
    "queued": CallStatus.STARTED.value,
    "initiated": CallStatus.STARTED.value,
    "ringing": CallStatus.STARTED.value,
    "answered": CallStatus.IN_PROGRESS.value,
    "in-progress": CallStatus.IN_PROGRESS.value,
    "in_progress": CallStatus.IN_PROGRESS.value,
    "completed": CallStatus.COMPLETED.value,
    "failed": CallStatus.FAILED.value,
    "busy": CallStatus.BUSY.value,
    "no-answer": CallStatus.NO_ANSWER.value,
    "no_answer": CallStatus.NO_ANSWER.value,
    "canceled": CallStatus.CANCELLED.value,
    "cancelled": CallStatus.CANCELLED.value,
}


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
            "transfer_number",
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
        if "transfer_number" in payload and payload.get("transfer_number"):
            transfer_number = _normalize_phone(str(payload["transfer_number"]))
            if not transfer_number.startswith("+") or len(transfer_number) < 8:
                raise ValueError("Canlı aktarım numarası +90... biçiminde olmalıdır")
            if not self._destination_allowed(transfer_number):
                raise ValueError("Canlı aktarım numarasının ülkesi izin verilen arama listesinde değil")
            payload["transfer_number"] = transfer_number
        if "business_hours_json" in payload and payload.get("business_hours_json") is not None:
            hours = dict(payload["business_hours_json"] or {})
            days = hours.get("days")
            if not isinstance(days, list) or not days:
                raise ValueError("En az bir arama günü seçilmelidir")
            if any(not isinstance(day, int) or not 1 <= day <= 7 for day in days):
                raise ValueError("Arama günleri 1 ile 7 arasında olmalıdır")
            try:
                start = time.fromisoformat(str(hours.get("start") or ""))
                end = time.fromisoformat(str(hours.get("end") or ""))
                ZoneInfo(str(hours.get("timezone") or "Europe/Istanbul"))
            except (ValueError, ZoneInfoNotFoundError) as exc:
                raise ValueError("Çalışma saati veya saat dilimi geçersiz") from exc
            if start >= end:
                raise ValueError("Arama başlangıç saati bitiş saatinden önce olmalıdır")
        for key, value in payload.items():
            if key in allowed and value is not None:
                setattr(settings, key, value)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    async def evaluate_whatsapp_message(
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

        lowered = (message_content or "").casefold()
        if any(pattern in lowered for pattern in DNC_PATTERNS):
            self.set_contact_policy(
                tenant_id=tenant_id,
                phone_number=customer_phone,
                status="do_not_call",
                source="whatsapp",
                reference=external_message_id,
                reason="Müşteri WhatsApp üzerinden aranmak istemediğini belirtti.",
            )
            self._log(
                tenant_id,
                "VOICE_CONTACT_OPTED_OUT",
                "Customer opted out of phone calls",
                {"customer_phone": customer_phone},
                correlation_id,
            )
            return None

        explicit_consent = any(pattern in lowered for pattern in CONSENT_PATTERNS)
        if explicit_consent:
            self.set_contact_policy(
                tenant_id=tenant_id,
                phone_number=customer_phone,
                status="allowed",
                source="whatsapp",
                reference=external_message_id,
                reason="Müşteri WhatsApp üzerinden aranmasına açıkça izin verdi.",
            )
        elif self.is_contact_blocked(tenant_id, customer_phone):
            return None

        existing = None
        if external_message_id:
            existing = self.db.query(CallIntent).filter(
                CallIntent.tenant_id == tenant_id,
                CallIntent.external_message_id == external_message_id,
            ).first()
        if existing is not None:
            return existing

        trigger, confidence = await self._detect_trigger(message_content, settings)
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
        next_attempt_at = self.next_business_opening(settings, now)
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
            confidence=confidence,
            next_attempt_at=next_attempt_at,
            meta_json={
                "source": "whatsapp",
                "message_content": message_content[:1000],
                "correlation_id": correlation_id,
                "consent_basis": "explicit_customer_request" if explicit_consent or trigger == "explicit_call_request" else "tenant_automation_policy",
                "scheduled_outside_business_hours": next_attempt_at > now,
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
                "bypass_business_hours": intent.trigger == "manual_test",
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
        self.reconcile_stale_dispatches(now=now)
        jobs = self.db.query(OutboundCallJob).filter(
            OutboundCallJob.status == OutboundCallJobStatus.PENDING.value,
            (OutboundCallJob.next_attempt_at.is_(None)) | (OutboundCallJob.next_attempt_at <= now),
        ).order_by(OutboundCallJob.created_at.asc()).limit(limit).all()

        started = 0
        failed = 0
        skipped = 0
        for job in jobs:
            try:
                tenant_settings = self.get_or_create_settings(job.tenant_id)
                if self.is_contact_blocked(job.tenant_id, job.to_number):
                    job.status = OutboundCallJobStatus.CANCELLED.value
                    job.last_error = "Contact is on the tenant do-not-call list"
                    self.db.commit()
                    skipped += 1
                    continue
                bypass_business_hours = bool((job.meta_json or {}).get("bypass_business_hours"))
                next_opening = self.next_business_opening(tenant_settings, now)
                if not bypass_business_hours and next_opening > now:
                    job.next_attempt_at = next_opening
                    job.meta_json = {
                        **(job.meta_json or {}),
                        "schedule_reason": "outside_business_hours",
                    }
                    self.db.commit()
                    skipped += 1
                    continue
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

    def reconcile_stale_dispatches(self, *, now: datetime | None = None) -> int:
        cutoff = (now or utc_now_naive()) - timedelta(minutes=15)
        rows = self.db.query(OutboundCallJob).filter(
            OutboundCallJob.status == OutboundCallJobStatus.RUNNING.value,
            OutboundCallJob.updated_at < cutoff,
            OutboundCallJob.provider_call_id.is_(None),
        ).limit(100).all()
        for job in rows:
            job.status = OutboundCallJobStatus.FAILED.value
            job.last_error = (
                "Provider dispatch result is uncertain after worker interruption; "
                "automatic retry was blocked to prevent a duplicate paid call."
            )
            job.meta_json = {
                **(job.meta_json or {}),
                "dispatch_state": "uncertain",
                "reconciled_at": utc_now_naive().isoformat(),
                "manual_retry_required": True,
            }
            if job.call_intent_id:
                intent = self.db.query(CallIntent).filter(CallIntent.id == job.call_intent_id).first()
                if intent:
                    intent.status = CallIntentStatus.FAILED.value
                    intent.processed_at = utc_now_naive()
        if rows:
            self.db.commit()
        return len(rows)

    def _start_job(self, job: OutboundCallJob) -> None:
        if job.status != OutboundCallJobStatus.PENDING.value:
            return
        job.status = OutboundCallJobStatus.RUNNING.value
        job.attempts += 1
        request_payload = self._build_provider_payload(job)
        job.request_payload_json = request_payload
        job.meta_json = {
            **(job.meta_json or {}),
            "dispatch_started_at": utc_now_naive().isoformat(),
            "dispatch_state": "dispatching",
        }
        # Persist the dispatch claim before the provider request. If the process dies
        # after Twilio accepts the request, another worker will not create a duplicate
        # paid call.
        self.db.commit()
        self.db.refresh(job)

        live_response: dict[str, Any] | None = None
        provider_call_id = f"{job.provider}_{job.id.hex}"
        is_live = app_settings.VOICE_OUTBOUND_MODE == "live"
        if is_live:
            if (job.provider or "").lower() != "twilio":
                raise RuntimeError(f"Unsupported live voice provider: {job.provider}")
            live_response = self._start_twilio_call(job, request_payload)
            provider_call_id = str(live_response.get("sid") or provider_call_id)
            job.meta_json = {
                **(job.meta_json or {}),
                "dispatch_state": "accepted",
                "provider_accepted_at": utc_now_naive().isoformat(),
            }

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

    async def _detect_trigger(
        self,
        text: str,
        settings: TenantVoiceSettings,
    ) -> tuple[str | None, int]:
        lowered = (text or "").lower()
        allowed = set(settings.allowed_triggers_json or [])
        has_explicit = any(pattern in lowered for pattern in CALL_REQUEST_PATTERNS)
        if has_explicit and (not allowed or "explicit_call_request" in allowed):
            return "explicit_call_request", 98

        if settings.require_explicit_call_request:
            return None, 0

        if any(pattern in lowered for pattern in APPOINTMENT_PATTERNS) and (
            not allowed or "appointment_intent" in allowed
        ):
            return "appointment_intent", 88
        if any(pattern in lowered for pattern in PRICE_PATTERNS) and (
            not allowed or "price_intent" in allowed
        ):
            return "price_intent", 82

        # Avoid an AI call for ordinary chat. Ambiguous messages with a request,
        # urgency or callback signal receive a provider-neutral semantic check.
        semantic_hints = (
            "ulaş",
            "dönüş",
            "yardım",
            "acil",
            "detay",
            "bilgi",
            "teklif",
            "müsait",
            "konuş",
            "görüş",
        )
        if not any(item in lowered for item in semantic_hints):
            return None, 0
        try:
            raw = await ai_service.generate_text(
                system_prompt=(
                    "Bir müşteri mesajını yalnızca telefon araması gereksinimi açısından sınıflandır. "
                    "JSON dışında hiçbir şey yazma. Şema: "
                    '{"trigger":"explicit_call_request|appointment_intent|price_intent|none",'
                    '"confidence":0-100}. Müşteri açıkça arama istemiyorsa explicit_call_request verme. '
                    "Telefon görüşmesi gerekmeyen sıradan bilgi sorularına none ver."
                ),
                user_text=(text or "")[:1000],
                max_tokens=80,
                temperature=0,
            )
            payload = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            trigger = str(payload.get("trigger") or "none")
            confidence = max(0, min(100, int(payload.get("confidence") or 0)))
            if trigger == "none" or confidence < 75 or (allowed and trigger not in allowed):
                return None, confidence
            if trigger not in {"explicit_call_request", "appointment_intent", "price_intent"}:
                return None, confidence
            return trigger, confidence
        except Exception:
            return None, 0

    def _reason_for_trigger(self, trigger: str) -> str:
        return {
            "explicit_call_request": "Müşteri WhatsApp konuşmasında aranmak istediğini belirtti.",
            "appointment_intent": "Müşteri randevu niyeti gösterdi.",
            "price_intent": "Müşteri fiyat/teklif niyeti gösterdi.",
        }.get(trigger, "Müşteri için telefon görüşmesi daha uygun göründü.")

    def set_contact_policy(
        self,
        *,
        tenant_id: uuid.UUID,
        phone_number: str,
        status: str,
        source: str,
        reference: str | None = None,
        reason: str | None = None,
    ) -> VoiceContactPolicy:
        normalized = _normalize_phone(phone_number)
        if status not in {"allowed", "do_not_call"}:
            raise ValueError("Unsupported voice contact policy")
        row = self.db.query(VoiceContactPolicy).filter(
            VoiceContactPolicy.tenant_id == tenant_id,
            VoiceContactPolicy.phone_number == normalized,
        ).first()
        now = utc_now_naive()
        if row is None:
            row = VoiceContactPolicy(
                tenant_id=tenant_id,
                phone_number=normalized,
                status=status,
                source=source,
            )
            self.db.add(row)
        row.status = status
        row.source = source
        row.reference = reference
        row.reason = reason
        if status == "allowed":
            row.consent_at = now
            row.opted_out_at = None
        else:
            row.opted_out_at = now
        self.db.commit()
        self.db.refresh(row)
        return row

    def is_contact_blocked(self, tenant_id: uuid.UUID, phone_number: str) -> bool:
        normalized = _normalize_phone(phone_number)
        return self.db.query(VoiceContactPolicy).filter(
            VoiceContactPolicy.tenant_id == tenant_id,
            VoiceContactPolicy.phone_number == normalized,
            VoiceContactPolicy.status == "do_not_call",
        ).first() is not None

    @staticmethod
    def next_business_opening(
        settings: TenantVoiceSettings,
        from_utc: datetime | None = None,
    ) -> datetime:
        config = settings.business_hours_json or {}
        try:
            zone = ZoneInfo(str(config.get("timezone") or "Europe/Istanbul"))
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("Europe/Istanbul")
        days = {
            int(value)
            for value in (config.get("days") or [1, 2, 3, 4, 5])
            if str(value).isdigit() and 1 <= int(value) <= 7
        }
        try:
            start_clock = time.fromisoformat(str(config.get("start") or "09:00"))
            end_clock = time.fromisoformat(str(config.get("end") or "18:00"))
        except ValueError:
            start_clock, end_clock = time(9, 0), time(18, 0)
        current_utc = from_utc or utc_now_naive()
        if current_utc.tzinfo is None:
            current_utc = current_utc.replace(tzinfo=timezone.utc)
        else:
            current_utc = current_utc.astimezone(timezone.utc)
        local_now = current_utc.astimezone(zone)

        for offset in range(0, 8):
            candidate_day = (local_now + timedelta(days=offset)).date()
            if candidate_day.isoweekday() not in days:
                continue
            opening = datetime.combine(candidate_day, start_clock, tzinfo=zone)
            closing = datetime.combine(candidate_day, end_clock, tzinfo=zone)
            if offset == 0 and opening <= local_now < closing:
                return current_utc.replace(tzinfo=None)
            if opening > local_now:
                return opening.astimezone(timezone.utc).replace(tzinfo=None)
        return (current_utc + timedelta(days=1)).replace(tzinfo=None)

    @staticmethod
    def normalize_provider_status(value: str | None) -> str:
        normalized = str(value or "").strip().lower()
        return PROVIDER_STATUS_MAP.get(normalized, normalized or CallStatus.STARTED.value)

    def handle_provider_event(
        self,
        *,
        call: Call,
        provider_status: str,
        metadata: dict[str, Any] | None = None,
    ) -> OutboundCallJob | None:
        normalized = self.normalize_provider_status(provider_status)
        call.status = normalized
        job: OutboundCallJob | None = None
        raw_job_id = (metadata or {}).get("outbound_job_id") or (call.meta_json or {}).get("outbound_job_id")
        if raw_job_id:
            try:
                job = self.db.query(OutboundCallJob).filter(
                    OutboundCallJob.id == uuid.UUID(str(raw_job_id)),
                    OutboundCallJob.tenant_id == call.tenant_id,
                ).first()
            except ValueError:
                job = None
        if job is None:
            job = self.db.query(OutboundCallJob).filter(
                OutboundCallJob.tenant_id == call.tenant_id,
                OutboundCallJob.provider_call_id == call.provider_call_id,
            ).first()
        if job is None:
            self.db.commit()
            return None

        if (
            job.status == OutboundCallJobStatus.CANCELLED.value
            and (job.meta_json or {}).get("cancelled_source") == "customer_panel"
        ):
            self.db.commit()
            return job

        already_scheduled_for = (job.meta_json or {}).get("retry_for_provider_call_id")
        if (
            normalized in RETRYABLE_PROVIDER_STATUSES
            and already_scheduled_for == call.provider_call_id
            and job.status == OutboundCallJobStatus.PENDING.value
        ):
            self.db.commit()
            return job

        job.call_id = call.id
        job.provider_call_id = call.provider_call_id
        job.meta_json = {
            **(job.meta_json or {}),
            "last_provider_status": normalized,
            "last_provider_event_at": utc_now_naive().isoformat(),
        }
        intent = (
            self.db.query(CallIntent).filter(CallIntent.id == job.call_intent_id).first()
            if job.call_intent_id
            else None
        )
        if normalized == CallStatus.COMPLETED.value:
            job.status = OutboundCallJobStatus.COMPLETED.value
            job.next_attempt_at = None
            if intent:
                intent.status = CallIntentStatus.COMPLETED.value
                intent.processed_at = utc_now_naive()
            self.ensure_fallback_summary(call)
        elif normalized in RETRYABLE_PROVIDER_STATUSES:
            if job.attempts < job.max_attempts and already_scheduled_for != call.provider_call_id:
                retry_at = self.next_business_opening(
                    self.get_or_create_settings(job.tenant_id),
                    utc_now_naive() + timedelta(minutes=10 * max(1, job.attempts)),
                )
                job.status = OutboundCallJobStatus.PENDING.value
                job.next_attempt_at = retry_at
                job.last_error = f"Provider ended call with status: {normalized}"
                job.meta_json = {
                    **(job.meta_json or {}),
                    "retry_for_provider_call_id": call.provider_call_id,
                    "previous_provider_call_id": call.provider_call_id,
                    "dispatch_state": "retry_scheduled",
                }
                job.call_id = None
                job.provider_call_id = None
                if intent:
                    intent.status = CallIntentStatus.QUEUED.value
                    intent.next_attempt_at = retry_at
            else:
                job.status = OutboundCallJobStatus.FAILED.value
                job.next_attempt_at = None
                if intent:
                    intent.status = CallIntentStatus.FAILED.value
                    intent.processed_at = utc_now_naive()
        elif normalized == CallStatus.CANCELLED.value:
            job.status = OutboundCallJobStatus.CANCELLED.value
            job.next_attempt_at = None
            if intent:
                intent.status = CallIntentStatus.FAILED.value
                intent.processed_at = utc_now_naive()
        self.db.commit()
        return job

    def ensure_fallback_summary(self, call: Call) -> CallSummary:
        existing = self.db.query(CallSummary).filter(CallSummary.call_id == call.id).first()
        if existing is not None:
            return existing
        transcript_rows = self.db.query(CallTranscript).filter(
            CallTranscript.call_id == call.id,
            CallTranscript.tenant_id == call.tenant_id,
        ).order_by(CallTranscript.segment_index.asc()).all()
        customer_lines = [row.text.strip() for row in transcript_rows if row.speaker == "user" and row.text.strip()]
        if customer_lines:
            excerpt = " ".join(customer_lines[-3:])
            summary_text = f"Müşteri görüşmede şunları belirtti: {excerpt[:700]}"
        else:
            summary_text = (
                f"Görüşme {int(call.duration_seconds or 0)} saniye sürdü. "
                "Konuşma dökümü oluşmadığı için ayrıntılı özet hazırlanamadı."
            )
        summary = CallSummary(
            tenant_id=call.tenant_id,
            call_id=call.id,
            intent="voice_conversation",
            summary=summary_text,
            labels_json={"source": "local_fallback"},
            action_items_json={},
        )
        self.db.add(summary)
        self.db.flush()
        return summary

    def enrich_twilio_call_cost(self, call: Call) -> bool:
        if (
            call.provider != "twilio"
            or not call.provider_call_id
            or not app_settings.TWILIO_ACCOUNT_SID.strip()
            or not app_settings.TWILIO_AUTH_TOKEN.strip()
        ):
            return False
        url = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{app_settings.TWILIO_ACCOUNT_SID.strip()}/Calls/{call.provider_call_id}.json"
        )
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    url,
                    auth=(
                        app_settings.TWILIO_ACCOUNT_SID.strip(),
                        app_settings.TWILIO_AUTH_TOKEN.strip(),
                    ),
                )
            if response.status_code >= 400:
                return False
            payload = response.json()
            if payload.get("duration") is not None:
                call.duration_seconds = max(call.duration_seconds or 0, int(payload["duration"]))
            raw_price = payload.get("price")
            if raw_price not in {None, ""}:
                call.cost_estimate = abs(float(raw_price))
                call.meta_json = {
                    **(call.meta_json or {}),
                    "cost_source": "twilio",
                    "cost_currency": str(payload.get("price_unit") or "USD").upper(),
                }
                self.db.commit()
                return True
        except (ValueError, httpx.HTTPError):
            return False
        return False

    def cancel_job(self, tenant_id: uuid.UUID, job_id: uuid.UUID) -> OutboundCallJob:
        job = self.db.query(OutboundCallJob).filter(
            OutboundCallJob.id == job_id,
            OutboundCallJob.tenant_id == tenant_id,
        ).first()
        if job is None:
            raise LookupError("Voice job not found")
        if job.status in {
            OutboundCallJobStatus.COMPLETED.value,
            OutboundCallJobStatus.FAILED.value,
        }:
            raise ValueError("Completed or failed jobs cannot be cancelled")
        if (
            job.status == OutboundCallJobStatus.RUNNING.value
            and job.provider == "twilio"
            and job.provider_call_id
            and app_settings.VOICE_OUTBOUND_MODE == "live"
        ):
            self._cancel_twilio_call(job.provider_call_id)
        job.status = OutboundCallJobStatus.CANCELLED.value
        job.next_attempt_at = None
        job.meta_json = {
            **(job.meta_json or {}),
            "cancelled_at": utc_now_naive().isoformat(),
            "cancelled_source": "customer_panel",
        }
        if job.call_intent_id:
            intent = self.db.query(CallIntent).filter(CallIntent.id == job.call_intent_id).first()
            if intent:
                intent.status = CallIntentStatus.FAILED.value
                intent.processed_at = utc_now_naive()
        self.db.commit()
        self.db.refresh(job)
        return job

    @staticmethod
    def _cancel_twilio_call(provider_call_id: str) -> None:
        account_sid = app_settings.TWILIO_ACCOUNT_SID.strip()
        auth_token = app_settings.TWILIO_AUTH_TOKEN.strip()
        if not account_sid or not auth_token:
            raise ValueError("Twilio credentials are missing")
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/"
            f"Calls/{provider_call_id}.json"
        )
        with httpx.Client(timeout=15) as client:
            response = client.post(
                url,
                data={"Status": "completed"},
                auth=(account_sid, auth_token),
            )
        if response.status_code >= 400:
            raise ValueError(
                f"Twilio call cancellation failed with status {response.status_code}"
            )

    def retry_job(
        self,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        *,
        next_attempt_at: datetime | None = None,
    ) -> OutboundCallJob:
        job = self.db.query(OutboundCallJob).filter(
            OutboundCallJob.id == job_id,
            OutboundCallJob.tenant_id == tenant_id,
        ).first()
        if job is None:
            raise LookupError("Voice job not found")
        if job.status not in {
            OutboundCallJobStatus.FAILED.value,
            OutboundCallJobStatus.CANCELLED.value,
        }:
            raise ValueError("Only failed or cancelled jobs can be retried manually")
        if self.is_contact_blocked(tenant_id, job.to_number):
            raise ValueError("Contact is on the do-not-call list")
        job.status = OutboundCallJobStatus.PENDING.value
        job.attempts = 0
        job.last_error = None
        job.call_id = None
        job.provider_call_id = None
        job.next_attempt_at = self.next_business_opening(
            self.get_or_create_settings(tenant_id),
            next_attempt_at or utc_now_naive(),
        )
        job.meta_json = {
            **(job.meta_json or {}),
            "manual_retry_at": utc_now_naive().isoformat(),
            "dispatch_state": "manual_retry",
        }
        if job.call_intent_id:
            intent = self.db.query(CallIntent).filter(CallIntent.id == job.call_intent_id).first()
            if intent:
                intent.status = CallIntentStatus.QUEUED.value
                intent.next_attempt_at = job.next_attempt_at
        self.db.commit()
        self.db.refresh(job)
        return job

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
        if isinstance(exc, httpx.TransportError):
            job.status = OutboundCallJobStatus.FAILED.value
            job.meta_json = {
                **(job.meta_json or {}),
                "dispatch_state": "uncertain",
                "manual_retry_required": True,
            }
        elif job.attempts >= job.max_attempts:
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
