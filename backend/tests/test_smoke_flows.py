import re
from datetime import datetime, timedelta, timezone
from uuid import UUID


def _extract_6_digit_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match, f"Could not extract verification code from message: {message!r}"
    return match.group(1)


def _auth_headers(access_token: str, tenant_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id
    return headers


def test_registration_rejects_weak_password(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "weak-password@example.com",
            "password": "short",
            "full_name": "Weak Password",
            "terms_accepted": True,
            "privacy_notice_acknowledged": True,
            "terms_version": "2026-07-22",
            "privacy_version": "2026-07-22",
            "kvkk_notice_version": "2026-07-22",
        },
    )

    assert response.status_code == 422
    assert "12 karakter" in response.text


def test_smoke_register_verify_login_and_core_resources(client):
    email = "user1@example.com"
    password = "Password123!"
    full_name = "User One"

    missing_legal = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert missing_legal.status_code == 422

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-07-22", "privacy_version": "2026-07-22", "kvkk_notice_version": "2026-07-22"},
    )
    assert register_resp.status_code == 201, register_resp.text

    from app.db import session as session_module
    from app.models.onboarding import AuditLog

    db = session_module.SessionLocal()
    try:
        legal_acceptance = db.query(AuditLog).filter(
            AuditLog.action == "legal.registration.accepted"
        ).one()
        assert legal_acceptance.payload_json["terms_version"] == "2026-07-22"
        assert legal_acceptance.payload_json["kvkk_notice_version"] == "2026-07-22"
    finally:
        db.close()

    login_before_verify = client.post("/auth/login", json={"email": email, "password": password})
    assert login_before_verify.status_code == 403, login_before_verify.text
    assert login_before_verify.json()["detail"]["code"] == "EMAIL_VERIFICATION_REQUIRED"
    assert login_before_verify.json()["detail"]["email"] == email

    request_code = client.post("/auth/email-verification/request", json={"email": email})
    assert request_code.status_code == 200, request_code.text
    code = _extract_6_digit_code(request_code.json().get("message", ""))

    confirm_code = client.post("/auth/email-verification/confirm", json={"email": email, "code": code})
    assert confirm_code.status_code == 200, confirm_code.text
    assert confirm_code.json()["verified"] is True

    verified_request = client.post("/auth/email-verification/request", json={"email": email})
    assert verified_request.status_code == 200, verified_request.text
    assert verified_request.json()["verified"] is True

    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token_payload = login_resp.json()
    assert "refresh_token" not in token_payload
    assert "httponly" in login_resp.headers["set-cookie"].lower()
    access_token = token_payload["access_token"]

    tenant_resp = client.post(
        "/tenants",
        json={"name": "Acme Inc"},
        headers=_auth_headers(access_token),
    )
    assert tenant_resp.status_code == 201, tenant_resp.text
    tenant_id = tenant_resp.json()["id"]

    me_context = client.get("/api/me", headers=_auth_headers(access_token, tenant_id))
    assert me_context.status_code == 200, me_context.text
    assert me_context.json().get("tenant", {}).get("id") == tenant_id

    bots_list = client.get("/bots", headers=_auth_headers(access_token, tenant_id))
    assert bots_list.status_code == 200, bots_list.text
    assert bots_list.json() == []

    onboarding_status = client.get("/onboarding/setup/status", headers=_auth_headers(access_token, tenant_id))
    assert onboarding_status.status_code == 200, onboarding_status.text
    assert onboarding_status.json()["current_step"] == "business_profile"

    profile_resp = client.post(
        "/onboarding/setup/business-profile",
        json={
            "industry": "service",
            "primary_goal": "appointment",
            "tone": "professional",
            "handoff_rules": ["complaint", "unknown_question"],
            "website_url": "https://acme.example",
            "business_summary": "Randevu ve bilgi taleplerini WhatsApp üzerinden karşılayan hizmet işletmesi.",
        },
        headers=_auth_headers(access_token, tenant_id),
    )
    assert profile_resp.status_code == 200, profile_resp.text
    assert profile_resp.json()["current_step"] == "autopilot_setup"

    automatically_prepared_bots = client.get("/bots", headers=_auth_headers(access_token, tenant_id))
    assert automatically_prepared_bots.status_code == 200, automatically_prepared_bots.text
    assert len(automatically_prepared_bots.json()) == 1
    assert automatically_prepared_bots.json()[0]["name"] == "Acme Inc Asistanı"
    assert automatically_prepared_bots.json()[0]["assistant_type"] == "primary"

    assistant_profile = client.get(
        "/bots/assistant-profile",
        headers=_auth_headers(access_token, tenant_id),
    )
    assert assistant_profile.status_code == 200, assistant_profile.text
    assert assistant_profile.json()["assistant"]["assistant_type"] == "primary"
    assert assistant_profile.json()["completion_percent"] < 100

    trained_profile = client.put(
        "/bots/assistant-profile/training",
        json={
            "goal": "appointments",
            "tone": "professional",
            "response_length": "concise",
            "price_policy": "known_only",
            "handoff_mode": "automatic",
            "business_summary": "Acme randevu ile çalışan profesyonel bir hizmet işletmesidir.",
        },
        headers=_auth_headers(access_token, tenant_id),
    )
    assert trained_profile.status_code == 200, trained_profile.text
    assert trained_profile.json()["completion_percent"] == 100

    appointment_capability = client.patch(
        "/bots/assistant-profile/capabilities/appointment_management",
        json={"enabled": False, "config": {}},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert appointment_capability.status_code == 200, appointment_capability.text
    appointment_item = next(
        item for item in appointment_capability.json()["capabilities"]
        if item["key"] == "appointment_management"
    )
    assert appointment_item["enabled"] is False

    primary_id = assistant_profile.json()["assistant"]["id"]
    primary_delete = client.delete(
        f"/bots/{primary_id}",
        headers=_auth_headers(access_token, tenant_id),
    )
    assert primary_delete.status_code == 409, primary_delete.text

    run_onboarding = client.post("/onboarding/setup/run-autopilot", headers=_auth_headers(access_token, tenant_id))
    assert run_onboarding.status_code == 200, run_onboarding.text
    assert run_onboarding.json()["is_completed"] is True

    bots_list = client.get("/bots", headers=_auth_headers(access_token, tenant_id))
    assert bots_list.status_code == 200, bots_list.text
    assert len(bots_list.json()) == 1
    assert bots_list.json()[0]["name"] == "Acme Inc Asistanı"

    autopilot_status = client.get("/setup/autopilot/status", headers=_auth_headers(access_token, tenant_id))
    assert autopilot_status.status_code == 200, autopilot_status.text
    assert autopilot_status.json()["latest_run"]["status"] == "completed"
    assert autopilot_status.json()["business_profile"]["status"] == "customer_collected"
    assert autopilot_status.json()["concierge_enrichment"]["status"] == "pending"
    concierge_ticket_id = autopilot_status.json()["concierge_enrichment"]["ticket_id"]

    tickets_resp = client.get("/tickets", headers=_auth_headers(access_token, tenant_id))
    assert tickets_resp.status_code == 200, tickets_resp.text
    assert any(ticket["id"] == concierge_ticket_id for ticket in tickets_resp.json())

    bot_resp = client.post(
        "/bots",
        json={
            "name": "Sales Bot",
            "description": "Helps with sales questions",
            "welcome_message": "Merhaba!",
            "language": "tr",
            "primary_color": "#111827",
            "widget_position": "right",
        },
        headers=_auth_headers(access_token, tenant_id),
    )
    assert bot_resp.status_code == 201, bot_resp.text
    assert bot_resp.json()["assistant_type"] == "specialist"
    assert bot_resp.json()["specialist_key"] == "custom"
    bot_id = bot_resp.json()["id"]

    knowledge_resp = client.post(
        f"/bots/{bot_id}/knowledge",
        json={"title": "Soru", "question": "Nasılsın?", "answer": "İyiyim."},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert knowledge_resp.status_code == 201, knowledge_resp.text

    lead_resp = client.post(
        "/leads",
        json={"name": "Lead 1", "email": "", "phone": "", "notes": "", "source": "manual"},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert lead_resp.status_code == 200, lead_resp.text
    assert lead_resp.json().get("email") is None

    note_resp = client.post(
        "/notes",
        json={"title": "Not 1", "content": "Deneme içerik", "color": "slate", "pinned": True},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert note_resp.status_code == 201, note_resp.text

    starts_at = (datetime.now(tz=timezone.utc) + timedelta(hours=2)).isoformat()
    appointment_resp = client.post(
        "/appointments",
        json={
            "customer_name": "Müşteri",
            "customer_email": "customer@example.com",
            "subject": "Demo",
            "starts_at": starts_at,
            "notes": "Test",
            "reminder_before_minutes": 30,
        },
        headers=_auth_headers(access_token, tenant_id),
    )
    assert appointment_resp.status_code == 201, appointment_resp.text

    ticket_resp = client.post(
        "/tickets",
        json={"subject": "Destek", "priority": "normal", "message": "Merhaba"},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert ticket_resp.status_code == 201, ticket_resp.text

    refresh_resp = client.post("/auth/refresh", json={})
    assert refresh_resp.status_code == 200, refresh_resp.text
    assert "refresh_token" not in refresh_resp.json()
    refreshed_access_token = refresh_resp.json()["access_token"]

    blocked_origin = client.post(
        "/auth/refresh",
        json={},
        headers={"Origin": "https://attacker.example"},
    )
    assert blocked_origin.status_code == 403

    logout_resp = client.post(
        "/auth/logout",
        headers=_auth_headers(refreshed_access_token, tenant_id),
    )
    assert logout_resp.status_code == 200, logout_resp.text
    revoked_session = client.get(
        "/api/me",
        headers=_auth_headers(refreshed_access_token, tenant_id),
    )
    assert revoked_session.status_code == 401
    body_token_fallback = client.post(
        "/auth/refresh",
        json={"refresh_token": "legacy-body-token-must-not-be-accepted"},
    )
    assert body_token_fallback.status_code == 401


def test_smoke_password_reset_flow(client):
    email = "user2@example.com"
    password = "Password123!"
    full_name = "User Two"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-07-22", "privacy_version": "2026-07-22", "kvkk_notice_version": "2026-07-22"},
    )
    assert register_resp.status_code == 201, register_resp.text

    request_code = client.post("/auth/email-verification/request", json={"email": email})
    assert request_code.status_code == 200, request_code.text
    code = _extract_6_digit_code(request_code.json().get("message", ""))
    confirm_code = client.post("/auth/email-verification/confirm", json={"email": email, "code": code})
    assert confirm_code.status_code == 200, confirm_code.text

    reset_request = client.post("/auth/password-reset/request", json={"email": email})
    assert reset_request.status_code == 200, reset_request.text
    reset_code = _extract_6_digit_code(reset_request.json().get("message", ""))

    new_password = "NewPassword123!"
    reset_confirm = client.post(
        "/auth/password-reset/confirm",
        json={"email": email, "code": reset_code, "new_password": new_password},
    )
    assert reset_confirm.status_code == 200, reset_confirm.text

    login_old = client.post("/auth/login", json={"email": email, "password": password})
    assert login_old.status_code == 401, login_old.text

    login_new = client.post("/auth/login", json={"email": email, "password": new_password})
    assert login_new.status_code == 200, login_new.text


def test_login_context_auto_provisions_missing_tenant(client):
    from app.db.session import SessionLocal
    from app.models.tenant import Tenant

    email = "missing-tenant@example.com"
    password = "Password123!"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Missing Tenant", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-07-22", "privacy_version": "2026-07-22", "kvkk_notice_version": "2026-07-22"},
    )
    assert register_resp.status_code == 201, register_resp.text

    request_code = client.post("/auth/email-verification/request", json={"email": email})
    code = _extract_6_digit_code(request_code.json().get("message", ""))
    confirm_code = client.post("/auth/email-verification/confirm", json={"email": email, "code": code})
    assert confirm_code.status_code == 200, confirm_code.text

    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    headers = _auth_headers(login_resp.json()["access_token"])

    first_context = client.get("/api/me", headers=headers)
    assert first_context.status_code == 200, first_context.text
    tenant_id = first_context.json()["tenant"]["id"]
    assert first_context.json()["tenant"]["name"] == "Missing Tenant İşletmesi"
    assert first_context.json()["role"]["name"] == "owner"

    second_context = client.get("/api/me", headers=headers)
    assert second_context.status_code == 200, second_context.text
    assert second_context.json()["tenant"]["id"] == tenant_id

    db = SessionLocal()
    try:
        assert db.query(Tenant).filter(Tenant.id == UUID(tenant_id)).count() == 1
    finally:
        db.close()
