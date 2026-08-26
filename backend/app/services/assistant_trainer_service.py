"""Conversational specialist builder for the tenant's primary assistant."""

import json
import logging
import re
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.models.assistant_training_session import AssistantTrainingSession
from app.models.bot import Bot
from app.models.bot_settings import BotSettings
from app.models.knowledge import BotKnowledgeItem
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.bot import AssistantTrainerProposal
from app.services.ai_service import ai_service
from app.services.assistant_profile_service import AssistantProfileService

logger = logging.getLogger(__name__)

MAX_SESSION_MESSAGES = 16


class AssistantTrainerUnavailableError(RuntimeError):
    """Raised when the configured AI provider cannot produce a training draft."""


class _TrainerAIResult(BaseModel):
    status: str
    assistant_message: str
    proposal: AssistantTrainerProposal | None = None


class AssistantTrainerService:
    """Collects an instruction, drafts a specialist, and applies it after approval."""

    def __init__(self, db: Session):
        self.db = db

    async def message(
        self,
        *,
        tenant: Tenant,
        user: User,
        message: str,
        session_id: UUID | None,
    ) -> tuple[AssistantTrainingSession, str]:
        session = self._get_or_create_session(tenant=tenant, user=user, session_id=session_id)
        if session.status == "applied":
            return session, "Bu uzman zaten oluşturuldu. Yeni bir uzman için yeni sohbet başlatın."

        messages = list(session.messages_json or [])
        messages.append({"role": "user", "content": message})
        messages = messages[-MAX_SESSION_MESSAGES:]

        try:
            result = await self._generate_result(tenant=tenant, messages=messages)
        except Exception as exc:
            logger.exception("assistant trainer generation failed")
            raise AssistantTrainerUnavailableError(
                "AI eğitim servisi şu anda yanıt vermiyor. Lütfen kısa bir süre sonra tekrar deneyin."
            ) from exc
        status = "ready" if result.status == "ready" and result.proposal else "collecting"
        messages.append({"role": "assistant", "content": result.assistant_message})

        session.messages_json = messages[-MAX_SESSION_MESSAGES:]
        session.status = status
        session.proposal_json = result.proposal.model_dump() if result.proposal else None
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session, result.assistant_message

    def apply(
        self,
        *,
        tenant: Tenant,
        user: User,
        session_id: UUID,
    ) -> tuple[AssistantTrainingSession, Bot, int]:
        session = (
            self.db.query(AssistantTrainingSession)
            .filter(
                AssistantTrainingSession.id == session_id,
                AssistantTrainingSession.tenant_id == tenant.id,
                AssistantTrainingSession.user_id == user.id,
            )
            .with_for_update()
            .first()
        )
        if session is None:
            raise ValueError("Eğitim sohbeti bulunamadı")
        if session.status == "applied" and session.specialist_bot_id:
            bot = self.db.query(Bot).filter(
                Bot.id == session.specialist_bot_id,
                Bot.tenant_id == tenant.id,
            ).first()
            if bot is not None:
                return session, bot, 0
        if session.status != "ready" or not session.proposal_json:
            raise ValueError("Uzman taslağı henüz onaya hazır değil")

        proposal = AssistantTrainerProposal.model_validate(session.proposal_json)
        bot = Bot(
            tenant_id=tenant.id,
            name=proposal.name,
            description=proposal.description,
            welcome_message="Size nasıl yardımcı olabilirim?",
            language="tr",
            primary_color="#0891B2",
            widget_position="right",
            assistant_type="specialist",
            specialist_key=f"trainer_{session.id.hex}",
            is_active=True,
        )
        self.db.add(bot)
        self.db.flush()
        self.db.add(
            BotSettings(
                bot_id=bot.id,
                extra_settings={
                    "managed_by_trainer": True,
                    "trainer_session_id": str(session.id),
                    "behavior_instruction": proposal.behavior_instruction,
                },
            )
        )
        self.db.add(
            BotKnowledgeItem(
                bot_id=bot.id,
                title=proposal.name,
                question="\n".join(proposal.example_questions),
                answer=(
                    f"Yanıt bilgisi: {proposal.answer}\n"
                    f"Davranış talimatı: {proposal.behavior_instruction}"
                ),
            )
        )
        session.status = "applied"
        session.specialist_bot_id = bot.id
        self.db.add(session)
        self.db.commit()
        self.db.refresh(bot)
        self.db.refresh(session)
        return session, bot, 1

    def _get_or_create_session(
        self,
        *,
        tenant: Tenant,
        user: User,
        session_id: UUID | None,
    ) -> AssistantTrainingSession:
        if session_id is None:
            return AssistantTrainingSession(tenant_id=tenant.id, user_id=user.id)
        session = (
            self.db.query(AssistantTrainingSession)
            .filter(
                AssistantTrainingSession.id == session_id,
                AssistantTrainingSession.tenant_id == tenant.id,
                AssistantTrainingSession.user_id == user.id,
            )
            .first()
        )
        if session is None:
            raise ValueError("Eğitim sohbeti bulunamadı")
        return session

    async def _generate_result(self, *, tenant: Tenant, messages: list[dict]) -> _TrainerAIResult:
        primary = AssistantProfileService(self.db).ensure_primary(tenant)
        business_summary = ""
        if primary.settings:
            profile = (primary.settings.extra_settings or {}).get("assistant_profile") or {}
            business_summary = ((profile.get("training") or {}).get("business_summary") or "")[:3000]
        existing_names = [
            row[0]
            for row in self.db.query(Bot.name).filter(
                Bot.tenant_id == tenant.id,
                Bot.assistant_type == "specialist",
            ).all()
        ]
        system_prompt = """Sen SvontAI içindeki güvenli uzman bot tasarım yardımcısısın.
Kullanıcının doğal dilde anlattığı tek bir iş kuralını uygulanabilir bir uzman taslağına çevir.
Yalnızca geçerli JSON döndür; markdown veya ek açıklama yazma.

Çıktı şeması:
{
  "status": "needs_info" veya "ready",
  "assistant_message": "Türkçe, kısa ve doğal mesaj",
  "proposal": null veya {
    "name": "2-80 karakter uzman adı",
    "description": "uzmanın amacı",
    "example_questions": ["müşterinin sorabileceği 1-5 örnek soru"],
    "answer": "yalnızca işletmenin doğruladığı cevap bilgisi",
    "behavior_instruction": "asistanın uygulayacağı açık davranış"
  }
}

Kurallar:
- Hedef müşteri sorusu/niyeti veya verilecek cevap/davranış eksikse status needs_info seç ve tek bir net soru sor.
- Kullanıcı kesin cevap vermediyse fiyat, tarih, stok, adres, politika veya vaat uydurma.
- Taslak hazırsa assistant_message içinde ne oluşturduğunu tek cümlede özetle ve onaya sun.
- Şifre, erişim anahtarı, kart bilgisi veya özel nitelikli kişisel veri isteme.
- Mevcut sohbetin son kullanıcı mesajını ve önceki yanıtları birlikte değerlendir.
"""
        context = {
            "business": {"name": tenant.name, "summary": business_summary},
            "existing_specialists": existing_names[:30],
            "conversation": messages,
        }
        raw = await ai_service.generate_text(
            system_prompt=system_prompt,
            user_text=json.dumps(context, ensure_ascii=False),
            max_tokens=900,
            temperature=0.15,
        )
        try:
            payload = self._parse_json_object(raw)
            result = _TrainerAIResult.model_validate(payload)
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            logger.warning("assistant trainer returned invalid JSON", exc_info=exc)
            return _TrainerAIResult(
                status="needs_info",
                assistant_message="Bunu net bir uzmana çevirebilmem için müşterinin soracağı örnek soruyu ve verilmesini istediğiniz cevabı birlikte yazar mısınız?",
            )
        if result.status != "ready" or result.proposal is None:
            return _TrainerAIResult(
                status="needs_info",
                assistant_message=result.assistant_message[:800],
            )
        return _TrainerAIResult(
            status="ready",
            assistant_message=result.assistant_message[:800],
            proposal=result.proposal,
        )

    @staticmethod
    def _parse_json_object(raw: str) -> dict:
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match is None:
                raise
            parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise ValueError("Trainer response must be an object")
        return parsed
