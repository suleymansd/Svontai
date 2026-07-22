from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from app.core.time import utc_now_naive
from uuid import UUID

import pytest

from app.core.config import settings
from app.core.encryption import encrypt_token
from app.models.google_oauth_token import GoogleOAuthToken
from app.models.tool import Tool
from app.models.tool_run import ToolRun
from app.services.subscription_service import SubscriptionService
from app.services.tool_runner_service import ToolRunnerService
from app.services.tool_seed_service import seed_initial_tools


TOOL_CASES = [
    {
        "slug": "meeting_summary",
        "input": {"text": "Toplantı notları"},
        "expected_data_key": "summary",
    },
    {
        "slug": "report_generator",
        "input": {"text": "Aylık performans verileri"},
        "expected_data_key": "summary",
    },
]


def _extract_6_digit_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match, f"Could not extract verification code from message: {message!r}"
    return match.group(1)


def _register_and_login(client) -> tuple[str, str]:
    email = f"toolrunner-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Tool Runner", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-07-22", "privacy_version": "2026-07-22", "kvkk_notice_version": "2026-07-22"},
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
        json={"name": "Tool Runner Tenant"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert tenant_resp.status_code == 201, tenant_resp.text
    tenant_id = tenant_resp.json()["id"]

    return access_token, tenant_id


@pytest.mark.parametrize("case", TOOL_CASES, ids=[x["slug"] for x in TOOL_CASES])
def test_tool_runner_auth_guard_per_new_tool(client, case):
    payload = {
        "requestId": f"unauth-{case['slug']}",
        "toolSlug": case["slug"],
        "toolInput": case["input"],
        "context": {"locale": "tr-TR", "timezone": "Europe/Istanbul", "channel": "web", "memory": {}},
    }
    no_auth = client.post("/tools/run", json=payload)
    assert no_auth.status_code in (401, 403)


@pytest.mark.parametrize("case", TOOL_CASES, ids=[x["slug"] for x in TOOL_CASES])
def test_tool_runner_e2e_idempotent_per_new_tool(client, monkeypatch, case):
    from app.db import session as session_module

    access_token, tenant_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}

    db = session_module.SessionLocal()
    try:
        seed_result = seed_initial_tools(db)
        assert seed_result["total"] >= 1
        subscription_service = SubscriptionService(db)
        subscription_service.get_or_create_free_plan()
        subscription_service.upgrade_plan(UUID(tenant_id), "enterprise")
    finally:
        db.close()

    old_use_n8n = settings.USE_N8N
    settings.USE_N8N = True
    run_db = None

    try:
        async def _fake_runner(self, runner_workflow_id, payload, tenant_uuid, request_id):
            assert runner_workflow_id == "svontai-tool-runner"
            assert str(tenant_uuid) == tenant_id
            assert payload["tool_slug"] == case["slug"]
            return {
                "request_id": payload["request_id"],
                "executionId": f"exec-{case['slug']}",
                "success": True,
                "data": {
                    case["expected_data_key"]: f"value-for-{case['slug']}",
                    "tool_slug": case["slug"],
                },
                "error": None,
                "usage": {"time_ms": 33, "tokens": 12, "cost": 0.0001},
                "artifacts": [
                    {
                        "type": "link",
                        "name": f"artifact-{case['slug']}",
                        "url": f"https://example.com/{case['slug']}",
                        "meta": {},
                    }
                ],
            }

        monkeypatch.setattr(ToolRunnerService, "_call_n8n_runner", _fake_runner)

        request_id = f"tool-run-{case['slug']}-001"
        payload = {
            "requestId": request_id,
            "toolSlug": case["slug"],
            "toolInput": case["input"],
            "context": {"locale": "tr-TR", "timezone": "Europe/Istanbul", "channel": "web", "memory": {}},
        }

        first = client.post("/tools/run", json=payload, headers=headers)
        assert first.status_code == 200, first.text
        first_json = first.json()
        assert first_json["requestId"] == request_id
        assert first_json["success"] is True
        assert case["expected_data_key"] in first_json["data"]
        assert isinstance(first_json["artifacts"], list) and first_json["artifacts"]
        assert "/tools/artifacts/" in first_json["artifacts"][0]["url"]
        assert "sig=" in first_json["artifacts"][0]["url"]
        assert "usage" in first_json

        second = client.post("/tools/run", json=payload, headers=headers)
        assert second.status_code == 200, second.text
        assert second.json() == first_json

        run_db = session_module.SessionLocal()
        rows = run_db.query(ToolRun).filter(
            ToolRun.tenant_id == UUID(tenant_id),
            ToolRun.request_id == request_id,
        ).all()
        assert len(rows) == 1
        assert rows[0].status == "success"
        assert case["expected_data_key"] in rows[0].output_json
    finally:
        if run_db is not None:
            run_db.close()
        settings.USE_N8N = old_use_n8n


