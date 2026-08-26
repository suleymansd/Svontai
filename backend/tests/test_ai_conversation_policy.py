from app.models.bot import Bot
from app.services.ai_service import AIService
from app.services.conversation_policy import requests_human_support


def test_prompt_asks_for_clarification_instead_of_forcing_handoff():
    prompt = AIService()._build_system_prompt(
        bot=Bot(name="Test Asistanı", description="Test işletmesi"),
        knowledge_items=[],
    )

    assert "Bilgi eksikse konuşmayı kapatma" in prompt
    assert "Belirsizlik tek başına insan desteğine devir nedeni değildir" in prompt
    assert "Sizi bir müşteri temsilcimize bağlıyorum" not in prompt


def test_unrequested_legacy_handoff_is_replaced_with_clarifying_question():
    reply = (
        "Üzgünüm, bu konuda size yardımcı olamıyorum. "
        "Sizi bir müşteri temsilcimize bağlıyorum, lütfen bekleyin."
    )

    repaired = AIService._repair_unrequested_handoff(reply, "Fiyatlarınız hakkında bilgi verir misiniz?")

    assert "temsilci" not in repaired.lower()
    assert "hangi ürün veya hizmet" in repaired.lower()


def test_explicit_human_request_keeps_handoff_reply():
    reply = "Sizi bir müşteri temsilcimize bağlıyorum, lütfen bekleyin."

    repaired = AIService._repair_unrequested_handoff(
        reply,
        "Bir müşteri temsilcisiyle görüşmek istiyorum.",
    )

    assert repaired == reply


def test_human_support_policy_requires_an_action_request():
    assert requests_human_support("Bir müşteri temsilcisiyle görüşmek istiyorum.") is True
    assert requests_human_support("Beni canlı desteğe bağlar mısınız?") is True
    assert requests_human_support("Müşteri temsilcisi misiniz?") is False
