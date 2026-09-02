from app.core.security import decode_token, get_password_hash
from app.models.user import User


DEVICE_ID = "2f4cb1b8-7e96-49f8-9fcb-8f6694ba08f7"


def _create_verified_user(email: str, password: str) -> None:
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        db.add(
            User(
                email=email,
                full_name="Mobile User",
                password_hash=get_password_hash(password),
                email_verified=True,
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()


def test_mobile_login_and_rotating_refresh_token(client):
    email = "mobile-user@example.com"
    password = "Password123!"
    _create_verified_user(email, password)

    login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
            "client": "mobile",
            "device_id": DEVICE_ID,
            "device_name": "iPhone 17 Pro",
            "platform": "ios",
            "app_version": "1.0.0",
        },
    )

    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["expires_in"] > 0
    assert "set-cookie" not in login.headers

    refresh_payload = decode_token(tokens["refresh_token"])
    assert refresh_payload["client"] == "mobile"
    assert refresh_payload["device_id"] == DEVICE_ID

    refreshed = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"], "device_id": DEVICE_ID},
    )
    assert refreshed.status_code == 200, refreshed.text
    rotated = refreshed.json()
    assert rotated["access_token"]
    assert rotated["refresh_token"] != tokens["refresh_token"]

    reused = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"], "device_id": DEVICE_ID},
    )
    assert reused.status_code == 401


def test_mobile_refresh_rejects_another_device(client):
    email = "mobile-device-check@example.com"
    password = "Password123!"
    _create_verified_user(email, password)

    login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
            "client": "mobile",
            "device_id": DEVICE_ID,
            "platform": "android",
        },
    )
    token = login.json()["refresh_token"]

    rejected = client.post(
        "/auth/refresh",
        json={
            "refresh_token": token,
            "device_id": "3b6f2607-689c-4f63-b6d3-9182c879a495",
        },
    )
    assert rejected.status_code == 401
    assert rejected.json()["detail"] == "Mobil oturum bu cihazla eşleşmiyor"


def test_mobile_login_requires_device_metadata(client):
    response = client.post(
        "/auth/login",
        json={
            "email": "missing-device@example.com",
            "password": "Password123!",
            "client": "mobile",
        },
    )
    assert response.status_code == 422
