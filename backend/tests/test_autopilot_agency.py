import re
from uuid import UUID


def _extract_6_digit_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match, f"Could not extract verification code from message: {message!r}"
    return match.group(1)


def _auth_headers(access_token: str, tenant_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id
    return headers


def _register_verify_login_and_create_tenant(client, email: str = "autopilot@example.com", tenant_name: str = "Autopilot Tenant"):
    password = "Password123!"
    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Autopilot User", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-07-22", "privacy_version": "2026-07-22", "kvkk_notice_version": "2026-07-22"},
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
        json={"name": tenant_name},
        headers=_auth_headers(access_token),
    )
    assert tenant_resp.status_code == 201, tenant_resp.text
    return access_token, tenant_resp.json()["id"]


def test_autopilot_run_is_idempotent_and_exposes_diagnostics(client):
    from app.db.session import SessionLocal
    from app.models.bot import Bot
    from app.models.knowledge import BotKnowledgeItem

    access_token, tenant_id = _register_verify_login_and_create_tenant(client)
    headers = _auth_headers(access_token, tenant_id)

    initial_status = client.get("/setup/autopilot/status", headers=headers)
    assert initial_status.status_code == 200, initial_status.text
    assert initial_status.json()["safe_to_autorun"] is True

    first_run = client.post("/setup/autopilot/run", headers=headers)
    assert first_run.status_code == 200, first_run.text
    assert first_run.json()["latest_run"]["status"] == "completed"

    second_run = client.post("/setup/autopilot/run", headers=headers)
    assert second_run.status_code == 200, second_run.text

    verification = client.post("/setup/autopilot/verify", headers=headers)
    assert verification.status_code == 200, verification.text
    assert verification.json()["status"] == "blocked"
    assert "business_profile" in verification.json()["failed_critical"]
    assert any(item["key"] == "database" for item in verification.json()["checks"])

    status_after_verification = client.get("/setup/autopilot/status", headers=headers)
    assert status_after_verification.status_code == 200, status_after_verification.text
    assert status_after_verification.json()["latest_verification"]["score"] == verification.json()["score"]

    prepared_bots = client.get("/bots", headers=headers)
    assert prepared_bots.status_code == 200, prepared_bots.text
    assert prepared_bots.json()[0]["name"] == "Autopilot Tenant Asistanı"
    bot_id = prepared_bots.json()[0]["id"]
    customized = client.put(
        f"/bots/{bot_id}",
        json={"name": "Özel Satış Asistanı"},
        headers=headers,
    )
    assert customized.status_code == 200, customized.text
    third_run = client.post("/setup/autopilot/run", headers=headers)
    assert third_run.status_code == 200, third_run.text

    db = SessionLocal()
    try:
        bots = db.query(Bot).filter(Bot.tenant_id == UUID(tenant_id)).all()
        assert len(bots) == 1
        assert bots[0].name == "Özel Satış Asistanı"
        knowledge_items = db.query(BotKnowledgeItem).filter(BotKnowledgeItem.bot_id == bots[0].id).all()
        assert {item.title for item in knowledge_items} == {"İşletme bilgi formasyonu"}
    finally:
        db.close()

    diagnostics = client.get("/integrations/diagnostics", headers=headers)
    assert diagnostics.status_code == 200, diagnostics.text
    providers = {item["provider"] for item in diagnostics.json()["items"]}
    assert {"openai", "n8n", "whatsapp", "google", "billing", "email", "artifacts"}.issubset(providers)

    repair = client.post("/integrations/whatsapp/repair", headers=headers)
    assert repair.status_code == 200, repair.text
    assert repair.json()["status"] == "requires_user_action"


def test_agency_clients_include_current_tenant_health(client):
    access_token, tenant_id = _register_verify_login_and_create_tenant(client)
    headers = _auth_headers(access_token, tenant_id)

    run = client.post("/setup/autopilot/run", headers=headers)
    assert run.status_code == 200, run.text

    clients = client.get("/agency/clients", headers=headers)
    assert clients.status_code == 200, clients.text
    items = clients.json()["items"]
    assert len(items) == 1
    assert items[0]["tenant_id"] == tenant_id
    assert "health_score" in items[0]

    health = client.get(f"/agency/clients/{tenant_id}/health", headers=headers)
    assert health.status_code == 200, health.text
    assert health.json()["found"] is True
    assert health.json()["client"]["tenant_id"] == tenant_id


def test_agency_client_relationship_crud(client):
    access_token, agency_tenant_id = _register_verify_login_and_create_tenant(client)
    agency_headers = _auth_headers(access_token, agency_tenant_id)
    _, client_tenant_id = _register_verify_login_and_create_tenant(
        client,
        email="managed-client@example.com",
        tenant_name="Managed Client Tenant",
    )

    create_resp = client.post(
        "/agency/clients",
        json={"client_tenant_id": client_tenant_id, "notes": "VIP müşteri"},
        headers=agency_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    relationship_id = create_resp.json()["client"]["relationship_id"]

    clients_resp = client.get("/agency/clients", headers=agency_headers)
    assert clients_resp.status_code == 200, clients_resp.text
    assert [item["tenant_id"] for item in clients_resp.json()["items"]] == [client_tenant_id]

    update_resp = client.patch(
        f"/agency/clients/{relationship_id}",
        json={"status": "paused", "notes": "Beklemede"},
        headers=agency_headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["client"]["status"] == "paused"

    delete_resp = client.delete(f"/agency/clients/{relationship_id}", headers=agency_headers)
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json()["client"]["status"] == "archived"


def test_scheduled_job_lock_prevents_duplicate_runs(client):
    _ = client
    from app.db.session import SessionLocal
    from app.services.scheduled_job_service import ScheduledJobService

    db = SessionLocal()
    try:
        first = ScheduledJobService(db, owner="worker-a").acquire("diagnostics", 300, lock_seconds=120)
        assert first is not None

        second = ScheduledJobService(db, owner="worker-b").acquire("diagnostics", 300, lock_seconds=120)
        assert second is None

        ScheduledJobService(db, owner="worker-a").mark_success(first)

        third = ScheduledJobService(db, owner="worker-b").acquire("diagnostics", 300, lock_seconds=120)
        assert third is None
    finally:
        db.close()


def test_scheduled_job_failure_rolls_back_before_recording_retry(client, monkeypatch):
    from unittest.mock import Mock

    from app.db.session import SessionLocal
    from app.services.scheduled_job_service import ScheduledJobService

    db = SessionLocal()
    try:
        service = ScheduledJobService(db, owner="worker-a")
        job = service.acquire("failure-recovery", 300, lock_seconds=120)
        assert job is not None

        original_rollback = db.rollback
        rollback_spy = Mock(side_effect=original_rollback)
        monkeypatch.setattr(db, "rollback", rollback_spy)

        service.mark_failure(job, RuntimeError("provider unavailable"))

        rollback_spy.assert_called_once()
        db.refresh(job)
        assert job.status == "retrying"
        assert job.retry_count == 1
        assert job.last_error == "provider unavailable"
    finally:
        db.close()


def test_worker_schema_wait_accepts_matching_heads(monkeypatch):
    from app import worker

    monkeypatch.setattr(worker, "_expected_migration_heads", lambda: {"037"})
    monkeypatch.setattr(worker, "_database_migration_heads", lambda: {"037"})

    worker._wait_for_database_schema(timeout_seconds=1, poll_seconds=0)
