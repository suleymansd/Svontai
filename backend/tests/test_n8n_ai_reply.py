import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.routers.n8n_tools import (
    AIGenerateRequest,
    AIReplyRequest,
    generate_ai_reply,
    generate_tool_text,
)
from app.models.conversation import ConversationStatus
from app.services.ai_service import ai_service


def _query_returning(*, first=None, all_items=None):
    query = MagicMock()
    query.filter.return_value.first.return_value = first
    query.filter.return_value.all.return_value = list(all_items or [])
    return query


def test_n8n_ai_reply_uses_tenant_bot_context():
    tenant_id = uuid.uuid4()
    bot_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    bot = MagicMock(settings=None)
    conversation = MagicMock(
        is_ai_paused=False,
        status=ConversationStatus.AI_ACTIVE.value,
    )
    knowledge = [MagicMock()]
    db = MagicMock()
    db.query.side_effect = [
        _query_returning(first=bot),
        _query_returning(first=conversation),
        _query_returning(all_items=knowledge),
    ]

    body = AIReplyRequest(
        tenantId=str(tenant_id),
        botId=str(bot_id),
        conversationId=str(conversation_id),
        message="Merhaba",
    )
    with patch("app.api.routers.n8n_tools._verify_tenant", new=AsyncMock()), patch.object(
        ai_service,
        "generate_reply",
        new=AsyncMock(return_value="Size nasıl yardımcı olabilirim?"),
    ) as generate:
        result = asyncio.run(generate_ai_reply(request=MagicMock(), body=body, db=db))

    assert result.should_reply is True
    assert result.reply_text == "Size nasıl yardımcı olabilirim?"
    generate.assert_awaited_once_with(
        bot=bot,
        knowledge_items=knowledge,
        conversation=conversation,
        last_user_message="Merhaba",
        bot_settings=bot.settings,
    )


def test_n8n_ai_reply_stops_during_human_takeover():
    tenant_id = uuid.uuid4()
    bot_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    bot = MagicMock()
    conversation = MagicMock(
        is_ai_paused=True,
        status=ConversationStatus.HUMAN_TAKEOVER.value,
    )
    db = MagicMock()
    db.query.side_effect = [
        _query_returning(first=bot),
        _query_returning(first=conversation),
    ]
    body = AIReplyRequest(
        tenantId=str(tenant_id),
        botId=str(bot_id),
        conversationId=str(conversation_id),
        message="Temsilci istiyorum",
    )

    with patch("app.api.routers.n8n_tools._verify_tenant", new=AsyncMock()), patch.object(
        ai_service,
        "generate_reply",
        new=AsyncMock(),
    ) as generate:
        result = asyncio.run(generate_ai_reply(request=MagicMock(), body=body, db=db))

    assert result.should_reply is False
    assert result.handoff_required is True
    generate.assert_not_awaited()


def test_n8n_tool_generation_uses_allowlisted_prompt():
    body = AIGenerateRequest(
        tenantId=str(uuid.uuid4()),
        purpose="meeting_summary",
        text="Toplantıda cuma günü yayına çıkma kararı alındı.",
    )
    with patch("app.api.routers.n8n_tools._verify_tenant", new=AsyncMock()), patch.object(
        ai_service,
        "generate_text",
        new=AsyncMock(return_value="- Karar: Cuma günü yayına çıkılacak."),
    ) as generate:
        result = asyncio.run(generate_tool_text(request=MagicMock(), body=body))

    assert result.success is True
    assert result.text.startswith("- Karar")
    assert result.output[0].content[0].text == result.text
    generate.assert_awaited_once()
