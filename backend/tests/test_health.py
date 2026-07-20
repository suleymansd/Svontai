def test_health_endpoints_report_liveness_and_readiness(client):
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"

    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["components"]["database"] == "ok"

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
