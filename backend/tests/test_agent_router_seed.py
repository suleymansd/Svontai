from __future__ import annotations

import uuid

from app.core.security import get_password_hash
from app.models.tool import Tool
from app.models.user import User
from app.services.tool_seed_service import seed_initial_tools


def test_seed_initial_tools_creates_agent_router_once(client):
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        first = seed_initial_tools(db)
        second = seed_initial_tools(db)
        assert first["total"] >= 1
        assert second["total"] >= 1

        tool = db.query(Tool).filter(Tool.slug == "agent_router").first()
        assert tool is not None
        assert tool.key == "agent_router"
        assert tool.n8n_workflow_id == "svontai-tool-runner"
        assert tool.required_plan == "free"
        assert tool.required_integrations_json == ["openai"]

        total = db.query(Tool).filter(Tool.slug == "agent_router").count()
        assert total == 1
    finally:
        db.close()


def test_admin_tools_list_contains_agent_router(client):
    from app.db import session as session_module

    email = f"agent-router-admin-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"
    db = session_module.SessionLocal()
    try:
        user = User(
            email=email,
            full_name="Agent Router Admin",
            password_hash=get_password_hash(password),
            is_admin=True,
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        db.commit()

        seed_initial_tools(db)
    finally:
        db.close()

    login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
            "portal": "super_admin",
            "admin_session_note": "agent_router_seed_check",
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    response = client.get("/admin/tools", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "items" in payload
    assert any(item.get("slug") == "agent_router" for item in payload["items"])
