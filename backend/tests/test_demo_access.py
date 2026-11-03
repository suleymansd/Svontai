from datetime import timedelta
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest

from app.core.config import settings
from app.core.security import create_access_token, hash_token
from app.core.time import utc_now_naive
from app.models.demo_access import DemoAccess
from app.models.plan import DEFAULT_PLANS, Plan
from app.models.session import UserSession
from app.models.tenant import Tenant
from app.models.user import User
from app.services.demo_access_service import AI_REQUEST_LIMIT, demo_login_limiter, demo_write_limiter


@pytest.fixture
def admin_headers(client, monkeypatch):
    from app.db.session import SessionLocal

    monkeypatch.setattr(settings, "SUPER_ADMIN_REQUIRE_2FA", False)
    demo_login_limiter.clear()
    demo_write_limiter.clear()
    with SessionLocal() as db:
        admin = User(id=uuid4(), email=f"admin-{uuid4().hex}@example.com", full_name="Admin", password_hash="unused", is_admin=True)
        db.add(admin)
        if not db.query(Plan).filter(Plan.name == "premium").first():
            db.add(Plan(**next(plan for plan in DEFAULT_PLANS if plan["name"] == "premium")))
        db.commit()
        token = create_access_token({"sub": str(admin.id), "portal": "super_admin"})
    return {"Authorization": f"Bearer {token}"}


def create(client, admin_headers, name="Optimageek"):
    response = client.post("/admin/demo-access", headers=admin_headers, json={"name": name})
    assert response.status_code == 201, response.text
    item = response.json()
    return item, parse_qs(urlsplit(item["url"]).fragment)["token"][0]


def enter(client, token):
    response = client.post("/auth/demo-login", json={"token": token})
    assert response.status_code == 200, response.text
    assert "httponly" in response.headers["set-cookie"].lower()
    assert response.headers["cache-control"] == "no-store"
    assert "refresh_token" not in response.json()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_link_opens_premium_without_registration_and_reuses_workspace(client, admin_headers):
    from app.db.session import SessionLocal

    item, token = create(client, admin_headers)
    headers = enter(client, token)
    context = client.get("/api/me", headers=headers)
    assert context.status_code == 200, context.text
    body = context.json()
    assert body["tenant"]["id"] == item["tenant_id"]
    assert body["tenant"]["name"] == "Optimageek"
    assert body["user"]["is_admin"] is False
    assert body["entitlements"]["plan_type"] == "premium"
    assert body["entitlements"]["demo_access"]["expires_at"]
    assert len(client.get("/bots", headers=headers).json()) == 1
    again = enter(client, token)
    assert client.get("/api/me", headers=again).json()["tenant"]["id"] == item["tenant_id"]
    refresh = client.post("/auth/refresh", json={})
    assert refresh.status_code == 200, refresh.text
    with SessionLocal() as db:
        demo = db.get(DemoAccess, UUID(item["id"]))
        assert demo.token_hash == hash_token(token)
        assert demo.visit_count == 2
        assert db.query(Tenant).count() == 1
        assert all(session.expires_at <= demo.expires_at for session in db.query(UserSession).filter_by(user_id=demo.user_id))
    listing = client.get("/admin/demo-access", headers=admin_headers)
    assert "token" not in listing.text and "url" not in listing.text


def test_demo_is_isolated_and_cannot_administer_or_create_credentials(client, admin_headers):
    first, token = create(client, admin_headers)
    other, _ = create(client, admin_headers, "Other customer")
    headers = enter(client, token)
    assert client.get("/api/me", headers={**headers, "X-Tenant-ID": other["tenant_id"]}).status_code == 403
    assert client.get("/admin/demo-access", headers=headers).status_code == 403
    assert client.post("/admin/demo-access", headers=headers, json={"name": "Escalation"}).status_code == 403
    assert client.put("/me", headers=headers, json={"email": "attacker@example.com"}).status_code == 403
    assert client.post("/api-keys", headers=headers, json={"name": "Persist"}).status_code == 403
    assert client.get("/integrations/google/start", headers=headers).status_code == 403
    assert client.post("/appointments/send-reminders", headers=headers).status_code == 403
    assert client.get("/api/me", headers=headers).json()["tenant"]["id"] == first["tenant_id"]


def test_revocation_ends_existing_sessions_without_deleting_data(client, admin_headers):
    from app.db.session import SessionLocal

    item, token = create(client, admin_headers)
    headers = enter(client, token)
    note = client.post("/notes", headers=headers, json={"title": "Test", "content": "Keep this"})
    assert note.status_code == 201, note.text
    assert client.delete(f"/admin/demo-access/{item['id']}", headers=admin_headers).status_code == 204
    assert client.post("/auth/demo-login", json={"token": token}).status_code == 403
    assert client.get("/api/me", headers=headers).status_code in (401, 403)
    assert client.post("/auth/refresh", json={}).status_code == 403
    with SessionLocal() as db:
        from app.models.note import WorkspaceNote
        assert db.get(Tenant, UUID(item["tenant_id"])) is not None
        assert db.query(WorkspaceNote).filter_by(tenant_id=UUID(item["tenant_id"])).count() == 1


