"""Deterministic, confirmation-gated appointment flow for voice calls."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.call import Call
from app.models.tenant import Tenant
from app.services.appointment_availability_service import AppointmentAvailabilityService


APPOINTMENT_RE = re.compile(r"\b(randevu|rezervasyon|görüşme|görüşmek|takvim|müsait|uygun saat)\b", re.IGNORECASE)
POSITIVE_RE = re.compile(r"\b(evet|onaylıyorum|onayla|tamam|olur|uygun|kabul)\b", re.IGNORECASE)
NEGATIVE_RE = re.compile(r"\b(hayır|istemiyorum|vazgeçtim|iptal|uygun değil|olmaz)\b", re.IGNORECASE)
SELECTION_PATTERNS = (
    re.compile(r"\b(bir|birinci|ilk)\b", re.IGNORECASE),
    re.compile(r"\b(iki|ikinci)\b", re.IGNORECASE),
    re.compile(r"\b(üç|üçüncü)\b", re.IGNORECASE),
)
SELECTION_LABELS = ("Birinci", "İkinci", "Üçüncü")
MONTH_NAMES = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)
DAY_NAMES = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")


@dataclass
class VoiceAppointmentResult:
    handled: bool
    response_text: str = ""
    appointment: Appointment | None = None


class VoiceAppointmentService:
    def __init__(self, db: Session):
        self.db = db
        self.availability = AppointmentAvailabilityService(db)

    @staticmethod
    def _state(call: Call) -> dict:
        value = (call.meta_json or {}).get("voice_booking")
        return dict(value) if isinstance(value, dict) else {}

    def _save_state(self, call: Call, state: dict) -> None:
        call.meta_json = {**(call.meta_json or {}), "voice_booking": state}
        self.db.commit()
        self.db.refresh(call)

    @staticmethod
    def _selection_index(text: str) -> int | None:
        for index, pattern in enumerate(SELECTION_PATTERNS):
            if pattern.search(text):
                return index
        return None

    @staticmethod
    def _offer_text(proposals: list[dict]) -> str:
        labels = [
            f"{SELECTION_LABELS[index]} seçenek, {item['spoken_label']}, {item['service_name']}"
            for index, item in enumerate(proposals)
        ]
        return "Uygun saatleri kontrol ettim. " + ". ".join(labels) + ". Hangisini istersiniz?"

    @staticmethod
    def _spoken_label(local_label: str) -> str:
        value = datetime.strptime(local_label, "%d.%m.%Y %H:%M")
        return (
            f"{value.day} {MONTH_NAMES[value.month - 1]} {DAY_NAMES[value.weekday()]} günü, "
            f"saat {value.hour:02d}.{value.minute:02d}"
        )

    def _fresh_proposals(self, tenant: Tenant) -> tuple[list[dict], str | None]:
        availability = self.availability.get_available_slots(tenant, days=14, limit=18)
        if not availability["reliable"]:
            return [], "Takvim uygunluğunu şu anda doğrulayamıyorum. Birkaç dakika sonra tekrar deneyelim."
        if not availability["slots"]:
            return [], "Önümüzdeki günlerde uygun bir randevu saati görünmüyor. Farklı bir dönem için tekrar sorabilirsiniz."
        proposals = [
            {
                "start_at": item["start_at"].isoformat() + "Z",
                "local_label": item["local_label"],
                "spoken_label": self._spoken_label(item["local_label"]),
                "service_id": item["service_id"],
                "service_name": item["service_name"],
            }
            for item in availability["slots"][:3]
        ]
        return proposals, None

    def handle_turn(self, *, tenant: Tenant, call: Call, user_text: str) -> VoiceAppointmentResult:
        state = self._state(call)
        stage = str(state.get("stage") or "")
        has_intent = bool(APPOINTMENT_RE.search(user_text or ""))

        if stage == "completed":
            if has_intent or POSITIVE_RE.search(user_text or ""):
                return VoiceAppointmentResult(
                    handled=True,
                    response_text="Bu görüşmedeki randevunuz zaten oluşturuldu ve işletme takvimine kaydedildi.",
                )
            return VoiceAppointmentResult(handled=False)

        if not stage and not has_intent:
            return VoiceAppointmentResult(handled=False)

        if stage == "awaiting_confirmation":
            selected = state.get("selected") if isinstance(state.get("selected"), dict) else None
            if selected is None:
                stage = "awaiting_selection"
            elif NEGATIVE_RE.search(user_text or ""):
                proposals = list(state.get("proposals") or [])
                self._save_state(call, {"stage": "awaiting_selection", "proposals": proposals})
                return VoiceAppointmentResult(
                    handled=True,
                    response_text="Tamam, bu saati seçmedim. " + self._offer_text(proposals),
                )
            elif POSITIVE_RE.search(user_text or ""):
                action = {
                    "type": "book_appointment",
                    "service_id": selected["service_id"],
                    "start_at": selected["start_at"],
                }
                action_reply = (
                    "Randevunuz oluşturuldu. "
                    f"<svontai_action>{json.dumps(action, ensure_ascii=False)}</svontai_action>"
                )
                clean_reply, appointment = self.availability.apply_ai_action(
                    tenant=tenant,
                    call=call,
                    reply=action_reply,
                )
                if appointment is None:
                    self._save_state(call, {})
                    return VoiceAppointmentResult(handled=True, response_text=clean_reply)
                self._save_state(
                    call,
                    {
                        "stage": "completed",
                        "appointment_id": str(appointment.id),
                        "selected": selected,
                    },
                )
                return VoiceAppointmentResult(
                    handled=True,
                    response_text=(
                        f"Randevunuz {selected['spoken_label']} için oluşturuldu. "
                        "İşletmenin randevu sistemine kaydettim."
                    ),
                    appointment=appointment,
                )
            else:
                return VoiceAppointmentResult(
                    handled=True,
                    response_text=f"{selected['spoken_label']} için randevuyu onaylıyor musunuz?",
                )

        if stage == "awaiting_selection":
            proposals = list(state.get("proposals") or [])
            selection = self._selection_index(user_text or "")
            if selection is None or selection >= len(proposals):
                return VoiceAppointmentResult(
                    handled=True,
                    response_text="Birinci, ikinci veya üçüncü seçenekten hangisini istediğinizi söyler misiniz?",
                )
            selected = proposals[selection]
            self._save_state(
                call,
                {
                    "stage": "awaiting_confirmation",
                    "proposals": proposals,
                    "selected": selected,
                },
            )
            return VoiceAppointmentResult(
                handled=True,
                response_text=f"{selected['spoken_label']} için randevuyu onaylıyor musunuz?",
            )

        proposals, error_message = self._fresh_proposals(tenant)
        if error_message:
            return VoiceAppointmentResult(handled=True, response_text=error_message)
        self._save_state(call, {"stage": "awaiting_selection", "proposals": proposals})
        return VoiceAppointmentResult(handled=True, response_text=self._offer_text(proposals))
