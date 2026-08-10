from __future__ import annotations

import re
import uuid
from datetime import timedelta

from app.core.time import utc_now_naive
from app.models.appointment import Appointment
from app.models.automation import AutomationRun, AutomationRunStatus
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationStatus
from app.models.voice_automation import OutboundCallJob, OutboundCallJobStatus


def _tenant_session(client, email: str) -> tuple[str, str]:
    password = "Password123!"
    assert client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Action Center User",
            "terms_accepted": True,
            "privacy_notice_acknowledged": True,
            "terms_version": "2026-08-04",
            "privacy_version": "2026-08-04",
            "kvkk_notice_version": "2026-08-04",
        },
    ).status_code == 201
    verification = client.post("/auth/email-verification/request", json={"email": email})
    code = re.search(r"(\d{6})", verification.json()["message"]).group(1)
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


def test_action_center_returns_only_current_tenant_attention_items(client):
    from app.db.session import SessionLocal

    token, tenant_id = _tenant_session(client, "action-center@example.com")
    other_token, other_tenant_id = _tenant_session(client, "action-center-other@example.com")
    now = utc_now_naive()

    db = SessionLocal()
    try:
        bot = Bot(
            tenant_id=uuid.UUID(tenant_id),
            name="Action Assistant",
            assistant_type="specialist",
        )
        other_bot = Bot(
            tenant_id=uuid.UUID(other_tenant_id),
            name="Other Assistant",
            assistant_type="specialist",
        )
        db.add_all([bot, other_bot])
        db.flush()
        conversation = Conversation(
            bot_id=bot.id,
            external_user_id="905551112233",
            source="whatsapp",
            status=ConversationStatus.WAITING.value,
            extra_data={"contact_name": "Ayşe Yılmaz", "phone_number": "+905551112233"},
        )
        other_conversation = Conversation(
            bot_id=other_bot.id,
            external_user_id="905559999999",
            source="whatsapp",
            status=ConversationStatus.WAITING.value,
            extra_data={"contact_name": "Başka Tenant"},
        )
        db.add_all([conversation, other_conversation])
        db.add(AutomationRun(
            tenant_id=tenant_id,
            channel="whatsapp",
            from_number="+905551112233",
            n8n_workflow_id="workflow-action",
            status=AutomationRunStatus.FAILED.value,
            error_message="private provider error",
            created_at=now - timedelta(minutes=20),
        ))
        db.add(OutboundCallJob(
            tenant_id=uuid.UUID(tenant_id),
            provider="twilio",
            from_number="+902120000000",
            to_number="+905551112233",
            status=OutboundCallJobStatus.FAILED.value,
            attempts=2,
            max_attempts=2,
            last_error="private call error",
            updated_at=now - timedelta(minutes=10),
        ))
        db.add(Appointment(
            tenant_id=uuid.UUID(tenant_id),
            customer_name="Mehmet Kaya",
            subject="Tanışma görüşmesi",
            starts_at=now + timedelta(hours=2),
            duration_minutes=30,
            status="scheduled",
            calendar_sync_status="synced",
        ))
        db.add(Appointment(
            tenant_id=uuid.UUID(tenant_id),
            customer_name="Takvim Müşterisi",
            subject="Takvim senkron testi",
            starts_at=now + timedelta(days=2),
            status="scheduled",
            calendar_sync_status="failed",
            calendar_last_error="private calendar error",
        ))
        db.commit()
        conversation_id = str(conversation.id)
    finally:
        db.close()

    response = client.get("/analytics/action-center", headers=_headers(token, tenant_id))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["required_count"] == 4
    assert {item["kind"] for item in payload["items"]} == {
        "human_handoff",
        "automation_failure",
        "voice_failure",
        "calendar_sync_failure",
    }
    assert payload["items"][0]["id"] == f"handoff:{conversation_id}"
    assert all("private" not in item["description"] for item in payload["items"])
    assert payload["upcoming_appointments"][0]["customer_name"] == "Mehmet Kaya"

    other_response = client.get(
        "/analytics/action-center",
        headers=_headers(other_token, other_tenant_id),
    )
    assert other_response.status_code == 200
    other_payload = other_response.json()
    assert other_payload["required_count"] == 1
    assert other_payload["items"][0]["description"] == "Başka Tenant insan desteği bekliyor."
    assert other_payload["upcoming_appointments"] == []


def test_action_center_hides_automation_failure_after_recovery(client):
    from app.db.session import SessionLocal

    token, tenant_id = _tenant_session(client, "action-center-recovery@example.com")
    now = utc_now_naive()
    db = SessionLocal()
    try:
        db.add(AutomationRun(
            tenant_id=tenant_id,
            channel="whatsapp",
            from_number="+905551112233",
            n8n_workflow_id="workflow-recovered",
            status=AutomationRunStatus.FAILED.value,
            created_at=now - timedelta(minutes=20),
        ))
        db.add(AutomationRun(
            tenant_id=tenant_id,
            channel="whatsapp",
            from_number="+905551112233",
            n8n_workflow_id="workflow-recovered",
            status=AutomationRunStatus.SUCCESS.value,
            created_at=now - timedelta(minutes=5),
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/analytics/action-center", headers=_headers(token, tenant_id))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["required_count"] == 0
    assert payload["items"] == []
