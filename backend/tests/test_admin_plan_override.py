from __future__ import annotations

import uuid
from uuid import UUID

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.subscription import TenantSubscription
from app.models.user import User


def _extract_6_digit_code(message: str) -> str:
    for token in (message or "").split():
        if token.isdigit() and len(token) == 6:
            return token
    raise AssertionError(f"Could not extract verification code from message: {message!r}")


def _register_and_login_with_tenant(client) -> tuple[str, str]:
    email = f"plan-tenant-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Plan Tenant User"},
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
        json={"name": "Plan Override Tenant"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert tenant_resp.status_code == 201, tenant_resp.text
    tenant_id = tenant_resp.json()["id"]
    return access_token, tenant_id


def _create_and_login_super_admin(client) -> str:
    from app.db import session as session_module

    email = f"plan-admin-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"

    db = session_module.SessionLocal()
    try:
        admin_user = User(
            email=email,
            full_name="Plan Override Admin",
            password_hash=get_password_hash(password),
            is_admin=True,
            is_active=True,
            email_verified=True,
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()

    login_resp = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
            "portal": "super_admin",
            "admin_session_note": "plan override",
        },
    )
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["access_token"]


def test_admin_plan_override_non_admin_forbidden(client):
    user_token, tenant_id = _register_and_login_with_tenant(client)
    headers = {"Authorization": f"Bearer {user_token}"}

    response = client.put(
        f"/admin/tenants/{tenant_id}/plan",
        json={"plan_type": "premium", "note": "test"},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_admin_plan_override_success(client):
    from app.db import session as session_module

    _, tenant_id = _register_and_login_with_tenant(client)
    admin_token = _create_and_login_super_admin(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.put(
        f"/admin/tenants/{tenant_id}/plan",
        json={"plan_type": "premium", "note": "meeting_summary test unlock"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["tenant_id"] == tenant_id
    assert payload["new_plan"] == "premium"
    assert payload["status"] == "ok"

    db = session_module.SessionLocal()
    try:
        subscription = db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == UUID(tenant_id)
        ).first()
        assert subscription is not None
        assert subscription.plan.name == "premium"
        assert (subscription.extra_data or {}).get("admin_plan_override", {}).get("new_plan") == "premium"
    finally:
        db.close()


def test_admin_plan_override_disabled_in_prod(client):
    _, tenant_id = _register_and_login_with_tenant(client)
    admin_token = _create_and_login_super_admin(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    previous_environment = settings.ENVIRONMENT
    previous_allow_override = settings.ALLOW_ADMIN_PLAN_OVERRIDE
    settings.ENVIRONMENT = "prod"
    settings.ALLOW_ADMIN_PLAN_OVERRIDE = False

    try:
        response = client.put(
            f"/admin/tenants/{tenant_id}/plan",
            json={"plan_type": "premium", "note": "blocked in prod"},
            headers=headers,
        )
        assert response.status_code == 403, response.text
        detail = response.json().get("detail", {})
        assert detail.get("code") == "PLAN_OVERRIDE_DISABLED"
    finally:
        settings.ENVIRONMENT = previous_environment
        settings.ALLOW_ADMIN_PLAN_OVERRIDE = previous_allow_override
