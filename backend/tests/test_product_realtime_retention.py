from __future__ import annotations

import re
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock

from app.core.time import utc_now_naive
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationSource, ConversationStatus
from app.models.data_retention import DataRetentionPolicy
from app.models.message import Message
from app.models.product_event import ProductEvent
from app.models.system_event import SystemEvent
from app.models.usage_log import UsageLog
from app.services.data_retention_service import DataRetentionService


def _tenant_session(client, email: str) -> tuple[str, str]:
    password = "Password123!"
    assert client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Product User",
            "terms_accepted": True,
            "privacy_notice_acknowledged": True,
            "terms_version": "2026-07-22",
            "privacy_version": "2026-07-22",
            "kvkk_notice_version": "2026-07-22",
        },
    ).status_code == 201
    code_message = client.post("/auth/email-verification/request", json={"email": email}).json()["message"]
    code = re.search(r"(\d{6})", code_message).group(1)
    assert client.post(
        "/auth/email-verification/confirm",
        json={"email": email, "code": code},
    ).status_code == 200
    token = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    tenant = client.post(
        "/tenants",
        json={"name": f"Tenant {email}"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    return token, tenant["id"]


def _headers(token: str, tenant_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}


def test_assistant_simulator_is_tenant_scoped_and_has_no_business_side_effects(client, monkeypatch):
    from app.db.session import SessionLocal
    from app.services.ai_service import ai_service

    token, tenant_id = _tenant_session(client, "simulator@example.com")
    headers = _headers(token, tenant_id)
    bot = client.post(
        "/bots",
        headers=headers,
        json={"name": "Test Assistant", "description": "Test business"},
    ).json()
    other_token, other_tenant_id = _tenant_session(client, "simulator-other@example.com")

    generate_reply = AsyncMock(return_value="Yarın saat 14.00 için uygunluğumuzu kontrol edebilirim.")
    monkeypatch.setattr(ai_service, "generate_reply", generate_reply)

    db = SessionLocal()
    try:
        before_conversations = db.query(Conversation).count()
        before_messages = db.query(Message).count()
    finally:
        db.close()

    response = client.post(
        f"/bots/{bot['id']}/simulate",
        headers=headers,
        json={
            "message": "Yarın randevu alabilir miyim?",
            "history": [{"role": "customer", "content": "Merhaba"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["safe_mode"] == "simulation"
    assert response.json()["history_count"] == 3
    assert "14.00" in response.json()["reply"]

    foreign = client.post(
        f"/bots/{bot['id']}/simulate",
        headers=_headers(other_token, other_tenant_id),
        json={"message": "Test", "history": []},
    )
    assert foreign.status_code == 404

    db = SessionLocal()
    try:
        assert db.query(Conversation).count() == before_conversations
        assert db.query(Message).count() == before_messages
    finally:
        db.close()


def test_product_events_strip_sensitive_properties_and_keep_tenant_isolation(client):
    from app.db.session import SessionLocal

    token, tenant_id = _tenant_session(client, "analytics-owner@example.com")
    headers = _headers(token, tenant_id)
    response = client.post(
        "/product-analytics/events",
        headers=headers,
        json={
            "events": [{
                "name": "form_error",
                "category": "error",
                "path": "/dashboard/onboarding?email=private@example.com",
                "session_id": "session_12345678",
                "properties": {
                    "status": 422,
                    "step": "business_profile",
                    "email": "private@example.com",
                    "message_content": "must not persist",
                    "access_token": "must not persist",
                    "value": "private free-form value",
                },
            }],
        },
    )
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] == 1

    summary = client.get("/product-analytics/friction", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["friction"][0]["name"] == "form_error"

    other_token, other_tenant_id = _tenant_session(client, "analytics-other@example.com")
    other_summary = client.get(
        "/product-analytics/friction",
        headers=_headers(other_token, other_tenant_id),
    )
    assert other_summary.status_code == 200
    assert other_summary.json()["total_events"] == 0

    db = SessionLocal()
    try:
        event = db.query(ProductEvent).filter(ProductEvent.tenant_id == uuid.UUID(tenant_id)).one()
        assert event.path == "/dashboard/onboarding"
        assert event.properties_json == {"status": 422, "step": "business_profile"}
    finally:
        db.close()


def test_retention_deletes_expired_records_and_respects_legal_hold(client):
    from app.db.session import SessionLocal

    token, tenant_id = _tenant_session(client, "retention@example.com")
    headers = _headers(token, tenant_id)
    bot_id = client.post("/bots", headers=headers, json={"name": "Retention Bot"}).json()["id"]
    old = utc_now_naive() - timedelta(days=800)

    db = SessionLocal()
    try:
        conversation = Conversation(
            bot_id=uuid.UUID(bot_id),
            external_user_id="905551110000",
            source=ConversationSource.WHATSAPP.value,
            status=ConversationStatus.CLOSED.value,
            created_at=old,
            updated_at=old,
        )
        db.add(conversation)
        db.flush()
        db.add(Message(
            conversation_id=conversation.id,
            sender="user",
            content="expired",
            raw_payload={"provider": "test", "private": "payload"},
            created_at=old,
        ))
        db.add(ProductEvent(
            tenant_id=uuid.UUID(tenant_id),
            name="page_view",
            category="navigation",
            path="/dashboard",
            session_id="session_retention_1",
            occurred_at=old,
        ))
        db.add(UsageLog(
            tenant_id=uuid.UUID(tenant_id),
            bot_id=uuid.UUID(bot_id),
            usage_type="message_received",
            created_at=old,
        ))
        db.add(SystemEvent(
            tenant_id=tenant_id,
            source="test",
            level="info",
            code="OLD_EVENT",
            message="old",
            created_at=old,
        ))
        db.commit()

        service = DataRetentionService(db)
        result = service.run(uuid.UUID(tenant_id), force=True)
        assert result["status"] == "completed"
        assert result["deleted"]["messages"] == 1
        assert result["deleted"]["closed_conversations"] == 1
        assert result["deleted"]["product_events"] == 1
        assert result["deleted"]["usage_logs"] == 1
        assert result["deleted"]["system_events"] == 1

        policy = service.get_or_create(uuid.UUID(tenant_id))
        policy.legal_hold = True
        policy.last_run_at = None
        db.add(ProductEvent(
            tenant_id=uuid.UUID(tenant_id),
            name="page_view",
            category="navigation",
            path="/dashboard",
            session_id="session_retention_2",
            occurred_at=old,
        ))
        db.commit()
        held = service.run(uuid.UUID(tenant_id), force=True)
        assert held["status"] == "legal_hold"
        assert db.query(ProductEvent).filter(ProductEvent.tenant_id == uuid.UUID(tenant_id)).count() == 1
    finally:
        db.close()


def test_message_commit_queues_tenant_realtime_event(client, monkeypatch):
    from app.db.session import SessionLocal
    from app.services import realtime_service

    token, tenant_id = _tenant_session(client, "realtime@example.com")
    bot_id = client.post(
        "/bots",
        headers=_headers(token, tenant_id),
        json={"name": "Realtime Bot"},
    ).json()["id"]
    published: list[tuple[str, dict]] = []
    monkeypatch.setattr(realtime_service, "_publish", lambda tenant, payload: published.append((tenant, payload)))

    db = SessionLocal()
    try:
        conversation = Conversation(
            bot_id=uuid.UUID(bot_id),
            external_user_id="905551112233",
            source=ConversationSource.WHATSAPP.value,
        )
        db.add(conversation)
        db.commit()
        published.clear()

        db.add(Message(conversation_id=conversation.id, sender="user", content="Merhaba"))
        db.commit()
        assert len(published) == 1
        assert published[0][0] == tenant_id
        assert published[0][1]["type"] == "message.created"
        assert published[0][1]["conversation_id"] == str(conversation.id)
        assert "content" not in published[0][1]
    finally:
        db.close()
