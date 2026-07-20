"""Tenant appointment settings, availability and AI-assisted booking."""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.appointment import Appointment
from app.models.conversation import Conversation
from app.models.google_oauth_token import GoogleOAuthToken
from app.models.tenant import Tenant
from app.services.google_calendar_service import GoogleCalendarError, GoogleCalendarService
from app.services.system_event_service import SystemEventService

logger = logging.getLogger(__name__)

DAY_KEYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
ACTION_RE = re.compile(r"<svontai_action>\s*(\{.*?\})\s*</svontai_action>", re.IGNORECASE | re.DOTALL)


def default_appointment_settings() -> dict:
    return {
        "configured": False,
        "timezone": "Europe/Istanbul",
        "minimum_notice_hours": 2,
        "booking_window_days": 30,
        "slot_interval_minutes": 30,
        "booking_location": "",
        "booking_notes": "",
        "services": [
            {"id": "general", "name": "Genel görüşme", "duration_minutes": 60, "active": True},
        ],
        "weekly_hours": {
            key: {
                "enabled": key in {"monday", "tuesday", "wednesday", "thursday", "friday"},
                "start": "09:00",
                "end": "18:00",
            }
            for key in DAY_KEYS
        },
        "closed_dates": [],
    }


class AppointmentAvailabilityService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _timezone(value: str) -> ZoneInfo:
        try:
            return ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Geçersiz saat dilimi") from exc

    def get_settings(self, tenant: Tenant) -> dict:
        defaults = default_appointment_settings()
        stored = dict((tenant.settings or {}).get("appointment_settings") or {})
        weekly = deepcopy(defaults["weekly_hours"])
        for key, value in dict(stored.get("weekly_hours") or {}).items():
            if key in weekly and isinstance(value, dict):
                weekly[key] = {**weekly[key], **value}
        services = stored.get("services")
        return {
            **defaults,
            **stored,
            "services": services if isinstance(services, list) and services else defaults["services"],
            "weekly_hours": weekly,
        }

    def update_settings(self, tenant: Tenant, payload: dict) -> dict:
        self._timezone(str(payload.get("timezone") or "Europe/Istanbul"))
        if set(payload.get("weekly_hours") or {}) != set(DAY_KEYS):
            raise ValueError("Haftanın tüm günleri için çalışma saati gönderilmelidir")
        service_ids = [str(item.get("id") or "") for item in payload.get("services") or []]
        if not service_ids or len(service_ids) != len(set(service_ids)):
            raise ValueError("En az bir benzersiz hizmet tanımlanmalıdır")
        if not any(item.get("active", True) for item in payload.get("services") or []):
            raise ValueError("En az bir hizmet aktif olmalıdır")
        for raw_date in payload.get("closed_dates") or []:
            date.fromisoformat(raw_date)

        payload = {**payload, "configured": True}
        settings = dict(tenant.settings or {})
        settings["appointment_settings"] = deepcopy(payload)
        tenant.settings = settings
        self.db.commit()
        self.db.refresh(tenant)
        return self.get_settings(tenant)

    @staticmethod
    def _parse_clock(value: str) -> time:
        return datetime.strptime(value, "%H:%M").time()

    @staticmethod
    def _overlaps(start_at: datetime, end_at: datetime, busy: list[tuple[datetime, datetime]]) -> bool:
        return any(start_at < busy_end and end_at > busy_start for busy_start, busy_end in busy)

    def get_available_slots(
        self,
        tenant: Tenant,
        *,
        start_date: date | None = None,
        days: int = 7,
        service_id: str | None = None,
        limit: int = 100,
    ) -> dict:
        settings = self.get_settings(tenant)
        local_tz = self._timezone(settings["timezone"])
        if not settings.get("configured"):
            return {
                "timezone": settings["timezone"],
                "reliable": True,
                "calendar_connected": False,
                "warnings": ["Çalışma planı henüz kaydedilmedi."],
                "slots": [],
            }
        services = [item for item in settings["services"] if item.get("active", True)]
        if service_id:
            services = [item for item in services if item.get("id") == service_id]
        if not services:
            return {
                "timezone": settings["timezone"],
                "reliable": True,
                "calendar_connected": False,
                "warnings": ["Aktif randevu hizmeti bulunmuyor."],
                "slots": [],
            }

        now_utc = datetime.now(timezone.utc)
        local_today = now_utc.astimezone(local_tz).date()
        first_date = max(start_date or local_today, local_today)
        horizon_date = local_today + timedelta(days=int(settings["booking_window_days"]))
        last_date = min(first_date + timedelta(days=max(1, days) - 1), horizon_date)
        minimum_start = now_utc + timedelta(hours=int(settings["minimum_notice_hours"]))

        range_start_local = datetime.combine(first_date, time.min, tzinfo=local_tz)
        range_end_local = datetime.combine(last_date + timedelta(days=1), time.min, tzinfo=local_tz)
        range_start_utc = range_start_local.astimezone(timezone.utc).replace(tzinfo=None)
        range_end_utc = range_end_local.astimezone(timezone.utc).replace(tzinfo=None)
        rows = self.db.query(Appointment).filter(
            Appointment.tenant_id == tenant.id,
            Appointment.status.in_(["scheduled", "confirmed"]),
            Appointment.starts_at < range_end_utc,
            Appointment.starts_at >= range_start_utc - timedelta(hours=8),
        ).all()
        busy = [
            (row.starts_at, row.starts_at + timedelta(minutes=row.duration_minutes or 60))
            for row in rows
        ]

        google_token = self.db.query(GoogleOAuthToken).filter(
            GoogleOAuthToken.tenant_id == tenant.id,
            GoogleOAuthToken.provider == "google",
        ).first()
        calendar_connected = google_token is not None
        warnings: list[str] = []
        reliable = True
        if calendar_connected:
            try:
                busy.extend(GoogleCalendarService(self.db).list_tenant_busy_intervals(
                    tenant.id,
                    time_min=range_start_utc,
                    time_max=range_end_utc,
                ))
            except GoogleCalendarError as exc:
                reliable = False
                warnings.append("Google Calendar doluluğu şu anda doğrulanamadı.")
                logger.warning("appointment.google_busy_failed tenant_id=%s error=%s", tenant.id, exc)

        closed_dates = set(settings.get("closed_dates") or [])
        interval = timedelta(minutes=int(settings["slot_interval_minutes"]))
        slots: list[dict] = []
        cursor_date = first_date
        while cursor_date <= last_date and len(slots) < limit:
            day_key = DAY_KEYS[cursor_date.weekday()]
            day_config = settings["weekly_hours"][day_key]
            if day_config.get("enabled") and cursor_date.isoformat() not in closed_dates:
                day_start = datetime.combine(cursor_date, self._parse_clock(day_config["start"]), tzinfo=local_tz)
                day_end = datetime.combine(cursor_date, self._parse_clock(day_config["end"]), tzinfo=local_tz)
                for service in services:
                    duration_minutes = int(service["duration_minutes"])
                    duration = timedelta(minutes=duration_minutes)
                    slot_local = day_start
                    while slot_local + duration <= day_end and len(slots) < limit:
                        slot_utc_aware = slot_local.astimezone(timezone.utc)
                        end_utc_aware = slot_utc_aware + duration
                        slot_utc = slot_utc_aware.replace(tzinfo=None)
                        end_utc = end_utc_aware.replace(tzinfo=None)
                        if slot_utc_aware >= minimum_start and not self._overlaps(slot_utc, end_utc, busy):
                            slots.append({
                                "start_at": slot_utc,
                                "end_at": end_utc,
                                "local_label": slot_local.strftime("%d.%m.%Y %H:%M"),
                                "service_id": service["id"],
                                "service_name": service["name"],
                                "duration_minutes": duration_minutes,
                            })
                        slot_local += interval
            cursor_date += timedelta(days=1)

        slots.sort(key=lambda item: (item["start_at"], item["service_name"]))
        return {
            "timezone": settings["timezone"],
            "reliable": reliable,
            "calendar_connected": calendar_connected,
            "warnings": warnings,
            "slots": slots[:limit],
        }

    def build_ai_context(self, tenant: Tenant) -> str:
        settings = self.get_settings(tenant)
        availability = self.get_available_slots(tenant, days=14, limit=18)
        services = ", ".join(
            f"{item['name']} ({item['duration_minutes']} dk, id={item['id']})"
            for item in settings["services"]
            if item.get("active", True)
        )
        lines = [
            "### GERÇEK RANDEVU BİLGİSİ",
            f"Saat dilimi: {settings['timezone']}",
            f"Hizmetler: {services or 'Tanımlı hizmet yok'}",
            f"Konum: {settings.get('booking_location') or 'Belirtilmedi'}",
            f"İşletme notu: {settings.get('booking_notes') or 'Yok'}",
        ]
        if not availability["reliable"]:
            lines.append("Takvim doluluğu doğrulanamadı. Saat önermek veya randevuyu kesinleştirmek yerine insan desteği öner.")
            return "\n".join(lines)
        if not availability["slots"]:
            lines.append("Şu an uygun randevu saati yok. Uygun saat uydurma; farklı gün tercihi iste veya insan desteği öner.")
            return "\n".join(lines)

        lines.append("Yalnızca aşağıdaki güncel boş saatlerden öner:")
        for item in availability["slots"]:
            lines.append(
                f"- {item['local_label']} | {item['service_name']} | service_id={item['service_id']} | "
                f"start_at={item['start_at'].isoformat()}Z"
            )
        lines.extend([
            "Müşteri bir hizmet ve yukarıdaki saati açıkça onaylarsa, doğal yanıtının SONUNA görünmez işlem satırı olarak şunu ekle:",
            '<svontai_action>{"type":"book_appointment","service_id":"...","start_at":"...Z"}</svontai_action>',
            "Müşteri yalnızca randevu istediğini söylüyorsa işlem oluşturma; önce en fazla 3 uygun seçenek sun.",
        ])
        return "\n".join(lines)

    def apply_ai_action(
        self,
        *,
        tenant: Tenant,
        conversation: Conversation,
        reply: str,
    ) -> tuple[str, Appointment | None]:
        match = ACTION_RE.search(reply or "")
        clean_reply = ACTION_RE.sub("", reply or "").strip()
        if not match:
            return clean_reply, None
        try:
            action = json.loads(match.group(1))
        except json.JSONDecodeError:
            return clean_reply, None
        if action.get("type") != "book_appointment":
            return clean_reply, None

        service_id = str(action.get("service_id") or "")
        raw_start = str(action.get("start_at") or "").replace("Z", "+00:00")
        try:
            selected = datetime.fromisoformat(raw_start)
            if selected.tzinfo is not None:
                selected = selected.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            selected = None
        if selected is None:
            return clean_reply, None

        # Serialize bookings per tenant so two concurrent confirmations cannot
        # claim the same local slot before either transaction commits.
        self.db.query(Tenant).filter(Tenant.id == tenant.id).with_for_update().one()

        active_for_conversation = self.db.query(Appointment).filter(
            Appointment.tenant_id == tenant.id,
            Appointment.conversation_id == conversation.id,
            Appointment.status.in_(["scheduled", "confirmed"]),
            Appointment.starts_at >= utc_now_naive(),
        ).first()
        if active_for_conversation is not None and active_for_conversation.starts_at != selected:
            return "Bu görüşme için zaten aktif bir randevunuz var. Değişiklik için mevcut randevunuzu belirtin.", None

        existing = self.db.query(Appointment).filter(
            Appointment.tenant_id == tenant.id,
            Appointment.conversation_id == conversation.id,
            Appointment.starts_at == selected,
            Appointment.status != "cancelled",
        ).first()
        if existing is not None:
            return clean_reply, None

        local_tz = self._timezone(self.get_settings(tenant)["timezone"])
        selected_local_date = selected.replace(tzinfo=timezone.utc).astimezone(local_tz).date()
        availability = self.get_available_slots(
            tenant,
            start_date=selected_local_date,
            days=2,
            service_id=service_id,
            limit=200,
        )
        valid_slot = next(
            (item for item in availability["slots"] if item["start_at"] == selected),
            None,
        )
        if not availability["reliable"] or valid_slot is None:
            alternatives = availability["slots"][:3]
            labels = ", ".join(item["local_label"] for item in alternatives)
            message = "Seçtiğiniz saat artık uygun görünmüyor."
            if labels:
                message += f" Güncel seçenekler: {labels}."
            return message, None

        customer_name = conversation.customer_name or "WhatsApp müşterisi"
        customer_phone = conversation.customer_phone if conversation.source == "whatsapp" else None
        appointment = Appointment(
            tenant_id=tenant.id,
            created_by=None,
            customer_name=customer_name,
            customer_phone=customer_phone,
            conversation_id=conversation.id,
            subject=valid_slot["service_name"],
            starts_at=selected,
            duration_minutes=valid_slot["duration_minutes"],
            notes="Müşteri konuşma içinde saati açıkça onayladı.",
            source="ai_conversation",
            status="scheduled",
        )
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        SystemEventService(self.db).log(
            tenant_id=str(tenant.id),
            source="appointments",
            level="info",
            code="AI_APPOINTMENT_CREATED",
            message="Müşteri onayıyla otomatik randevu oluşturuldu.",
            meta_json={
                "appointment_id": str(appointment.id),
                "conversation_id": str(conversation.id),
                "service_id": service_id,
                "starts_at": selected.isoformat(),
            },
        )
        return clean_reply, appointment
