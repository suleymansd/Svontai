"""Deterministic post-generation quality gate and human escalation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.bot_settings import BotSettings
from app.models.conversation import Conversation, ConversationStatus
from app.models.knowledge import BotKnowledgeItem
from app.models.message import MessageSender
from app.models.ticket import Ticket, TicketMessage
from app.services.system_event_service import SystemEventService


@dataclass(frozen=True)
class QualityAssessment:
    reply: str
    passed: bool
    requires_handoff: bool
    reasons: tuple[str, ...]


class AIResponseQualityService:
    """Rejects risky replies without another paid AI request."""

    CURRENCY_RE = re.compile(r"(?<!\w)(\d[\d.,]*)\s*(?:₺|TL|TRY|lira)(?!\w)", re.IGNORECASE)
    INTERNAL_MARKERS = ("<svontai_action>", "### BİLGİ TABANI", "system prompt", "api_key", "access_token")

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^\wçğıöşü]+", " ", value.lower())).strip()

    @staticmethod
    def _remove_repeated_greeting(reply: str, conversation: Conversation) -> str:
        has_bot_reply = any(message.sender == MessageSender.BOT.value for message in conversation.messages or [])
        if not has_bot_reply:
            return reply.strip()
        cleaned = re.sub(
            r"^\s*(?:merhaba|selam(?:lar)?|iyi\s+(?:günler|akşamlar|sabahlar))"
            r"(?:\s+[^,\n.!?]{1,60})?\s*[,!.:-]?\s*",
            "",
            reply,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
        return cleaned or reply.strip()

    def assess(
        self,
        *,
        reply: str,
        conversation: Conversation,
        knowledge_items: list[BotKnowledgeItem],
        bot_settings: BotSettings | None,
        appointment_confirmed: bool,
    ) -> QualityAssessment:
        cleaned = self._remove_repeated_greeting((reply or "").strip(), conversation)
        reasons: list[str] = []

        if not cleaned:
            return QualityAssessment(
                reply="Talebinizi aldım. Ekibimiz kısa süre içinde sizinle ilgilenecek.",
                passed=False,
                requires_handoff=True,
                reasons=("empty_reply",),
            )

        if len(cleaned) > 1800:
            cleaned = cleaned[:1797].rsplit(" ", 1)[0].rstrip() + "..."
            reasons.append("reply_truncated")

        lowered = cleaned.lower()
        if any(marker.lower() in lowered for marker in self.INTERNAL_MARKERS):
            return QualityAssessment(
                reply="Talebinizi güvenli şekilde yanıtlamak için ekibimize aktardım.",
                passed=False,
                requires_handoff=True,
                reasons=("internal_instruction_leak",),
            )

        trusted_text = "\n".join(
            f"{item.title}\n{item.question}\n{item.answer}" for item in knowledge_items
        )
        trusted_amounts = {match.group(1).replace(" ", "") for match in self.CURRENCY_RE.finditer(trusted_text)}
        reply_amounts = {match.group(1).replace(" ", "") for match in self.CURRENCY_RE.finditer(cleaned)}
        if reply_amounts - trusted_amounts:
            return QualityAssessment(
                reply="Güncel fiyatı doğrulamadan yanlış bilgi vermek istemem. Talebinizi ekibimize aktardım.",
                passed=False,
                requires_handoff=True,
                reasons=("unverified_price",),
            )

        booking_claims = (
            "randevunuz oluşturuldu",
            "randevunuz onaylandı",
            "randevunuzu oluşturdum",
            "randevunuzu kaydettim",
        )
        if not appointment_confirmed and any(claim in lowered for claim in booking_claims):
            return QualityAssessment(
                reply="Randevuyu kesinleştirmeden önce uygunluğu yeniden kontrol etmem gerekiyor. Talebinizi ekibimize aktardım.",
                passed=False,
                requires_handoff=True,
                reasons=("unverified_appointment",),
            )

        normalized = self._normalize(cleaned)
        previous_bot_messages = [
            message.content
            for message in (conversation.messages or [])
            if message.sender == MessageSender.BOT.value and message.content
        ][-4:]
        for previous in previous_bot_messages:
            similarity = SequenceMatcher(None, normalized, self._normalize(previous)).ratio()
            if len(normalized) >= 24 and similarity >= 0.92:
                handoff_message = (
                    bot_settings.human_handoff_message
                    if bot_settings and bot_settings.human_handoff_message
                    else "Talebinizi ekibimize aktardım; aynı yanıtı tekrarlamadan sizinle ilgilenecekler."
                )
                return QualityAssessment(
                    reply=handoff_message,
                    passed=False,
                    requires_handoff=True,
                    reasons=("duplicate_reply",),
                )

        if re.search(r"([!?.,])\1{4,}", cleaned) or re.search(r"\b(\w{2,})\s+\1\s+\1\b", lowered):
            return QualityAssessment(
                reply="Mesajınızı aldım. Sağlıklı bir yanıt için talebinizi ekibimize aktardım.",
                passed=False,
                requires_handoff=True,
                reasons=("malformed_reply",),
            )

        return QualityAssessment(
            reply=cleaned,
            passed=not reasons,
            requires_handoff=False,
            reasons=tuple(reasons),
        )


class HumanHandoffService:
    """Pauses AI and creates one deduplicated operator ticket per conversation."""

    def __init__(self, db: Session):
        self.db = db

    def escalate(self, conversation: Conversation, tenant_id: str, reasons: tuple[str, ...]) -> Ticket:
        conversation.status = ConversationStatus.WAITING.value
        conversation.is_ai_paused = True
        conversation.tags = list(dict.fromkeys([*(conversation.tags or []), "ai_quality_review"]))
        conversation.extra_data = {
            **(conversation.extra_data or {}),
            "handoff_reason": list(reasons),
            "handoff_requested_at": utc_now_naive().isoformat(),
        }

        subject = f"AI kalite kontrolü: {conversation.id}"
        ticket = self.db.query(Ticket).filter(
            Ticket.tenant_id == str(tenant_id),
            Ticket.subject == subject,
            Ticket.status.in_(["open", "pending"]),
        ).first()
        if ticket is None:
            ticket = Ticket(
                tenant_id=str(tenant_id),
                requester_id=None,
                subject=subject,
                status="open",
                priority="high",
            )
            self.db.add(ticket)
            self.db.flush()
            self.db.add(TicketMessage(
                ticket_id=ticket.id,
                sender_id=None,
                sender_type="system",
                body="Yanıt gönderim öncesi kalite kontrolünde durduruldu. Nedenler: " + ", ".join(reasons),
            ))

        self.db.commit()
        SystemEventService(self.db).log(
            tenant_id=str(tenant_id),
            source="ai_quality",
            level="warning",
            code="AI_RESPONSE_ESCALATED",
            message="AI response was safely escalated before delivery.",
            meta_json={"conversation_id": str(conversation.id), "ticket_id": ticket.id, "reasons": list(reasons)},
        )
        return ticket
