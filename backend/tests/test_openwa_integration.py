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
        json={"email": email, "password": password, "full_name": "OpenWA User"},
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

    qr = client.get("/api/onboarding/whatsapp/openwa/qr", headers=headers)
    assert qr.status_code == 200, qr.text
    assert qr.json()["qr_code"].startswith("data:image/png;base64,")

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

    _, tenant_id = _create_tenant(client)
    monkeypatch.setattr(settings, "OPENWA_WEBHOOK_SECRET", "test-openwa-secret")
    monkeypatch.setattr(settings, "USE_N8N", True)
    generate_reply = AsyncMock(return_value="Merhaba, size nasıl yardımcı olabilirim?")
    send_text = AsyncMock(return_value={"messageId": "openwa-reply-1"})
    n8n_trigger = AsyncMock(return_value=AutomationRunStatus.FAILED.value)
    monkeypatch.setattr(ai_service, "generate_reply", generate_reply)
    monkeypatch.setattr(openwa_client, "send_text", send_text)
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
            "contact": {"pushName": "Müşteri"},
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
    send_text.assert_awaited_once_with(
        session_id,
        "905559998877",
        "Merhaba, size nasıl yardımcı olabilirim?",
    )


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
