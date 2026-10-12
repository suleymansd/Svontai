"""Regression coverage for customer-facing failures found in the release audit."""

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import pytest

from tests.test_openwa_integration import _create_tenant, _headers


@pytest.fixture
def workspace(client):
    from app.db.session import SessionLocal
    from app.models.bot import Bot
    from app.models.conversation import Conversation
    from app.services.subscription_service import SubscriptionService

    token, tenant_id = _create_tenant(client)
    with SessionLocal() as db:
        if SubscriptionService(db).get_subscription(UUID(tenant_id)) is None:
            SubscriptionService(db).create_subscription(UUID(tenant_id), "free")
        bot = Bot(tenant_id=UUID(tenant_id), name="Audit", assistant_type="primary")
        db.add(bot)
        db.flush()
        conversation = Conversation(bot_id=bot.id, external_user_id="audit-customer", source="whatsapp")
        db.add(conversation)
        db.commit()
        return _headers(token, tenant_id), UUID(tenant_id), bot.id, conversation.id


def test_manual_booking_rejects_overlap_but_accepts_adjacent_slot(client, workspace):
    from app.core.time import utc_now_naive
    headers, *_ = workspace
    start = utc_now_naive() + timedelta(days=7)
    payload = {"customer_name": "Audit", "subject": "Slot", "starts_at": start.isoformat(), "duration_minutes": 60}
    first = client.post("/appointments", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    assert client.post("/appointments", json=payload, headers=headers).status_code == 409
    payload["starts_at"] = (start + timedelta(minutes=60)).isoformat()
    second = client.post("/appointments", json=payload, headers=headers)
    assert second.status_code == 201, second.text
    assert client.patch(f"/appointments/{second.json()['id']}", json={"starts_at": start.isoformat()}, headers=headers).status_code == 409
    assert client.patch(f"/appointments/{first.json()['id']}", json={"status": "cancelled"}, headers=headers).status_code == 200
    assert client.patch(f"/appointments/{second.json()['id']}", json={"starts_at": start.isoformat()}, headers=headers).status_code == 200


@pytest.mark.parametrize("field", ["customer_name", "subject", "starts_at", "duration_minutes", "status", "reminder_before_minutes"])
def test_appointment_update_rejects_null_required_fields(client, workspace, field):
    headers, *_ = workspace
    assert client.patch(f"/appointments/{uuid4()}", json={field: None}, headers=headers).status_code == 422


def test_message_window_returns_latest_and_bounds_page_size(client, workspace):
    from app.core.time import utc_now_naive
    from app.db.session import SessionLocal
    from app.models.message import Message
    headers, _, _, conversation_id = workspace
    now = utc_now_naive()
    with SessionLocal() as db:
        db.add_all([Message(conversation_id=conversation_id, sender="user", content=f"audit-{i}", created_at=now + timedelta(seconds=i)) for i in range(105)])
        db.commit()
    url = f"/operator/conversation/{conversation_id}/messages"
    messages = client.get(url + "?limit=100", headers=headers).json()
    assert len(messages) == 100
    assert messages[0]["content"] == "audit-5"
    assert messages[-1]["content"] == "audit-104"
    older = client.get(url + "?limit=100&skip=100", headers=headers).json()
    assert older[-1]["content"] == "audit-4"
    assert client.get(url + "?limit=999999", headers=headers).status_code == 422
    assert client.get(url + "?skip=-1", headers=headers).status_code == 422


def test_conversation_list_does_not_load_entire_message_relationship(client, workspace):
    from sqlalchemy import inspect
    from sqlalchemy.orm.attributes import NO_VALUE
    from app.api.routers.conversations import list_all_conversations
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.conversation import Conversation
    from app.models.tenant import Tenant
    _, tenant_id, _, conversation_id = workspace
    with SessionLocal() as db:
        db.add_all([Message(conversation_id=conversation_id, sender="user", content="Large history " * 1000) for _ in range(100)])
        db.commit()
        conversation = db.get(Conversation, conversation_id)
        rows = asyncio.run(list_all_conversations(skip=0, limit=50, current_tenant=db.get(Tenant, tenant_id), db=db, _=None))
        assert len(rows) == 1
        assert rows[0]["last_message"].startswith("Large history")
        assert len(rows[0]["last_message"]) == 500
        assert "messages" not in rows[0]
        assert inspect(conversation).attrs.messages.loaded_value is NO_VALUE


def test_old_worker_cannot_complete_or_fail_new_owners_lease(client):
    from app.core.time import utc_now
    from app.db.session import SessionLocal
    from app.models.webhook_inbox import WebhookInboxEvent
    from app.services.webhook_inbox_service import WebhookInboxService
    with SessionLocal() as db:
        row = WebhookInboxEvent(provider="openwa", event_type="message.received", deduplication_key=uuid4().hex, payload_json={"test": True}, status="processing", lock_owner="new-worker", locked_until=utc_now() + timedelta(minutes=3))
        db.add(row)
        db.commit()
        old = WebhookInboxService(db, owner="old-worker")
        old.mark_processed(row.id)
        old.mark_failed(row.id, RuntimeError("stale"))
        db.refresh(row)
        assert row.status == "processing"
        assert row.lock_owner == "new-worker"
        assert row.payload_json == {"test": True}


def test_usage_increment_preserves_concurrent_stale_update(client, workspace, monkeypatch):
    from app.db.session import SessionLocal
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, *_ = workspace
    with SessionLocal() as first, SessionLocal() as second:
        a, b = UsageCounterService(first), UsageCounterService(second)
        a.get_or_create(tenant_id)
        stale = b.get_or_create(tenant_id)
        a.increment_message_count(tenant_id)
        monkeypatch.setattr(b, "get_or_create", lambda *args, **kwargs: stale)
        b.increment_message_count(tenant_id)
        second.refresh(stale)
        assert stale.message_count == 2


def test_bot_creation_enforces_free_plan_capacity(client, workspace):
    headers, *_ = workspace
    response = client.post("/bots", headers=headers, json={"name": "Beyond plan"})
    assert response.status_code == 403, response.text


def test_reply_delivery_recovers_generation_but_never_resends_ambiguous_send(client, workspace):
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.services.reply_delivery_guard import ReplyDeliveryGuard, ReplyDeliveryUncertain
    _, _, _, conversation_id = workspace
    with SessionLocal() as db:
        db.add(Message(conversation_id=conversation_id, sender="user", content="Hello", external_id="retry"))
        db.commit()
    first = ReplyDeliveryGuard(conversation_id, "retry")
    assert first.claim()
    with pytest.raises(RuntimeError, match="already claimed"):
        ReplyDeliveryGuard(conversation_id, "retry").claim()
    first.failed()
    second = ReplyDeliveryGuard(conversation_id, "retry")
    assert second.claim()
    with pytest.raises(RuntimeError, match="ownership lost"):
        first.set_status("dispatching")
    second.set_status("dispatching")
    second.failed()
    with pytest.raises(ReplyDeliveryUncertain):
        ReplyDeliveryGuard(conversation_id, "retry").claim()


def test_persisted_inbound_resumes_unfinished_reply(client, workspace, monkeypatch):
    from app.api.routers import whatsapp_webhook as webhook
    from app.db.session import SessionLocal
    from app.models.message import Message
    _, tenant_id, _, conversation_id = workspace
    reply = AsyncMock()
    monkeypatch.setattr(webhook, "process_whatsapp_reply_in_background", reply)
    with SessionLocal() as db:
        db.add(Message(conversation_id=conversation_id, sender="user", content="Hello", external_id="crash-window"))
        db.commit()
        asyncio.run(webhook.handle_incoming_message(
            tenant_id_str=str(tenant_id), account_phone_number_id="audit-session",
            account_display_phone_number="audit-business", access_token_encrypted=None,
            from_number="audit-customer", message_content="Hello", message_type="text",
            message_id="crash-window", contact_name="Audit", db=db,
            contact_name_source="profile", correlation_id=str(uuid4()),
        ))
        assert db.query(Message).filter_by(external_id="crash-window").count() == 1
    reply.assert_awaited_once()


def test_ai_outage_is_retryable_and_not_marked_delivered(client, workspace, monkeypatch):
    from app.api.routers import whatsapp_webhook as webhook
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.whatsapp_account import WhatsAppAccount
    _, tenant_id, bot_id, conversation_id = workspace
    with SessionLocal() as db:
        db.add(WhatsAppAccount(tenant_id=tenant_id, provider="openwa", provider_session_id="audit-session", is_active=True))
        db.add(Message(conversation_id=conversation_id, sender="user", content="Hello", external_id="provider-outage"))
        db.commit()
    monkeypatch.setattr(webhook.ai_service, "generate_reply", AsyncMock(side_effect=RuntimeError("AI outage")))
    monkeypatch.setattr(webhook.AssistantProfileService, "build_runtime_context", lambda *args: "audit")
    with pytest.raises(RuntimeError, match="AI outage"):
        asyncio.run(webhook.process_whatsapp_reply_in_background(
            tenant_id=tenant_id, bot_id=bot_id, conversation_id=conversation_id,
            account_phone_number_id="audit-session", provider="openwa", from_number="audit-customer",
            to_number="audit-business", message_content="Hello", message_id="provider-outage",
            timestamp="2026-10-12T09:00:00", correlation_id=str(uuid4()), contact_name="Audit",
            raw_payload=None, use_n8n=False, n8n_workflow_id=None,
        ))
    with SessionLocal() as db:
        incoming = db.query(Message).filter_by(external_id="provider-outage").one()
        assert incoming.raw_payload["reply_delivery"]["status"] == "retrying"
        assert db.query(Message).filter_by(conversation_id=conversation_id, sender="bot").count() == 0
        from app.services.subscription_service import SubscriptionService
        assert SubscriptionService(db).get_subscription(tenant_id).messages_used_this_month == 0


def test_reply_metering_is_transactional_and_idempotent_per_inbound(client, workspace):
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.automation import AutomationRun
    from app.services.reply_usage_service import record_delivered_reply
    from app.services.subscription_service import SubscriptionService
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, _, conversation_id = workspace
    with SessionLocal() as db:
        db.add(Message(conversation_id=conversation_id, sender="user", content="Hello", external_id="billable-inbound"))
        run = AutomationRun(tenant_id=str(tenant_id), channel="whatsapp", message_id="billable-inbound", from_number="audit-customer", to_number="audit-business")
        db.add(run)
        db.commit()
        reply = Message(conversation_id=conversation_id, sender="bot", content="Reply", reply_to_external_id="billable-inbound")
        db.add(reply)
        assert record_delivered_reply(db, tenant_id, reply)
        assert not record_delivered_reply(db, tenant_id, reply)
        db.rollback()
        assert SubscriptionService(db).get_subscription(tenant_id).messages_used_this_month == 0
        assert UsageCounterService(db).get_or_create(tenant_id).message_count == 0

        delivered = Message(conversation_id=conversation_id, sender="bot", content="Reply", reply_to_external_id="billable-inbound")
        db.add(delivered)
        assert record_delivered_reply(db, tenant_id, delivered)
        db.commit()
        media = Message(conversation_id=conversation_id, sender="bot", content="[image]", automation_run_id=str(run.id))
        db.add(media)
        assert not record_delivered_reply(db, tenant_id, media)
        db.commit()
        assert SubscriptionService(db).get_subscription(tenant_id).messages_used_this_month == 1
        assert UsageCounterService(db).get_or_create(tenant_id).message_count == 1


def test_excluded_inbound_does_not_consume_reply_quota(client, workspace):
    from app.api.routers.whatsapp_webhook import handle_incoming_message
    from app.db.session import SessionLocal
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.services.subscription_service import SubscriptionService
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, _, conversation_id = workspace
    with SessionLocal() as db:
        db.get(Conversation, conversation_id).ai_reply_enabled = False
        db.commit()
        asyncio.run(handle_incoming_message(
            tenant_id_str=str(tenant_id), account_phone_number_id="audit-session",
            account_display_phone_number="audit-business", access_token_encrypted=None,
            from_number="audit-customer", message_content="Hello", message_type="text",
            message_id="excluded-unbilled", contact_name="Audit", db=db,
            contact_name_source="profile", correlation_id=str(uuid4()),
        ))
        assert db.query(Message).filter_by(external_id="excluded-unbilled").count() == 1
        assert SubscriptionService(db).get_subscription(tenant_id).messages_used_this_month == 0
        assert UsageCounterService(db).get_or_create(tenant_id).message_count == 0


def test_widget_provider_failure_returns_retryable_error_without_billing(client, workspace, monkeypatch):
    from app.api.routers import public
    from app.db.session import SessionLocal
    from app.models.bot import Bot
    from app.models.message import Message
    from app.services.subscription_service import SubscriptionService
    _, tenant_id, bot_id, _ = workspace
    with SessionLocal() as db:
        public_key = db.get(Bot, bot_id).public_key
    init = client.post("/public/chat/init", json={"bot_public_key": public_key})
    assert init.status_code == 200, init.text
    monkeypatch.setattr(public.ai_service, "generate_reply", AsyncMock(side_effect=RuntimeError("Provider unavailable")))
    monkeypatch.setattr(public.AssistantProfileService, "build_runtime_context", lambda *args: "audit")
    result = client.post("/public/chat/send", json={
        "conversation_id": init.json()["conversation_id"], "session_token": init.json()["session_token"], "message": "Hello",
    })
    assert result.status_code == 503, result.text
    with SessionLocal() as db:
        assert SubscriptionService(db).get_subscription(tenant_id).messages_used_this_month == 0
        assert db.query(Message).filter_by(conversation_id=UUID(init.json()["conversation_id"]), sender="bot").count() == 0


def test_calendar_reconciles_lost_create_response_without_duplicate(client, workspace, monkeypatch):
    import httpx
    from app.core.time import utc_now_naive
    from app.db.session import SessionLocal
    from app.models.appointment import Appointment
    from app.services.google_calendar_service import GoogleCalendarService
    _, tenant_id, *_ = workspace
    with SessionLocal() as db:
        row = Appointment(tenant_id=tenant_id, customer_name="Test", subject="Test", starts_at=utc_now_naive() + timedelta(days=2))
        db.add(row)
        db.commit()
        service = GoogleCalendarService(db)
        monkeypatch.setattr(service, "_tenant_access_token", lambda _: "test-token")
        attempted_ids = []
        def post(url, **kwargs):
            attempted_ids.append(kwargs["json"]["id"])
            if len(attempted_ids) == 1:
                raise httpx.ReadTimeout("Response lost after acceptance")
            return httpx.Response(409, json={"error": {"message": "Already exists"}})
        monkeypatch.setattr("app.services.google_calendar_service.httpx.post", post)
        patches = []
        def patch(url, **kwargs):
            patches.append(url)
            return httpx.Response(200, json={"id": attempted_ids[0]})
        monkeypatch.setattr("app.services.google_calendar_service.httpx.patch", patch)
        with pytest.raises(httpx.ReadTimeout):
            service.sync_appointment(row)
        assert service.sync_appointment(row) == "synced"
        assert attempted_ids[0] == attempted_ids[1] == row.calendar_event_id
        assert patches[0].endswith(row.calendar_event_id)


def test_retention_respects_legal_hold_and_leaves_pending_work(client, workspace):
    from app.core.time import utc_now
    from app.db.session import SessionLocal
    from app.models.webhook_inbox import WebhookInboxEvent
    from app.services.data_retention_service import DataRetentionService
    _, tenant_id, *_ = workspace
    with SessionLocal() as db:
        for status in ["processed", "dead_letter", "pending"]:
            db.add(WebhookInboxEvent(tenant_id=tenant_id, provider="openwa", event_type="message.received", deduplication_key=uuid4().hex, payload_json={"customer": "private"}, status=status, received_at=utc_now() - timedelta(days=800)))
        db.commit()
        service = DataRetentionService(db)
        policy = service.get_or_create(tenant_id)
        policy.enabled = True
        policy.legal_hold = True
        db.commit()
        assert service.run(tenant_id, force=True)["status"] == "legal_hold"
        assert db.query(WebhookInboxEvent).count() == 3
        policy.legal_hold = False
        db.commit()
        assert service.run(tenant_id, force=True)["deleted"]["terminal_webhooks"] == 2
        assert db.query(WebhookInboxEvent).one().status == "pending"


def test_postgres_parallel_bookings_and_metering(client, workspace):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException
    from app.core.time import utc_now_naive
    from app.db.session import SessionLocal
    from app.models.appointment import Appointment
    from app.services.appointment_booking_guard import lock_booking_calendar, require_available_interval
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, *_ = workspace
    with SessionLocal() as db:
        if db.get_bind().dialect.name != "postgresql":
            pytest.skip("Requires the PostgreSQL CI lane")
    start = utc_now_naive() + timedelta(days=7)
    barrier = Barrier(2)
    def book():
        with SessionLocal() as db:
            barrier.wait(timeout=5)
            try:
                lock_booking_calendar(db, tenant_id)
                require_available_interval(db, tenant_id, start, 60)
                db.add(Appointment(tenant_id=tenant_id, customer_name="Test", subject="Concurrent", starts_at=start))
                db.commit()
                return 201
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: book(), range(2))) == [201, 409]
    def meter():
        with SessionLocal() as db:
            barrier.wait(timeout=5)
            for _ in range(10):
                UsageCounterService(db).increment_message_count(tenant_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: meter(), range(2)))
    with SessionLocal() as db:
        assert UsageCounterService(db).get_or_create(tenant_id).message_count == 20
