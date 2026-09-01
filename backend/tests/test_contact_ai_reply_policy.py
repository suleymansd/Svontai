import asyncio
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers.channels import _automated_reply_blocked, _prepare_automation_delivery
from app.api.routers.conversations import (
    ConversationAIReplyPolicyUpdate,
    update_conversation_ai_reply_policy,
)
from app.api.routers.whatsapp_webhook import handle_incoming_message
from app.db.base import Base
from app.models.automation import AutomationRun
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationSource
from app.models.message import Message, MessageSender
from app.models.tenant import Tenant
from app.models.user import User


def _session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _conversation_fixture(db):
    owner = User(email="owner@example.com", password_hash="x", full_name="Owner")
    db.add(owner)
    db.flush()
    tenant = Tenant(name="Test", slug="test", owner_id=owner.id)
    db.add(tenant)
    db.flush()
    bot = Bot(tenant_id=tenant.id, name="Primary", assistant_type="primary")
    db.add(bot)
    db.flush()
    conversation = Conversation(
        bot_id=bot.id,
        external_user_id="905551112233",
        source=ConversationSource.WHATSAPP.value,
    )
    db.add(conversation)
    db.commit()
    return tenant, conversation


def test_contact_can_be_excluded_without_hiding_messages():
    db = _session()
    tenant, conversation = _conversation_fixture(db)
    db.add(Message(
        conversation_id=conversation.id,
        sender=MessageSender.USER.value,
        content="Merhaba",
    ))
    db.commit()

    updated = asyncio.run(update_conversation_ai_reply_policy(
        conversation_id=conversation.id,
        body=ConversationAIReplyPolicyUpdate(enabled=False),
        current_tenant=tenant,
        db=db,
        _=None,
    ))

    assert updated.ai_reply_enabled is False
    assert "ai_reply_excluded" in updated.tags
    assert len(updated.messages) == 1
    assert _automated_reply_blocked(updated, require_conversation=True) is True


def test_n8n_delivery_is_idempotent_per_run_and_kind():
    db = _session()
    tenant, conversation = _conversation_fixture(db)
    run = AutomationRun(
        tenant_id=str(tenant.id),
        channel="whatsapp",
        from_number="+90 555 111 22 33",
        to_number="905550000000",
        message_id="incoming-1",
        message_content="Hizmetleriniz neler?",
    )
    db.add(run)
    db.flush()
    sent = Message(
        conversation_id=conversation.id,
        sender=MessageSender.BOT.value,
        content="Hizmetlerimiz...",
        external_id="outgoing-1",
        automation_run_id=str(run.id),
        automation_delivery_key=f"{run.id}:text",
        reply_to_external_id="incoming-1",
    )
    db.add(sent)
    db.commit()

    locked_run, existing = _prepare_automation_delivery(
        db,
        tenant_id=str(tenant.id),
        to_number="905551112233",
        run_id=str(run.id),
        delivery_kind="text",
    )

    assert locked_run.id == run.id
    assert existing.id == sent.id


def test_excluded_contact_message_is_saved_without_starting_automation():
    db = _session()
    tenant, conversation = _conversation_fixture(db)
    conversation.ai_reply_enabled = False
    db.commit()

    with patch(
        "app.services.voice_automation_service.VoiceAutomationService.evaluate_whatsapp_message",
        new=AsyncMock(),
    ) as voice_evaluation, patch(
        "app.api.routers.whatsapp_webhook.get_n8n_client",
    ) as n8n_client:
        asyncio.run(handle_incoming_message(
            tenant_id_str=str(tenant.id),
            account_phone_number_id="openwa-session",
            account_display_phone_number="905550000000",
            access_token_encrypted="",
            from_number=conversation.external_user_id,
            contact_name="Aile Kişisi",
            contact_name_source="phonebook",
            message_content="Nasılsın?",
            message_type="text",
            message_id="incoming-excluded-1",
            correlation_id="correlation-1",
            db=db,
            provider="openwa",
        ))

    messages = db.query(Message).filter(Message.conversation_id == conversation.id).all()
    assert [(message.sender, message.content) for message in messages] == [("user", "Nasılsın?")]
    voice_evaluation.assert_not_awaited()
    n8n_client.assert_not_called()
