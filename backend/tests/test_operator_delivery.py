import asyncio
from datetime import timedelta
from uuid import uuid4
from unittest.mock import AsyncMock

from tests.test_reliability_regressions import workspace  # noqa: F401


def connect(tenant_id):
    from app.db.session import SessionLocal
    from app.models.whatsapp_account import WhatsAppAccount
    with SessionLocal() as db:
        db.add(WhatsAppAccount(tenant_id=tenant_id, provider="openwa", provider_session_id="test-session", is_active=True))
        db.commit()


def test_operator_send_is_idempotent_and_rejects_key_reuse(client, workspace, monkeypatch):
    from app.services.whatsapp_gateway_service import whatsapp_gateway_service
    headers, tenant_id, _, conversation_id = workspace
    connect(tenant_id)
    send = AsyncMock(return_value={"message_id": "provider-id"})
    monkeypatch.setattr(whatsapp_gateway_service, "send_text", send)
    data = {"conversation_id": str(conversation_id), "content": "Test", "request_id": str(uuid4())}
    first = client.post("/operator/send-message", json=data, headers=headers)
    assert first.status_code == 200, first.text
    second = client.post("/operator/send-message", json=data, headers=headers)
    assert second.json()["message_id"] == first.json()["message_id"]
    assert second.json()["delivery_status"] == "sent"
    assert send.await_count == 1
    assert client.post("/operator/send-message", json={**data, "content": "Different"}, headers=headers).status_code == 409


def test_uncertain_delivery_requires_explicit_reconciliation_not_retry(client, workspace, monkeypatch):
    from app.services.whatsapp_gateway_service import whatsapp_gateway_service
    from app.db.session import SessionLocal
    from app.models.onboarding import AuditLog
    from tests.test_openwa_integration import _create_tenant, _headers
    headers, tenant_id, _, conversation_id = workspace
    connect(tenant_id)
    send = AsyncMock(side_effect=TimeoutError("private provider credential"))
    monkeypatch.setattr(whatsapp_gateway_service, "send_text", send)
    data = {"conversation_id": str(conversation_id), "content": "Test", "request_id": str(uuid4())}
    result = client.post("/operator/send-message", json=data, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["delivery_status"] == "uncertain"
    assert "credential" not in result.text
    client.post("/operator/send-message", json=data, headers=headers)
    assert send.await_count == 1
    message_id = result.json()["message_id"]
    url = f"/operator/deliveries/{message_id}/resolve"
    assert client.post(url, json={"outcome": "not_sent"}, headers=headers).status_code == 422
    other_token, other_tenant = _create_tenant(client, email="delivery-other@example.com")
    assert client.post(url, json={"outcome": "sent", "checked_whatsapp": True}, headers=_headers(other_token, other_tenant)).status_code == 404
    resolved = client.post(url, json={"outcome": "sent", "checked_whatsapp": True}, headers=headers)
    assert resolved.json()["delivered"] is True
    assert send.await_count == 1
    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action="operator.delivery_resolved", resource_id=message_id).count() == 1


def test_worker_recovers_queued_but_never_retries_stale_dispatch(client, workspace, monkeypatch):
    from app.core.time import utc_now_naive
    from app.db.session import SessionLocal
    from app.models.conversation import Conversation
    from app.models.operator_delivery import OperatorDelivery
    from app.services.operator_delivery_service import enqueue_operator_message, dispatch_operator_message, mark_stale_deliveries
    from app.services.whatsapp_gateway_service import whatsapp_gateway_service
    _, tenant_id, _, conversation_id = workspace
    connect(tenant_id)
    send = AsyncMock(return_value={"message_id": "worker-recovered"})
    monkeypatch.setattr(whatsapp_gateway_service, "send_text", send)
    with SessionLocal() as db:
        message_id = enqueue_operator_message(db, tenant_id, db.get(Conversation, conversation_id), "Queued", uuid4())
        db.commit()
    asyncio.run(dispatch_operator_message(message_id))
    assert send.await_count == 1
    with SessionLocal() as db:
        row = db.get(OperatorDelivery, message_id)
        assert row.status == "sent"
        row.status = "dispatching"
        row.updated_at = utc_now_naive() - timedelta(minutes=6)
        db.commit()
        assert mark_stale_deliveries(db) == 1
    asyncio.run(dispatch_operator_message(message_id))
    assert send.await_count == 1