def test_expiry_applies_to_refresh_and_access_not_just_link(client, admin_headers):
    from app.db.session import SessionLocal

    item, token = create(client, admin_headers)
    headers = enter(client, token)
    with SessionLocal() as db:
        db.get(DemoAccess, UUID(item["id"])).expires_at = utc_now_naive() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/me", headers=headers).status_code == 403
    assert client.post("/auth/refresh", json={}).status_code == 403
    assert client.post("/auth/demo-login", json={"token": token}).status_code == 403


def test_rotation_invalidates_old_link_and_sessions(client, admin_headers):
    item, token = create(client, admin_headers)
    headers = enter(client, token)
    rotated = client.post(f"/admin/demo-access/{item['id']}/rotate", headers=admin_headers)
    assert rotated.status_code == 200, rotated.text
    assert client.post("/auth/demo-login", json={"token": token}).status_code == 403
    assert client.get("/api/me", headers=headers).status_code == 401
    new_token = parse_qs(urlsplit(rotated.json()["url"]).fragment)["token"][0]
    new_headers = enter(client, new_token)
    assert client.get("/api/me", headers=new_headers).json()["tenant"]["id"] == item["tenant_id"]


def test_simulator_works_and_has_a_persistent_ai_budget(client, admin_headers, monkeypatch):
    from app.api.routers.bots import ai_service
    from app.db.session import SessionLocal

    item, token = create(client, admin_headers)
    headers = enter(client, token)
    bot = client.get("/bots", headers=headers).json()[0]
    reply = AsyncMock(return_value="Size nasıl yardımcı olabilirim?")
    monkeypatch.setattr(ai_service, "generate_reply", reply)
    response = client.post(f"/bots/{bot['id']}/simulate", headers=headers, json={"message": "Merhaba", "history": []})
    assert response.status_code == 200, response.text
    assert reply.call_count == 1
    with SessionLocal() as db:
        demo = db.get(DemoAccess, UUID(item["id"]))
        assert demo.ai_requests_used == 1
        demo.ai_requests_used = AI_REQUEST_LIMIT
        db.commit()
    assert client.post(f"/bots/{bot['id']}/simulate", headers=headers, json={"message": "Merhaba", "history": []}).status_code == 429
    assert reply.call_count == 1
    assert client.post("/public/chat/init", json={"bot_public_key": bot["public_key"]}).status_code == 403


def test_test_appointments_never_send_external_email(client, admin_headers, monkeypatch):
    from app.db.session import SessionLocal
    from app.services.email_service import EmailService
    from app.services.appointment_reminder_service import AppointmentReminderService

    _, token = create(client, admin_headers)
    headers = enter(client, token)
    def fail_send(*args, **kwargs):
        raise AssertionError("Demo must not send email")
    monkeypatch.setattr(EmailService, "send_appointment_created_email", fail_send)
    monkeypatch.setattr(EmailService, "send_appointment_before_reminder_email", fail_send)
    monkeypatch.setattr(EmailService, "send_appointment_after_followup_email", fail_send)
    response = client.post("/appointments", headers=headers, json={
        "customer_name": "Test", "customer_email": "real@example.com", "subject": "Preview",
        "starts_at": (utc_now_naive() + timedelta(minutes=5)).isoformat(),
    })
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        result = AppointmentReminderService(db).dispatch_due_reminders()
        assert result.sent_before == result.sent_after == 0


def test_creation_and_login_reject_untrusted_inputs(client, admin_headers):
    assert client.post("/admin/demo-access", json={"name": "Forbidden"}).status_code in (401, 403)
    for payload in ({"name": "  "}, {"name": "Test", "days": 0}, {"name": "Test", "days": 999}, {"name": "Test", "tenant_id": str(uuid4())}):
        assert client.post("/admin/demo-access", headers=admin_headers, json=payload).status_code == 422
    _, token = create(client, admin_headers)
    assert client.post("/auth/demo-login", json={"token": "invalid"}).status_code == 422
    assert client.post("/auth/demo-login", json={"token": "A" * 43}).status_code == 403
    assert client.post("/auth/demo-login", json={"token": token}, headers={"Origin": "https://attacker.example"}).status_code == 403


def test_disabled_or_elevated_demo_identity_cannot_use_link(client, admin_headers):
    from app.db.session import SessionLocal

    item, token = create(client, admin_headers)
    with SessionLocal() as db:
        demo = db.get(DemoAccess, UUID(item["id"]))
        db.get(User, demo.user_id).is_admin = True
        db.commit()
    assert client.post("/auth/demo-login", json={"token": token}).status_code == 403


def test_removed_demo_record_cannot_turn_old_sessions_into_normal_accounts(client, admin_headers):
    from app.db.session import SessionLocal

    item, token = create(client, admin_headers)
    headers = enter(client, token)
    with SessionLocal() as db:
        db.delete(db.get(DemoAccess, UUID(item["id"])))
        db.commit()
    assert client.get("/api/me", headers=headers).status_code == 401
    assert client.post("/auth/refresh", json={}).status_code == 401
