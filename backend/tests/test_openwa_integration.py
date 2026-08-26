import asyncio
import hashlib
import hmac
import json
import re
from unittest.mock import AsyncMock
from uuid import UUID


def _extract_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match
    return match.group(1)


def _create_tenant(client) -> tuple[str, str]:
    email = "openwa@example.com"
    password = "Password123!"
    assert client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "OpenWA User", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-08-04", "privacy_version": "2026-08-04", "kvkk_notice_version": "2026-08-04"},
    ).status_code == 201
    code_response = client.post("/auth/email-verification/request", json={"email": email})
    code = _extract_code(code_response.json()["message"])
    assert client.post(
        "/auth/email-verification/confirm",
        json={"email": email, "code": code},
    ).status_code == 200
    login = client.post("/auth/login", json={"email": email, "password": password})
    token = login.json()["access_token"]
    tenant = client.post(
        "/tenants",
        json={"name": "OpenWA Tenant"},
        headers={"Authorization": f"Bearer {token}"},
    )
    tenant_id = tenant.json()["id"]
    return token, tenant_id


def _headers(token: str, tenant_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }


def test_openwa_qr_onboarding_is_tenant_scoped(client, monkeypatch):
    from app.core.config import settings
    from app.services.openwa_client import openwa_client

    token, tenant_id = _create_tenant(client)
    headers = _headers(token, tenant_id)

    monkeypatch.setattr(settings, "OPENWA_ENABLED", True)
    monkeypatch.setattr(settings, "OPENWA_WEBHOOK_SECRET", "test-openwa-secret")
    monkeypatch.setattr(openwa_client, "base_url", "https://openwa.test")
    monkeypatch.setattr(openwa_client, "api_key", "test-api-key")
    monkeypatch.setattr(
        openwa_client,
        "create_or_get_session",
        AsyncMock(return_value={"id": "82d1023f-998b-4ada-bf1c-a1e192e933c6", "status": "created"}),
    )
    monkeypatch.setattr(
        openwa_client,
        "ensure_webhook",
        AsyncMock(return_value={"id": "7ae34565-e24c-4a50-9378-8b76f404ec77"}),
    )
    monkeypatch.setattr(
        openwa_client,
        "start_session",
        AsyncMock(return_value={"id": "82d1023f-998b-4ada-bf1c-a1e192e933c6", "status": "qr_ready"}),
    )
    monkeypatch.setattr(
        openwa_client,
        "get_session",
        AsyncMock(return_value={"id": "82d1023f-998b-4ada-bf1c-a1e192e933c6", "status": "qr_ready"}),
    )
    monkeypatch.setattr(
        openwa_client,
        "get_qr",
        AsyncMock(return_value={"status": "qr_ready", "qrCode": "data:image/png;base64,dGVzdA=="}),
    )
    delete_session = AsyncMock(return_value=None)
    monkeypatch.setattr(openwa_client, "delete_session", delete_session)

    without_consent = client.post(
        "/api/onboarding/whatsapp/openwa/start",
        json={"accepted_unofficial_risk": False},
        headers=headers,
    )
    assert without_consent.status_code == 400

    start = client.post(
        "/api/onboarding/whatsapp/openwa/start",
        json={"accepted_unofficial_risk": True},
        headers=headers,
    )
    assert start.status_code == 200, start.text
    assert start.json()["provider"] == "openwa"
    assert start.json()["status"] == "qr_ready"

    from app.db import session as session_module
    from app.models.onboarding import AuditLog

    db = session_module.SessionLocal()
    try:
        consent = db.query(AuditLog).filter(
            AuditLog.tenant_id == UUID(tenant_id),
            AuditLog.action == "legal.openwa_risk.accepted",
        ).one()
        assert consent.payload_json["notice_version"] == "2026-07-22"
        assert consent.payload_json["accepted"] is True
    finally:
        db.close()

    qr = client.get("/api/onboarding/whatsapp/openwa/qr", headers=headers)
    assert qr.status_code == 200, qr.text
    assert qr.json()["qr_code"].startswith("data:image/png;base64,")

    reconnect = client.post("/api/onboarding/whatsapp/openwa/reconnect", headers=headers)
    assert reconnect.status_code == 200, reconnect.text
    assert reconnect.json()["status"] == "qr_ready"
    assert reconnect.json()["qr_code"].startswith("data:image/png;base64,")

    fresh_qr = client.post("/api/onboarding/whatsapp/openwa/qr/refresh", headers=headers)
    assert fresh_qr.status_code == 200, fresh_qr.text
    assert fresh_qr.json()["qr_code"].startswith("data:image/png;base64,")
    delete_session.assert_awaited_once_with("82d1023f-998b-4ada-bf1c-a1e192e933c6")

    status = client.get("/api/onboarding/whatsapp/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["provider"] == "openwa"
    assert status.json()["openwa_enabled"] is True

    from app.db.session import SessionLocal
    from app.models.whatsapp_account import WhatsAppAccount

    db = SessionLocal()
    try:
        account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == UUID(tenant_id)
        ).one()
        assert account.provider_session_id == "82d1023f-998b-4ada-bf1c-a1e192e933c6"
        assert account.access_token_encrypted is None
        assert account.is_active is False
        assert account.token_status == "pending"
        assert account.provider_metadata_json["health_status"] == "action_required"
        assert account.provider_metadata_json["risk_accepted"] is True
    finally:
        db.close()


