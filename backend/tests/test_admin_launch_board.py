from __future__ import annotations

import re
import uuid

from app.core.security import get_password_hash
from app.models.user import User


def _extract_6_digit_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match, f"Could not extract verification code from message: {message!r}"
    return match.group(1)


def _create_and_login_super_admin(client) -> str:
    from app.db import session as session_module

    email = f"launch-admin-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"

    db = session_module.SessionLocal()
    try:
        user = User(
            email=email,
            full_name="Launch Board Admin",
            password_hash=get_password_hash(password),
            is_admin=True,
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
            "portal": "super_admin",
            "admin_session_note": "launch board",
        },
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _register_login_and_create_tenant(client) -> tuple[str, str]:
    email = f"launch-user-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"

    register = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Launch User", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-07-22", "privacy_version": "2026-07-22", "kvkk_notice_version": "2026-07-22"},
    )
    assert register.status_code == 201, register.text

    request_code = client.post("/auth/email-verification/request", json={"email": email})
    assert request_code.status_code == 200, request_code.text
    code = _extract_6_digit_code(request_code.json().get("message", ""))
    confirm_code = client.post("/auth/email-verification/confirm", json={"email": email, "code": code})
    assert confirm_code.status_code == 200, confirm_code.text

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    access_token = login.json()["access_token"]

    tenant = client.post(
        "/tenants",
        json={"name": "Launch Board Tenant"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert tenant.status_code == 201, tenant.text
    return access_token, tenant.json()["id"]


def test_admin_launch_board_shows_concierge_pipeline(client):
    _, tenant_id = _register_login_and_create_tenant(client)
    admin_token = _create_and_login_super_admin(client)

    response = client.get(
        "/admin/launch-board",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    item = next((row for row in payload["items"] if row["tenant_id"] == tenant_id), None)
    assert item is not None
    assert item["launch_stage"] == "concierge"
    assert item["business_profile_status"] == "needs_enrichment"
    assert item["concierge_status"] == "pending"
    assert item["setup_mode"] == "concierge"
    assert item["concierge_ticket_id"]
    assert item["bot_count"] == 0
    assert item["latest_setup_run_status"] is None
    assert payload["pending_concierge"] >= 1


def test_admin_can_enrich_run_autopilot_and_launch_tenant(client, monkeypatch):
    _, tenant_id = _register_login_and_create_tenant(client)
    admin_token = _create_and_login_super_admin(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    concierge = client.patch(
        f"/admin/launch-board/{tenant_id}/concierge",
        json={"status": "in_progress", "note": "Bilgi formasyonu başlatıldı", "create_ticket": True},
        headers=headers,
    )
    assert concierge.status_code == 200, concierge.text
    assert concierge.json()["concierge_status"] == "in_progress"
    assert concierge.json()["concierge_ticket_id"]

    profile = client.patch(
        f"/admin/tenants/{tenant_id}/business-profile",
        json={
            "industry": "clinic",
            "tone": "professional",
            "summary": "Diş kliniği; randevu, fiyat ve tedavi bilgisi taleplerini yönetir.",
            "services": ["implant", "ortodonti"],
            "faq": [{"question": "Çalışma saatleri?", "answer": "Hafta içi 09:00-18:00"}],
            "status": "ready",
        },
        headers=headers,
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["business_profile_status"] == "ready"
    assert profile.json()["concierge_status"] == "ready_for_review"

    autopilot = client.post(f"/admin/tenants/{tenant_id}/autopilot/run", headers=headers)
    assert autopilot.status_code == 200, autopilot.text
    assert autopilot.json()["tenant_id"] == tenant_id
    assert autopilot.json()["health_score"] >= 0

    monkeypatch.setattr(
        "app.api.routers.admin.SystemVerificationService.run",
        lambda self, tenant, user: {
            "ready_for_launch": True,
            "status": "ready",
            "score": 100,
            "run_id": "test-verification-run",
            "failed_critical": [],
        },
    )

    launch = client.post(f"/admin/tenants/{tenant_id}/launch", headers=headers)
    assert launch.status_code == 200, launch.text
    assert launch.json()["concierge_status"] == "launched"
    assert launch.json()["business_profile_status"] == "ready"
