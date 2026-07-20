import re
import uuid
from datetime import timedelta

from app.core.time import utc_now_naive


def _extract_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match
    return match.group(1)


def _authenticated_tenant(client) -> tuple[str, str, str]:
    email = "notifications@example.com"
    password = "Password123!"
    assert client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Notification User"},
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
        json={"name": "Notification Tenant"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    return token, tenant["id"], email


def _headers(token: str, tenant_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }


def test_push_subscription_and_preferences_are_persisted(client, monkeypatch):
    from app.core.config import settings

    token, tenant_id, _ = _authenticated_tenant(client)
    headers = _headers(token, tenant_id)
    monkeypatch.setattr(settings, "WEB_PUSH_VAPID_PUBLIC_KEY", "test-public-key")
    monkeypatch.setattr(
        settings,
        "WEB_PUSH_VAPID_PRIVATE_KEY_B64",
        "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCg==",
    )

    initial = client.get("/notifications/settings", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["configured"] is True
    assert initial.json()["subscribed"] is False

    subscription = client.post(
        "/notifications/subscribe",
        headers=headers,
        json={
            "endpoint": "https://push.example.test/subscription-1",
            "keys": {"p256dh": "browser-public-key", "auth": "browser-auth-secret"},
        },
    )
    assert subscription.status_code == 201

    updated = client.patch(
        "/notifications/settings",
        headers=headers,
        json={
            "notify_ai_reply": True,
            "notify_new_lead": False,
            "notify_appointment": True,
            "notify_weekly_report": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["updated"] == 1

    status = client.get("/notifications/settings", headers=headers).json()
    assert status["subscribed"] is True
    assert status["device_count"] == 1
    assert status["preferences"]["notify_new_lead"] is False
    assert status["preferences"]["notify_weekly_report"] is False

    disabled = client.request(
        "DELETE",
        "/notifications/subscribe",
        headers=headers,
        json={"endpoint": "https://push.example.test/subscription-1"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["disabled"] == 1


def test_operational_report_uses_real_tenant_data(client):
    from app.db.session import SessionLocal
    from app.models.appointment import Appointment
    from app.models.automation import AutomationRun, AutomationRunStatus
    from app.models.bot import Bot
    from app.models.conversation import Conversation, ConversationSource
    from app.models.lead import Lead
    from app.models.message import Message, MessageSender

    token, tenant_id, _ = _authenticated_tenant(client)
    headers = _headers(token, tenant_id)
    tenant_uuid = uuid.UUID(tenant_id)

    db = SessionLocal()
    try:
        report_now = utc_now_naive()
        bot = Bot(
            tenant_id=tenant_uuid,
            name="Report Bot",
            description="Report test",
            welcome_message="Merhaba",
            language="tr",
            primary_color="#2563EB",
            widget_position="right",
            is_active=True,
        )
        db.add(bot)
        db.flush()
        conversation = Conversation(
            bot_id=bot.id,
            external_user_id="905551112233",
            source=ConversationSource.WHATSAPP.value,
        )
        db.add(conversation)
        db.flush()
        db.add_all([
            Message(
                conversation_id=conversation.id,
                sender=MessageSender.USER.value,
                content="Merhaba",
            ),
            Message(
                conversation_id=conversation.id,
                sender=MessageSender.BOT.value,
                content="Merhaba, nasıl yardımcı olabilirim?",
            ),
            Lead(
                tenant_id=tenant_uuid,
                bot_id=bot.id,
                conversation_id=conversation.id,
                name="Müşteri",
                phone="905551112233",
                source="whatsapp",
            ),
            Appointment(
                tenant_id=tenant_uuid,
                created_by=None,
                customer_name="Müşteri",
                subject="Görüşme",
                starts_at=utc_now_naive() + timedelta(days=1),
            ),
            AutomationRun(
                tenant_id=str(tenant_uuid),
                channel="whatsapp",
                from_number="905551112233",
                to_number="905552223344",
                message_id="report-message-failed",
                message_content="Merhaba",
                n8n_workflow_id="svontai-whatsapp-v2",
                status=AutomationRunStatus.FAILED.value,
                error_message="Webhook was not registered",
                created_at=report_now - timedelta(minutes=2),
            ),
            AutomationRun(
                tenant_id=str(tenant_uuid),
                channel="whatsapp",
                from_number="905551112233",
                to_number="905552223344",
                message_id="report-message-1",
                message_content="Merhaba",
                n8n_workflow_id="svontai-whatsapp-v2",
                status=AutomationRunStatus.SUCCESS.value,
                created_at=report_now - timedelta(minutes=1),
            ),
        ])
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/analytics/operational-report",
        params={"period": "today"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["metrics"]["incoming_messages"] == 1
    assert report["metrics"]["ai_replies"] == 1
    assert report["metrics"]["leads"] == 1
    assert report["metrics"]["appointments"] == 1
    assert report["metrics"]["successful_automations"] == 1
    assert report["metrics"]["failed_automations"] == 1
    assert report["metrics"]["unresolved_automation_failures"] == 0
    assert report["metrics"]["recovered_automation_failures"] == 1
    assert report["health"]["healthy"] is True
    assert "PERFORMANS ÖZETİ" in report["text"]
