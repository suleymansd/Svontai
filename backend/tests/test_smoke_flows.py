import re
from datetime import datetime, timedelta, timezone


def _extract_6_digit_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match, f"Could not extract verification code from message: {message!r}"
    return match.group(1)


def _auth_headers(access_token: str, tenant_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id
    return headers


def test_smoke_register_verify_login_and_core_resources(client):
    email = "user1@example.com"
    password = "Password123!"
    full_name = "User One"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_resp.status_code == 201, register_resp.text

    login_before_verify = client.post("/auth/login", json={"email": email, "password": password})
    assert login_before_verify.status_code == 403, login_before_verify.text

    request_code = client.post("/auth/email-verification/request", json={"email": email})
    assert request_code.status_code == 200, request_code.text
    code = _extract_6_digit_code(request_code.json().get("message", ""))

    confirm_code = client.post("/auth/email-verification/confirm", json={"email": email, "code": code})
    assert confirm_code.status_code == 200, confirm_code.text

    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token_payload = login_resp.json()
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


def test_smoke_password_reset_flow(client):
    email = "user2@example.com"
    password = "Password123!"
    full_name = "User Two"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
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