def test_openwa_signed_message_is_processed_once(client, monkeypatch):
    from app.api.routers import whatsapp_webhook
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.models.automation import AutomationRunStatus, TenantAutomationSettings
    from app.models.bot import Bot
    from app.models.message import Message
    from app.models.whatsapp_account import WhatsAppAccount
    from app.services.ai_service import ai_service
    from app.services.openwa_client import openwa_client

    token, tenant_id = _create_tenant(client)
    tenant_headers = _headers(token, tenant_id)
    monkeypatch.setattr(settings, "OPENWA_WEBHOOK_SECRET", "test-openwa-secret")
    monkeypatch.setattr(settings, "USE_N8N", True)
    generate_reply = AsyncMock(return_value="Merhaba, size nasıl yardımcı olabilirim?")
    send_text = AsyncMock(return_value={"messageId": "openwa-reply-1"})
    get_contact = AsyncMock(return_value={
        "id": "905559998877@c.us",
        "name": "Rehberdeki Müşteri",
        "pushName": "WhatsApp Profili",
        "number": "905559998877",
        "isMyContact": True,
    })
    n8n_trigger = AsyncMock(return_value=AutomationRunStatus.FAILED.value)
    monkeypatch.setattr(ai_service, "generate_reply", generate_reply)
    monkeypatch.setattr(openwa_client, "send_text", send_text)
    monkeypatch.setattr(openwa_client, "get_contact", get_contact)
    monkeypatch.setattr(whatsapp_webhook, "trigger_n8n_in_background", n8n_trigger)

    session_id = "82d1023f-998b-4ada-bf1c-a1e192e933c6"
    db = SessionLocal()
    try:
        db.add(Bot(
            tenant_id=UUID(tenant_id),
            name="OpenWA Bot",
            description="Test",
            welcome_message="Merhaba",
            language="tr",
            primary_color="#2563EB",
            widget_position="right",
            is_active=True,
        ))
        db.add(WhatsAppAccount(
            tenant_id=UUID(tenant_id),
            provider="openwa",
            provider_session_id=session_id,
            display_phone_number="+905551112233",
            token_status="active",
            webhook_status="verified",
            is_active=True,
            is_verified=True,
        ))
        db.add(TenantAutomationSettings(
            tenant_id=tenant_id,
            use_n8n=True,
            whatsapp_workflow_id="svontai-whatsapp-v2",
        ))
        db.commit()
    finally:
        db.close()

    payload = {
        "event": "message.received",
        "timestamp": "2026-07-16T10:00:00Z",
        "sessionId": session_id,
        "idempotencyKey": "evt-message-1",
        "deliveryId": "delivery-1",
        "data": {
            "id": "wa-message-1",
            "from": "905559998877@c.us",
            "to": "905551112233@c.us",
            "chatId": "905559998877@c.us",
            "body": "Randevu almak istiyorum",
            "type": "text",
            "timestamp": 1784196000,
            "fromMe": False,
            "isGroup": False,
            "contact": {"pushName": "WhatsApp Profili"},
        },
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    derived_secret = hmac.new(
        b"test-openwa-secret",
        f"openwa-webhook:{session_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    signature = hmac.new(derived_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-OpenWA-Signature": f"sha256={signature}",
    }

    first = client.post("/whatsapp/openwa/webhook", content=raw_body, headers=headers)
    second = client.post("/whatsapp/openwa/webhook", content=raw_body, headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == "accepted"
    assert second.json()["status"] == "duplicate"

    from app.models.webhook_inbox import WebhookInboxEvent
    from app.services.webhook_inbox_service import WebhookInboxService

    db = SessionLocal()
    try:
        event_ids = WebhookInboxService(db, owner="test-worker").claim_batch()
    finally:
        db.close()
    assert len(event_ids) == 1

    db = SessionLocal()
    try:
        asyncio.run(WebhookInboxService(db, owner="test-worker").process_claimed(event_ids[0]))
        inbox_event = db.query(WebhookInboxEvent).filter(WebhookInboxEvent.id == event_ids[0]).one()
        assert inbox_event.status == "processed"
        assert inbox_event.payload_json == {}
    finally:
        db.close()

    db = SessionLocal()
    try:
        messages = db.query(Message).filter(Message.external_id == "wa-message-1").all()
        assert len(messages) == 1
        assert messages[0].content == "Randevu almak istiyorum"
        assert messages[0].raw_payload["meta"]["provider"] == "openwa"
        bot_messages = db.query(Message).filter(Message.external_id == "openwa-reply-1").all()
        assert len(bot_messages) == 1
        assert bot_messages[0].content == "Merhaba, size nasıl yardımcı olabilirim?"
    finally:
        db.close()

    generate_reply.assert_awaited_once()
    n8n_trigger.assert_awaited_once()
    get_contact.assert_awaited_once_with(session_id, "905559998877@c.us")
    send_text.assert_awaited_once_with(
        session_id,
        "905559998877",
        "Merhaba, size nasıl yardımcı olabilirim?",
    )

    conversations = client.get("/conversations", headers=tenant_headers)
    assert conversations.status_code == 200, conversations.text
    assert len(conversations.json()) == 1
    conversation = conversations.json()[0]
    assert conversation["customer_name"] == "Rehberdeki Müşteri"
    assert conversation["customer_phone"] == "905559998877"
    assert conversation["last_message"] == "Merhaba, size nasıl yardımcı olabilirim?"

    conversation_detail = client.get(
        f"/conversations/{conversation['id']}",
        headers=tenant_headers,
    )
    assert conversation_detail.status_code == 200, conversation_detail.text
    assert [item["sender"] for item in conversation_detail.json()["messages"]] == ["user", "bot"]


def test_openwa_gateway_routes_outbound_to_tenant_session(client, monkeypatch):
    from app.models.whatsapp_account import WhatsAppAccount
    from app.services.openwa_client import openwa_client
    from app.services.whatsapp_gateway_service import whatsapp_gateway_service

    _ = client
    send_text = AsyncMock(return_value={"messageId": "outgoing-1", "timestamp": 1784196000})
    monkeypatch.setattr(openwa_client, "send_text", send_text)
    account = WhatsAppAccount(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        provider="openwa",
        provider_session_id="82d1023f-998b-4ada-bf1c-a1e192e933c6",
        token_status="active",
        webhook_status="verified",
        is_active=True,
        is_verified=True,
    )

    import asyncio

    result = asyncio.run(
        whatsapp_gateway_service.send_text(
            account,
            to="+90 555 999 88 77",
            text="Merhaba",
        )
    )
    assert result["message_id"] == "outgoing-1"
    send_text.assert_awaited_once_with(
        "82d1023f-998b-4ada-bf1c-a1e192e933c6",
        "+90 555 999 88 77",
        "Merhaba",
    )


def test_openwa_webhook_secret_is_scoped_per_session(client, monkeypatch):
    from app.core.config import settings
    from app.services.openwa_client import OpenWAClient

    _ = client
    monkeypatch.setattr(settings, "OPENWA_WEBHOOK_SECRET", "master-secret")
    first = OpenWAClient.webhook_secret("session-a")
    second = OpenWAClient.webhook_secret("session-b")
    assert first
    assert second
    assert first != second


def test_openwa_qr_state_requires_user_action_instead_of_reconnect():
    from datetime import datetime, timedelta

    from app.worker import (
        _openwa_qr_is_ready,
        _openwa_reconnect_is_due,
        _openwa_recovery_action,
    )

    assert _openwa_recovery_action(
        status="qr_ready",
        connected=False,
        was_active=True,
        previous_failures=2,
        previous_health="disconnected",
    ) == "qr_required"
    assert _openwa_recovery_action(
        status="disconnected",
        connected=False,
        was_active=True,
        previous_failures=0,
        previous_health="connected",
    ) == "reconnect"
    assert _openwa_recovery_action(
        status="ready",
        connected=True,
        was_active=True,
        previous_failures=0,
        previous_health="connected",
    ) == "none"
    assert _openwa_recovery_action(
        status="initializing",
        connected=False,
        was_active=True,
        previous_failures=1,
        previous_health="disconnected",
    ) == "wait"
    assert _openwa_qr_is_ready({"status": "qr_ready", "qrCode": "data:image/png;base64,dGVzdA=="})
    assert not _openwa_qr_is_ready({"status": "initializing", "qrCode": None})

    now = datetime(2026, 7, 21, 12, 0, 0)
    assert not _openwa_reconnect_is_due(
        {
            "reconnect_failure_count": 2,
            "last_reconnect_attempt_at": (now - timedelta(minutes=20)).isoformat(),
        },
        now=now,
    )
    assert _openwa_reconnect_is_due(
        {
            "reconnect_failure_count": 2,
            "last_reconnect_attempt_at": (now - timedelta(minutes=31)).isoformat(),
        },
        now=now,
    )


def test_openwa_connected_state_clears_auto_rotation_guard(client):
    from app.db.session import SessionLocal
    from app.models.whatsapp_account import WhatsAppAccount
    from app.services.onboarding_service import OnboardingService

    _, tenant_id = _create_tenant(client)
    db = SessionLocal()
    try:
        account = WhatsAppAccount(
            tenant_id=UUID(tenant_id),
            provider="openwa",
            provider_session_id="rotated-session",
            token_status="pending",
            webhook_status="verified",
            is_active=False,
            is_verified=True,
            provider_metadata_json={
                "risk_accepted": True,
                "auto_session_rotation_started_at": "2026-07-19T10:00:00",
                "auto_session_rotated_at": "2026-07-19T10:00:01",
                "auto_session_rotated_from": "old-session",
                "auto_session_rotated_to": "rotated-session",
            },
        )
        db.add(account)
        db.commit()

        OnboardingService(db).sync_openwa_webhook_event(
            account,
            "session.authenticated",
            {"status": "ready", "phone": "905551112233"},
        )
        db.refresh(account)

        assert account.is_active is True
        assert account.provider_metadata_json["health_status"] == "connected"
        assert not any(key.startswith("auto_session_rotat") for key in account.provider_metadata_json)
    finally:
        db.close()


def test_openwa_logout_webhook_marks_account_for_new_qr(client):
    from app.db.session import SessionLocal
    from app.models.whatsapp_account import WhatsAppAccount
    from app.services.onboarding_service import OnboardingService

    _, tenant_id = _create_tenant(client)
    db = SessionLocal()
    try:
        account = WhatsAppAccount(
            tenant_id=UUID(tenant_id),
            provider="openwa",
            provider_session_id="logout-session",
            token_status="active",
            webhook_status="verified",
            is_active=True,
            is_verified=True,
            provider_metadata_json={"risk_accepted": True, "health_status": "connected"},
        )
        db.add(account)
        db.commit()

        OnboardingService(db).sync_openwa_webhook_event(
            account,
            "session.disconnected",
            {"status": "logged_out", "reason": "Logged out from the phone"},
        )
        db.refresh(account)

        assert account.is_active is False
        assert account.token_status == "pending"
        assert account.provider_metadata_json["engine_status"] == "logged_out"
        assert account.provider_metadata_json["health_status"] == "action_required"
        assert account.provider_metadata_json["qr_required_at"]
    finally:
        db.close()


def test_openwa_missing_remote_session_is_recreated_for_qr(client, monkeypatch):
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.models.whatsapp_account import WhatsAppAccount
    from app.services.openwa_client import OpenWAError, openwa_client

    token, tenant_id = _create_tenant(client)
    headers = _headers(token, tenant_id)
    monkeypatch.setattr(settings, "OPENWA_ENABLED", True)
    monkeypatch.setattr(settings, "OPENWA_WEBHOOK_SECRET", "test-openwa-secret")
    monkeypatch.setattr(openwa_client, "base_url", "https://openwa.test")
    monkeypatch.setattr(openwa_client, "api_key", "test-api-key")
    monkeypatch.setattr(
        openwa_client,
        "get_session",
        AsyncMock(side_effect=[
            OpenWAError("missing", status_code=404),
            OpenWAError("missing", status_code=404),
        ]),
    )
    monkeypatch.setattr(
        openwa_client,
        "create_or_get_session",
        AsyncMock(return_value={"id": "replacement-session", "status": "created"}),
    )
    monkeypatch.setattr(
        openwa_client,
        "ensure_webhook",
        AsyncMock(return_value={"id": "replacement-webhook"}),
    )
    monkeypatch.setattr(
        openwa_client,
        "start_session",
        AsyncMock(return_value={"id": "replacement-session", "status": "qr_ready"}),
    )
    monkeypatch.setattr(
        openwa_client,
        "get_qr",
        AsyncMock(return_value={"status": "qr_ready", "qrCode": "data:image/png;base64,bmV3"}),
    )

    db = SessionLocal()
    try:
        db.add(WhatsAppAccount(
            tenant_id=UUID(tenant_id),
            provider="openwa",
            provider_session_id="missing-session",
            token_status="active",
            webhook_status="verified",
            is_active=True,
            is_verified=True,
            provider_metadata_json={
                "session_name": f"svontai-{UUID(tenant_id).hex[:24]}",
                "risk_accepted": True,
            },
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/api/onboarding/whatsapp/openwa/qr", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["session_id"] == "replacement-session"
    assert response.json()["qr_code"] == "data:image/png;base64,bmV3"

    db = SessionLocal()
    try:
        account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == UUID(tenant_id)
        ).one()
        assert account.provider_session_id == "replacement-session"
        assert account.token_status == "pending"
    finally:
        db.close()
