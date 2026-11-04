"""Audit A11: the quota unit is a delivered AI reply.

AI-excluded contacts and operator-sent messages consume neither reply quota,
usage counters nor AI token budget.
"""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

from tests.test_reliability_regressions import workspace  # noqa: F401


def _snapshot(tenant_id):
    from app.db.session import SessionLocal
    from app.models.reply_reservation import ReplyReservation
    from app.models.subscription import TenantSubscription
    from app.models.usage_ledger import UsageLedgerEntry
    from app.services.usage_counter_service import UsageCounterService
    with SessionLocal() as db:
        counter = UsageCounterService(db).get_or_create(tenant_id)
        return {
            "messages_used": db.query(TenantSubscription).filter_by(tenant_id=tenant_id).one().messages_used_this_month,
            "message_count": counter.message_count,
            "ai_tokens": int((counter.extra_json or {}).get("ai_input_tokens") or 0)
            + int((counter.extra_json or {}).get("ai_output_tokens") or 0),
            "reservations": db.query(ReplyReservation).filter_by(tenant_id=tenant_id).count(),
            "ledger_rows": db.query(UsageLedgerEntry).filter_by(tenant_id=tenant_id).count(),
        }


def _stub_model(monkeypatch):
    from app.services.ai_service import ai_service
    generate_reply = AsyncMock(return_value="Bu yanit asla uretilmemeli.")
    monkeypatch.setattr(ai_service, "generate_reply", generate_reply)
    return generate_reply


def test_ai_excluded_contact_consumes_no_quota_or_budget(client, workspace, monkeypatch):
    from app.api.routers import whatsapp_webhook
    from app.db.session import SessionLocal
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.services.whatsapp_gateway_service import whatsapp_gateway_service
    _, tenant_id, bot_id, conversation_id = workspace
    generate_reply = _stub_model(monkeypatch)
    send_text = AsyncMock(return_value={"message_id": "wamid.never"})
    monkeypatch.setattr(whatsapp_gateway_service, "send_text", send_text)
    with SessionLocal() as db:
        db.get(Conversation, conversation_id).ai_reply_enabled = False
        db.add(Message(conversation_id=conversation_id, sender="user", content="Merhaba", external_id="wamid.excluded"))
        db.commit()
    before = _snapshot(tenant_id)

    asyncio.run(whatsapp_webhook.process_whatsapp_reply_in_background(
        tenant_id=tenant_id, bot_id=bot_id, conversation_id=conversation_id, account_phone_number_id="pn-1",
        provider="meta", from_number="905551112233", to_number="pn-1", message_content="Merhaba",
        message_id="wamid.excluded", timestamp="1", correlation_id="corr", contact_name=None, raw_payload=None,
        use_n8n=False, n8n_workflow_id=None,
    ))

    generate_reply.assert_not_awaited()
    send_text.assert_not_awaited()
    after = _snapshot(tenant_id)
    assert after == before
    assert after["reservations"] == 0 and after["messages_used"] == 0 and after["ai_tokens"] == 0
    with SessionLocal() as db:
        assert db.query(Message).filter_by(conversation_id=conversation_id, sender="bot").count() == 0
        # the message is still stored and visible to the operator
        assert db.query(Message).filter_by(external_id="wamid.excluded").count() == 1


def test_inbound_webhook_does_not_schedule_ai_work_for_excluded_contact(client, workspace, monkeypatch):
    """The inbound handler returns before any background reply job, so nothing can reserve quota later."""
    from unittest.mock import MagicMock
    from app.api.routers import whatsapp_webhook
    from app.db.session import SessionLocal
    from app.models.conversation import Conversation
    from app.models.message import Message
    _, tenant_id, _, conversation_id = workspace
    generate_reply = _stub_model(monkeypatch)
    scheduled = AsyncMock()
    monkeypatch.setattr(whatsapp_webhook, "process_whatsapp_reply_in_background", scheduled)
    monkeypatch.setattr(
        "app.services.voice_automation_service.VoiceAutomationService.evaluate_whatsapp_message", AsyncMock(),
    )
    monkeypatch.setattr(whatsapp_webhook, "get_n8n_client", MagicMock())
    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        conversation.is_ai_paused = True
        external_user_id = conversation.external_user_id
        db.commit()
    before = _snapshot(tenant_id)

    background_tasks = MagicMock()
    with SessionLocal() as db:
        asyncio.run(whatsapp_webhook.handle_incoming_message(
            tenant_id_str=str(tenant_id), account_phone_number_id="pn-1", account_display_phone_number="905550000000",
            access_token_encrypted="", from_number=external_user_id, contact_name="Musteri", contact_name_source="profile",
            message_content="Nasilsin?", message_type="text", message_id="wamid.paused", correlation_id="corr",
            db=db, provider="meta", background_tasks=background_tasks,
        ))

    background_tasks.add_task.assert_not_called()
    scheduled.assert_not_awaited()
    generate_reply.assert_not_awaited()
    assert _snapshot(tenant_id) == before
    with SessionLocal() as db:
        assert db.query(Message).filter_by(conversation_id=conversation_id, external_id="wamid.paused").count() == 1


def test_operator_message_consumes_no_ai_quota(client, workspace, monkeypatch):
    from app.db.session import SessionLocal
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.operator_delivery import OperatorDelivery
    from app.models.whatsapp_account import WhatsAppAccount
    from app.services import operator_delivery_service as module
    from app.services.whatsapp_gateway_service import whatsapp_gateway_service
    _, tenant_id, _, conversation_id = workspace
    generate_reply = _stub_model(monkeypatch)
    send_text = AsyncMock(return_value={"message_id": "wamid.operator"})
    monkeypatch.setattr(whatsapp_gateway_service, "send_text", send_text)
    with SessionLocal() as db:
        db.add(WhatsAppAccount(tenant_id=tenant_id, provider="meta", phone_number_id="pn-1", display_phone_number="+90555",
                               token_status="active", webhook_status="verified", is_active=True, is_verified=True))
        db.add(Message(conversation_id=conversation_id, sender="user", content="Soru", external_id="wamid.q"))
        db.commit()
    before = _snapshot(tenant_id)

    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        message_id = module.enqueue_operator_message(db, tenant_id, conversation, "Operator yaniti", uuid4())
        db.commit()
    asyncio.run(module.dispatch_operator_message(message_id))

    send_text.assert_awaited_once()
    generate_reply.assert_not_awaited()
    with SessionLocal() as db:
        assert db.get(OperatorDelivery, message_id).status == "sent"
        sent = db.get(Message, message_id)
        assert sent.sender == "operator" and sent.external_id == "wamid.operator"
        assert "reply_usage" not in (db.query(Message).filter_by(external_id="wamid.q").one().raw_payload or {})
    assert _snapshot(tenant_id) == before
