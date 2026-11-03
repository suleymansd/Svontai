def test_health_endpoints_report_liveness_and_readiness(client):
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"

    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["components"]["database"] == "ok"
    assert isinstance(ready.json()["deployment"]["migration_heads"], list)
    assert "api_commit" in ready.json()["deployment"]
    assert "worker_commit" in ready.json()["deployment"]

    compatibility = client.get("/health")
    assert compatibility.status_code == 200
    assert compatibility.json()["status"] == "ready"


def test_health_ready_returns_503_without_exposing_exception(client, monkeypatch):
    from app.core import health as health_module

    async def unavailable():
        return False, {
            "status": "not_ready",
            "environment": "test",
            "components": {"database": "unavailable", "redis": "not_required"},
        }

    monkeypatch.setattr(health_module, "readiness_status", unavailable)
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "environment": "test",
        "components": {"database": "unavailable", "redis": "not_required"},
    }


def test_health_reports_worker_release_heartbeat(client, monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "a" * 40)

    from app.db import session as session_module
    from app import worker as worker_module

    monkeypatch.setattr(worker_module, "SessionLocal", session_module.SessionLocal)

    worker_module._record_worker_heartbeat()
    response = client.get("/health/ready")

    assert response.status_code == 200
    deployment = response.json()["deployment"]
    assert deployment["api_commit"] == "a" * 40
    assert deployment["worker_commit"] == "a" * 40
    assert deployment["worker_heartbeat_age_seconds"] <= 2


def _store_heartbeat(age_seconds: int) -> None:
    from datetime import datetime, timedelta, timezone

    from app.db import session as session_module
    from app.models.autopilot import ScheduledJob

    db = session_module.SessionLocal()
    try:
        job = db.query(ScheduledJob).filter(ScheduledJob.name == "worker_heartbeat").first()
        if job is None:
            job = ScheduledJob(name="worker_heartbeat", interval_seconds=30)
            db.add(job)
        job.last_success_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
        job.meta_json = {"release_sha": "b" * 40}
        db.commit()
    finally:
        db.close()


def test_health_ready_worker_ok_within_threshold(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "WORKER_HEARTBEAT_MAX_AGE_SECONDS", 300)
    _store_heartbeat(age_seconds=120)

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["components"]["worker"] == "ok"
    assert 118 <= body["deployment"]["worker_heartbeat_age_seconds"] <= 125
    assert body["deployment"]["worker_heartbeat_max_age_seconds"] == 300


def test_health_ready_returns_503_on_stale_worker_heartbeat(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "WORKER_HEARTBEAT_MAX_AGE_SECONDS", 300)
    _store_heartbeat(age_seconds=900)

    response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["components"]["database"] == "ok"
    assert body["components"]["worker"] == "stale"
    assert body["deployment"]["worker_heartbeat_age_seconds"] >= 900


def test_health_ready_stale_heartbeat_is_informational_when_threshold_disabled(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "WORKER_HEARTBEAT_MAX_AGE_SECONDS", 0)
    _store_heartbeat(age_seconds=900)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["components"]["worker"] == "ok"


def test_health_ready_missing_heartbeat_reports_missing_in_dev(client):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["components"]["worker"] == "missing"
    assert response.json()["deployment"]["worker_heartbeat_age_seconds"] is None


def test_health_ready_missing_heartbeat_returns_503_in_prod(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")
    monkeypatch.setattr(settings, "WORKER_HEARTBEAT_MAX_AGE_SECONDS", 300)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["components"]["worker"] == "missing"
    assert response.json()["components"]["database"] == "ok"


def test_worker_heartbeat_status_classification():
    from app.core.health import worker_heartbeat_status

    assert worker_heartbeat_status(None, 300) == "missing"
    assert worker_heartbeat_status(0, 300) == "ok"
    assert worker_heartbeat_status(300, 300) == "ok"
    assert worker_heartbeat_status(301, 300) == "stale"
    assert worker_heartbeat_status(10_000, 0) == "ok"
