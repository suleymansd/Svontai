from app.core.totp import generate_code


def _extract_6_digit_code(message: str) -> str:
    digits = "".join(ch for ch in (message or "") if ch.isdigit())
    return digits[-6:]


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _register_verify_and_login(client):
    email = "twofactor@example.com"
    password = "Password123!"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Two Factor"},
    )
    assert register_resp.status_code == 201, register_resp.text

    request_code = client.post("/auth/email-verification/request", json={"email": email})
    assert request_code.status_code == 200, request_code.text
    code = _extract_6_digit_code(request_code.json().get("message", ""))
    assert len(code) == 6

    confirm_code = client.post("/auth/email-verification/confirm", json={"email": email, "code": code})
    assert confirm_code.status_code == 200, confirm_code.text

    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    access_token = login_resp.json()["access_token"]

    return email, password, access_token


def test_two_factor_setup_and_login_flow(client):
    email, password, access_token = _register_verify_and_login(client)

    status_before = client.get("/auth/2fa/status", headers=_auth_headers(access_token))
    assert status_before.status_code == 200, status_before.text
    assert status_before.json()["enabled"] is False

    setup_wrong_password = client.post(
        "/auth/2fa/setup",
        json={"current_password": "wrong"},
        headers=_auth_headers(access_token),
    )
    assert setup_wrong_password.status_code == 403

    setup_ok = client.post(
        "/auth/2fa/setup",
        json={"current_password": password},
        headers=_auth_headers(access_token),
    )
    assert setup_ok.status_code == 200, setup_ok.text
    setup_payload = setup_ok.json()
    secret = setup_payload["secret"]
    assert secret
    assert setup_payload["otpauth_uri"].startswith("otpauth://totp/")

    enable_invalid = client.post(
        "/auth/2fa/enable",
        json={"code": "000000"},
        headers=_auth_headers(access_token),
    )
    assert enable_invalid.status_code == 400

    enable_ok = client.post(
        "/auth/2fa/enable",
        json={"code": generate_code(secret)},
        headers=_auth_headers(access_token),
    )
    assert enable_ok.status_code == 200, enable_ok.text
    assert enable_ok.json()["enabled"] is True

    login_without_2fa = client.post("/auth/login", json={"email": email, "password": password})
    assert login_without_2fa.status_code == 401, login_without_2fa.text
    assert login_without_2fa.json()["detail"]["code"] == "TWO_FACTOR_REQUIRED"

    login_invalid_2fa = client.post(
        "/auth/login",
        json={"email": email, "password": password, "two_factor_code": "123456"},
    )
    assert login_invalid_2fa.status_code == 401
    assert login_invalid_2fa.json()["detail"]["code"] == "TWO_FACTOR_INVALID"

    login_with_2fa = client.post(
        "/auth/login",
        json={"email": email, "password": password, "two_factor_code": generate_code(secret)},
    )
    assert login_with_2fa.status_code == 200, login_with_2fa.text
    enabled_access_token = login_with_2fa.json()["access_token"]

    disable_wrong_password = client.post(
        "/auth/2fa/disable",
        json={"current_password": "wrong", "code": generate_code(secret)},
        headers=_auth_headers(enabled_access_token),
    )
    assert disable_wrong_password.status_code == 403

    disable_ok = client.post(
        "/auth/2fa/disable",
        json={"current_password": password, "code": generate_code(secret)},
        headers=_auth_headers(enabled_access_token),
    )
    assert disable_ok.status_code == 200, disable_ok.text
    assert disable_ok.json()["enabled"] is False

    status_after = client.get("/auth/2fa/status", headers=_auth_headers(enabled_access_token))
    assert status_after.status_code == 200, status_after.text
    assert status_after.json()["enabled"] is False

    login_after_disable = client.post("/auth/login", json={"email": email, "password": password})
    assert login_after_disable.status_code == 200, login_after_disable.text
