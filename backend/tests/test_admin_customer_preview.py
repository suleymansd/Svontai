from __future__ import annotations

import re
import uuid

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.onboarding import AuditLog
from app.models.user import User


def _create_tenant(client) -> str:
    email = f"preview-customer-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"
    assert client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Preview Customer",
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
        json={"name": "Preview Tenant"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert tenant.status_code == 201, tenant.text
    return tenant.json()["id"]


def _create_admin(client) -> tuple[str, str, str]:
    from app.db.session import SessionLocal

    email = f"preview-admin-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"
    db = SessionLocal()
    try:
        admin = User(
            email=email,
            full_name="Preview Admin",
            password_hash=get_password_hash(password),
            is_admin=True,
            is_active=True,
            email_verified=True,
        )
        db.add(admin)
        db.commit()
        admin_id = str(admin.id)
    finally:
        db.close()
    return email, password, admin_id


def _login_admin(client, email: str, password: str, portal: str) -> str:
    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
            "portal": portal,
            "admin_session_note": "customer preview regression test" if portal == "super_admin" else None,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_super_admin_can_preview_tenant_without_membership_and_action_is_audited(client):
    from app.db.session import SessionLocal

    tenant_id = _create_tenant(client)
    email, password, admin_id = _create_admin(client)
    admin_token = _login_admin(client, email, password, "super_admin")
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-ID": tenant_id,
    }

    preview = client.post(f"/admin/tenants/{tenant_id}/preview", headers=headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()["id"] == tenant_id

    context = client.get("/api/me", headers=headers)
    assert context.status_code == 200, context.text
    assert context.json()["tenant"]["id"] == tenant_id

    action_center = client.get("/analytics/action-center", headers=headers)
    assert action_center.status_code == 200, action_center.text

    usage = client.get("/subscription/usage", headers=headers)
    assert usage.status_code == 200, usage.text

    db = SessionLocal()
    try:
        audit = db.query(AuditLog).filter(
            AuditLog.user_id == uuid.UUID(admin_id),
            AuditLog.action == "admin.tenant.preview.start",
            AuditLog.resource_id == tenant_id,
        ).first()
        assert audit is not None
    finally:
        db.close()


def test_admin_tenant_portal_cannot_preview_an_unrelated_tenant(client):
    tenant_id = _create_tenant(client)
    email, password, _ = _create_admin(client)
    previous_require_2fa = settings.SUPER_ADMIN_REQUIRE_2FA
    settings.SUPER_ADMIN_REQUIRE_2FA = False
    try:
        tenant_portal_token = _login_admin(client, email, password, "tenant")
        response = client.get(
            "/analytics/action-center",
            headers={
                "Authorization": f"Bearer {tenant_portal_token}",
                "X-Tenant-ID": tenant_id,
            },
        )
    finally:
        settings.SUPER_ADMIN_REQUIRE_2FA = previous_require_2fa

    assert response.status_code == 403, response.text
    assert "süper admin" in response.json()["detail"].lower()
