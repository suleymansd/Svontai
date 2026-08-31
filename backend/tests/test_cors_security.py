from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.cors import StrictCORSMiddleware


def _preflight_headers(origin: str, method: str = "POST") -> dict[str, str]:
    return {
        "Origin": origin,
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "authorization,content-type",
    }


def test_cors_allows_only_the_configured_frontend(client):
    trusted_origin = settings.FRONTEND_URL.strip().rstrip("/")
    response = client.options(
        "/auth/login",
        headers=_preflight_headers(trusted_origin),
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == trusted_origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["vary"] == "Origin"


def test_cors_rejects_unknown_preflight_without_cors_headers(client):
    response = client.options(
        "/auth/login",
        headers=_preflight_headers("https://attacker.example"),
    )

    assert response.status_code == 403
    assert response.headers["vary"] == "Origin"
    assert not any(name.startswith("access-control-") for name in response.headers)


def test_cors_rejects_unknown_simple_browser_request(client):
    response = client.get(
        "/health/live",
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert not any(name.startswith("access-control-") for name in response.headers)


def test_cors_keeps_originless_service_requests_working(client):
    response = client.get("/health/live")

    assert response.status_code == 200
    assert not any(name.startswith("access-control-") for name in response.headers)


def test_widget_origin_is_credential_free_and_public_path_only():
    test_app = FastAPI()

    @test_app.get("/public/ping")
    def public_ping():
        return {"ok": True}

    @test_app.get("/private/ping")
    def private_ping():
        return {"ok": True}

    wrapped = StrictCORSMiddleware(
        test_app,
        trusted_origins=["https://app.svontai.test"],
        widget_origins=["https://customer.example"],
    )

    with TestClient(wrapped) as test_client:
        public_response = test_client.get(
            "/public/ping",
            headers={"Origin": "https://customer.example"},
        )
        private_response = test_client.get(
            "/private/ping",
            headers={"Origin": "https://customer.example"},
        )

    assert public_response.status_code == 200
    assert public_response.headers["access-control-allow-origin"] == "https://customer.example"
    assert "access-control-allow-credentials" not in public_response.headers
    assert private_response.status_code == 403
    assert not any(name.startswith("access-control-") for name in private_response.headers)
