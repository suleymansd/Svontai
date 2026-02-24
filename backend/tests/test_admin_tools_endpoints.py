from __future__ import annotations

import uuid

from app.core.security import get_password_hash
from app.models.tool import Tool
from app.models.user import User
from app.services.tool_seed_service import seed_initial_tools


def _create_and_login_super_admin(client) -> str:
    from app.db import session as session_module

    email = f"admin-tools-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"

    db = session_module.SessionLocal()
    try:
        user = User(
            email=email,
            full_name="Admin Tools Tester",
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
            "admin_session_note": "tool patch",
        },
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _seed_tools_and_get_first_id() -> str:
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        seed_initial_tools(db)
        tool = db.query(Tool).order_by(Tool.created_at.asc()).first()
        assert tool is not None
        return str(tool.id)
    finally:
        db.close()


def test_admin_tools_list_returns_items(client):
    token = _create_and_login_super_admin(client)
    _seed_tools_and_get_first_id()

    response = client.get("/admin/tools", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert "total" in payload
    assert "page" in payload
    assert "page_size" in payload


def test_admin_tools_get_by_id(client):
    token = _create_and_login_super_admin(client)
    tool_id = _seed_tools_and_get_first_id()

    response = client.get(f"/admin/tools/{tool_id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == tool_id
    assert "key" in payload
    assert "n8n_workflow_id" in payload


def test_admin_tools_patch_updates_n8n_workflow_id(client):
    token = _create_and_login_super_admin(client)
    tool_id = _seed_tools_and_get_first_id()

    response = client.patch(
        f"/admin/tools/{tool_id}",
        json={"n8n_workflow_id": "svontai-meeting-summary"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == tool_id
    assert payload["n8n_workflow_id"] == "svontai-meeting-summary"

    verify = client.get(f"/admin/tools/{tool_id}", headers={"Authorization": f"Bearer {token}"})
    assert verify.status_code == 200, verify.text
    assert verify.json()["n8n_workflow_id"] == "svontai-meeting-summary"