def test_ai_resolution_uses_dispatch_age_and_meters_once(client, workspace):
    from app.core.time import utc_now_naive
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.reply_reservation import ReplyReservation
    from app.models.subscription import TenantSubscription
    from app.services.reply_quota_service import reserve_reply
    from tests.test_reply_quota import sources
    headers, tenant_id, _, conversation_id = workspace
    message_id, _ = sources(tenant_id, conversation_id)
    with SessionLocal() as db:
        message = db.get(Message, message_id)
        message.created_at = utc_now_naive() - timedelta(hours=1)
        message.raw_payload = {"reply_delivery": {"status": "dispatching", "updated_at": utc_now_naive().isoformat(),
                                                  "prepared_reply": {"text": "Randevunuz oluşturuldu."}}}
        assert reserve_reply(db, tenant_id, message_id)[0]
        db.commit()
    url = f"/operator/deliveries/{message_id}/resolve"
    body = {"outcome": "sent", "checked_whatsapp": True, "kind": "ai"}
    assert client.post(url, json=body, headers=headers).status_code == 409
    assert client.get(f"/operator/deliveries?conversation_id={conversation_id}", headers=headers).json() == []
    with SessionLocal() as db:
        message = db.get(Message, message_id)
        state = message.raw_payload["reply_delivery"]
        message.raw_payload = {"reply_delivery": {**state, "updated_at": (utc_now_naive() - timedelta(minutes=6)).isoformat()}}
        db.commit()
    pending = client.get(f"/operator/deliveries?conversation_id={conversation_id}", headers=headers).json()
    assert pending[0]["content"] == "Randevunuz oluşturuldu."
    assert client.post(url, json=body, headers=headers).status_code == 200
    assert client.post(url, json=body, headers=headers).status_code == 409
    with SessionLocal() as db:
        assert db.query(TenantSubscription).filter_by(tenant_id=tenant_id).one().messages_used_this_month == 1
        assert db.get(ReplyReservation, message_id).state == "consumed"
        assert db.query(Message).filter_by(conversation_id=conversation_id, sender="bot").count() == 1


def test_ai_not_sent_resolution_releases_quota_and_pauses_conversation(client, workspace):
    from app.core.time import utc_now_naive
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.conversation import Conversation
    from app.models.reply_reservation import ReplyReservation
    from app.services.reply_quota_service import reserve_reply
    from tests.test_reply_quota import sources
    from tests.test_openwa_integration import _create_tenant, _headers
    headers, tenant_id, _, conversation_id = workspace
    message_id, _ = sources(tenant_id, conversation_id)
    with SessionLocal() as db:
        message = db.get(Message, message_id)
        message.raw_payload = {"reply_delivery": {"status": "uncertain", "updated_at": (utc_now_naive() - timedelta(minutes=6)).isoformat()}}
        assert reserve_reply(db, tenant_id, message_id)[0]
        db.commit()
    url = f"/operator/deliveries/{message_id}/resolve"
    body = {"outcome": "not_sent", "checked_whatsapp": True, "kind": "ai"}
    other_token, other_tenant = _create_tenant(client, email="ai-delivery-other@example.com")
    assert client.post(url, json=body, headers=_headers(other_token, other_tenant)).status_code == 404
    assert client.post(url, json=body, headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.get(ReplyReservation, message_id).state == "released"
        assert db.get(Conversation, conversation_id).is_ai_paused
        assert db.query(Message).filter_by(conversation_id=conversation_id, sender="bot").count() == 0


def test_ai_history_excludes_unconfirmed_operator_intents(client, workspace):
    from app.db.session import SessionLocal
    from app.models.conversation import Conversation
    from app.models.operator_delivery import OperatorDelivery
    from app.services.conversation_history import recent_messages
    from app.services.operator_delivery_service import enqueue_operator_message
    _, tenant_id, _, conversation_id = workspace
    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        message_id = enqueue_operator_message(db, tenant_id, conversation, "Not yet delivered", uuid4())
        db.commit()
        assert all(item.id != message_id for item in recent_messages(conversation, 50))
        db.get(OperatorDelivery, message_id).status = "sent"
        db.commit()
        assert any(item.id == message_id for item in recent_messages(conversation, 50))
