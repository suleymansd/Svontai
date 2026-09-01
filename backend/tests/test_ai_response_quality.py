import uuid

from app.models.conversation import Conversation
from app.models.knowledge import BotKnowledgeItem
from app.models.message import Message
from app.services.ai_response_quality_service import AIResponseQualityService


def _conversation(*bot_replies: str) -> Conversation:
    conversation = Conversation(
        id=uuid.uuid4(),
        bot_id=uuid.uuid4(),
        external_user_id="905551112233",
        source="whatsapp",
    )
    conversation.messages = [
        Message(conversation_id=conversation.id, sender="bot", content=reply)
        for reply in bot_replies
    ]
    return conversation


def _knowledge(answer: str) -> list[BotKnowledgeItem]:
    return [BotKnowledgeItem(bot_id=uuid.uuid4(), title="Fiyat", question="Ücret nedir?", answer=answer)]


def test_quality_gate_removes_repeated_greeting_and_keeps_valid_reply():
    result = AIResponseQualityService().assess(
        reply="Merhaba Ahmet, yarın 14:00 için uygun saatimiz var.",
        conversation=_conversation("Merhaba, nasıl yardımcı olabilirim?"),
        knowledge_items=[],
        bot_settings=None,
        appointment_confirmed=False,
    )
    assert result.requires_handoff is False
    assert result.reply == "yarın 14:00 için uygun saatimiz var."


def test_quality_gate_blocks_unverified_price():
    result = AIResponseQualityService().assess(
        reply="Hizmet bedeli 2.500 TL'dir.",
        conversation=_conversation(),
        knowledge_items=_knowledge("Fiyat için teklif alın."),
        bot_settings=None,
        appointment_confirmed=False,
    )
    assert result.requires_handoff is False
    assert result.reasons == ("unverified_price",)
    assert "kayıtlarımda görünmüyor" in result.reply


def test_quality_gate_allows_verified_price():
    result = AIResponseQualityService().assess(
        reply="Hizmet bedeli 2.500 TL'dir.",
        conversation=_conversation(),
        knowledge_items=_knowledge("Standart hizmet bedeli 2.500 TL'dir."),
        bot_settings=None,
        appointment_confirmed=False,
    )
    assert result.requires_handoff is False


def test_quality_gate_blocks_false_booking_confirmation():
    result = AIResponseQualityService().assess(
        reply="Randevunuz oluşturuldu.",
        conversation=_conversation(),
        knowledge_items=[],
        bot_settings=None,
        appointment_confirmed=False,
    )
    assert result.requires_handoff is False
    assert result.reasons == ("unverified_appointment",)


def test_quality_gate_blocks_near_duplicate_reply():
    previous = "Size uygun seçenekleri kontrol edip birazdan bilgi vereceğim."
    result = AIResponseQualityService().assess(
        reply=previous,
        conversation=_conversation(previous),
        knowledge_items=[],
        bot_settings=None,
        appointment_confirmed=False,
    )
    assert result.requires_handoff is False
    assert result.reasons == ("duplicate_reply",)


def test_quality_gate_handoffs_only_on_explicit_human_request():
    from app.models.bot_settings import BotSettings

    result = AIResponseQualityService().assess(
        reply="Elbette, yardımcı olayım.",
        conversation=_conversation(),
        knowledge_items=[],
        bot_settings=BotSettings(
            human_handoff_enabled=True,
            human_handoff_message="Talebinizi ekibimize aktardım.",
        ),
        appointment_confirmed=False,
        user_message="Bir müşteri temsilcisiyle görüşmek istiyorum.",
    )

    assert result.requires_handoff is True
    assert result.reasons == ("human_requested",)
    assert result.reply == "Talebinizi ekibimize aktardım."


def test_quality_gate_does_not_handoff_for_ordinary_unknown_question():
    from app.models.bot_settings import BotSettings

    result = AIResponseQualityService().assess(
        reply="Bu detayı netleştirmek için hangi hizmeti istediğinizi söyler misiniz?",
        conversation=_conversation(),
        knowledge_items=[],
        bot_settings=BotSettings(human_handoff_enabled=True),
        appointment_confirmed=False,
        user_message="Bu işlemin ayrıntıları nedir?",
    )

    assert result.requires_handoff is False
    assert result.reasons == ()


def test_quality_gate_removes_near_duplicate_sentences():
    reply = (
        "Web tasarım ve dijital pazarlama hizmeti veriyoruz. "
        "Web tasarımı ve dijital pazarlama hizmetleri veriyoruz. "
        "Hangi hizmetle ilgileniyorsunuz?"
    )

    cleaned = AIResponseQualityService._remove_redundant_sentences(reply)

    assert cleaned.count("dijital pazarlama") == 1
    assert "Hangi hizmetle ilgileniyorsunuz?" in cleaned
