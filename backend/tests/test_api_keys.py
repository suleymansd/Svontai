import re


def _extract_6_digit_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match, f"Could not extract code from message: {message!r}"
    return match.group(1)


def _auth_headers(access_token: str, tenant_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id
    return headers


def _register_verify_login_and_create_tenant(client):
    email = "apikeys@example.com"
    password = "Password123!"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Api Keys"},
    )
    assert register_resp.status_code == 201, register_resp.text

    request_code = client.post("/auth/email-verification/request", json={"email": email})
    assert request_code.status_code == 200, request_code.text
    code = _extract_6_digit_code(request_code.json().get("message", ""))

    confirm_code = client.post("/auth/email-verification/confirm", json={"email": email, "code": code})
    assert confirm_code.status_code == 200, confirm_code.text

    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    access_token = login_resp.json()["access_token"]

    tenant_resp = client.post(
        "/tenants",
        json={"name": "Api Tenant"},
        headers=_auth_headers(access_token),
    )
    assert tenant_resp.status_code == 201, tenant_resp.text
    tenant_id = tenant_resp.json()["id"]

    return access_token, tenant_id, password


def test_api_keys_require_plan_feature(client):
    access_token, tenant_id, password = _register_verify_login_and_create_tenant(client)

    list_resp = client.get("/api-keys", headers=_auth_headers(access_token, tenant_id))
    assert list_resp.status_code == 403

    upgrade = client.post(
        "/subscription/upgrade",
        json={"plan_name": "pro"},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert upgrade.status_code == 200, upgrade.text

    create_fail = client.post(
        "/api-keys",
        json={"name": "Primary", "current_password": "wrong"},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert create_fail.status_code == 403

    create_ok = client.post(
        "/api-keys",
        json={"name": "Primary", "current_password": password},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert create_ok.status_code == 201, create_ok.text
    payload = create_ok.json()
    assert payload["last4"]
    assert payload["secret"].startswith("svk_")

    list_ok = client.get("/api-keys", headers=_auth_headers(access_token, tenant_id))
    assert list_ok.status_code == 200, list_ok.text
    items = list_ok.json()["items"]
    assert len(items) == 1
    assert "secret" not in items[0]
    assert items[0]["last4"] == payload["last4"]

    revoke_fail = client.request(
        "DELETE",
        f"/api-keys/{items[0]['id']}",
        json={"current_password": "wrong"},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert revoke_fail.status_code == 403

    revoke_ok = client.request(
        "DELETE",
        f"/api-keys/{items[0]['id']}",
        json={"current_password": password},
        headers=_auth_headers(access_token, tenant_id),
    )
    assert revoke_ok.status_code == 204, revoke_ok.text