def test_tool_runner_and_admin_seed_auth_guards(client):
    no_auth_registry = client.get("/tools/registry")
    assert no_auth_registry.status_code in (401, 403)

    access_token, tenant_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}

    tenant_user_seed = client.post("/admin/tools/seed-initial", headers=headers)
    assert tenant_user_seed.status_code == 403


def test_tools_marketplace_endpoints_and_run_detail(client, monkeypatch):
    from app.db import session as session_module

    access_token, tenant_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}

    db = session_module.SessionLocal()
    try:
        seed_initial_tools(db)
        SubscriptionService(db).upgrade_plan(UUID(tenant_id), "enterprise")
    finally:
        db.close()

    old_use_n8n = settings.USE_N8N
    settings.USE_N8N = True

    try:
        async def _fake_runner(self, runner_workflow_id, payload, tenant_uuid, request_id):
            return {
                "request_id": payload["request_id"],
                "executionId": "exec-tools-listing",
                "success": True,
                "data": {"summary": "ok"},
                "error": None,
                "usage": {"time_ms": 20, "tokens": 3, "cost": 0.0},
                "artifacts": [
                    {
                        "type": "link",
                        "name": "result",
                        "url": "https://example.com/result.pdf",
                        "meta": {},
                    }
                ],
            }

        monkeypatch.setattr(ToolRunnerService, "_call_n8n_runner", _fake_runner)

        run_payload = {
            "requestId": "marketplace-run-001",
            "toolSlug": "meeting_summary",
            "toolInput": {"text": "Toplantı notları"},
            "context": {"locale": "tr-TR", "timezone": "Europe/Istanbul", "channel": "web", "memory": {}},
        }
        run_resp = client.post("/tools/run", json=run_payload, headers=headers)
        assert run_resp.status_code == 200, run_resp.text

        tools_resp = client.get("/tools", headers=headers)
        assert tools_resp.status_code == 200, tools_resp.text
        assert isinstance(tools_resp.json(), list)

        runs_resp = client.get("/tools/runs", headers=headers)
        assert runs_resp.status_code == 200, runs_resp.text
        runs = runs_resp.json()
        assert runs and runs[0]["requestId"] == "marketplace-run-001"

        detail_resp = client.get("/tools/runs/marketplace-run-001", headers=headers)
        assert detail_resp.status_code == 200, detail_resp.text
        detail_json = detail_resp.json()
        assert detail_json["requestId"] == "marketplace-run-001"
        assert detail_json["artifacts"]
        assert "/tools/artifacts/" in detail_json["artifacts"][0]["url"]
    finally:
        settings.USE_N8N = old_use_n8n


def test_integrations_status_endpoint(client):
    from app.db import session as session_module

    access_token, tenant_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}

    db = session_module.SessionLocal()
    try:
        db.add(
            GoogleOAuthToken(
                tenant_id=UUID(tenant_id),
                provider="google",
                scopes_json=[
                    "https://www.googleapis.com/auth/drive.file",
                    "https://www.googleapis.com/auth/gmail.readonly",
                ],
                access_token_encrypted=encrypt_token("test-access-token"),
                refresh_token_encrypted=None,
                expires_at=utc_now_naive() + timedelta(hours=1),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/integrations/status", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    for key in ["google_drive", "gmail", "google_sheets", "google_calendar", "openai", "ai_provider", "document_converter", "whatsapp_cloud", "n8n"]:
        assert key in payload
        assert payload[key]["status"] in ("connected", "missing", "expired")

    assert payload["google_drive"]["status"] == "connected"
    assert payload["gmail"]["status"] == "connected"
    assert payload["google_sheets"]["status"] == "missing"
    assert payload["google_calendar"]["status"] == "missing"
    assert payload["google_drive"]["required_scopes"]


def test_integrations_status_expired_google_token(client):
    from app.db import session as session_module

    access_token, tenant_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}

    db = session_module.SessionLocal()
    try:
        db.add(
            GoogleOAuthToken(
                tenant_id=UUID(tenant_id),
                provider="google",
                scopes_json=["https://www.googleapis.com/auth/calendar.events"],
                access_token_encrypted=encrypt_token("expired-token"),
                refresh_token_encrypted=None,
                expires_at=utc_now_naive() - timedelta(minutes=5),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/integrations/status", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["google_calendar"]["status"] == "expired"


def test_premium_tool_gating_for_free_plan(client):
    from app.db import session as session_module

    access_token, tenant_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}

    db = session_module.SessionLocal()
    try:
        seed_initial_tools(db)
        premium_tool = db.query(Tool).filter(Tool.slug == "meeting_summary").first()
        assert premium_tool is not None
        premium_tool.is_premium = True
        db.commit()
    finally:
        db.close()

    payload = {
        "requestId": "premium-gating-001",
        "toolSlug": "meeting_summary",
        "toolInput": {"text": "Toplantı notları"},
        "context": {"locale": "tr-TR", "timezone": "Europe/Istanbul", "channel": "web", "memory": {}},
    }
    response = client.post("/tools/run", json=payload, headers=headers)
    assert response.status_code == 403, response.text
    assert "Premium plan required" in response.json().get("detail", "")
