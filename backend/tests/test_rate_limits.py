from fastapi import Request

from app.core.rate_limit import client_ip


def test_register_rate_limit_blocks_repeated_attempts(client):
    payload = {"email": "ratelimit@example.com", "password": "Password123!", "full_name": "Rate Limit"}
    headers = {"X-Forwarded-For": "203.0.113.10"}

    statuses = [client.post("/auth/register", json=payload, headers=headers).status_code for _ in range(6)]

    assert statuses[0] == 201
    assert 429 in statuses
    assert statuses[-1] == 429


def test_whatsapp_webhook_rate_limit_blocks_flood(client):
    from app.core import rate_limit as rate_limit_module

    old_max = rate_limit_module.webhook_rate_limiter.max_attempts
    rate_limit_module.webhook_rate_limiter.clear()
    rate_limit_module.webhook_rate_limiter.max_attempts = 1
    try:
        headers = {"X-Forwarded-For": "203.0.113.11"}
        payload = {"object": "not_whatsapp"}
        first = client.post("/whatsapp/webhook", json=payload, headers=headers)
        second = client.post("/whatsapp/webhook", json=payload, headers=headers)
    finally:
        rate_limit_module.webhook_rate_limiter.max_attempts = old_max
        rate_limit_module.webhook_rate_limiter.clear()

    assert first.status_code == 200, first.text
    assert second.status_code == 429, second.text


def test_client_ip_prefers_forwarded_for(client):
    @client.app.get("/_test/client-ip", include_in_schema=False)
    async def _client_ip_endpoint(request: Request):  # pragma: no cover - exercised through TestClient
        return {"ip": client_ip(request)}

    resp = client.get("/_test/client-ip", headers={"X-Forwarded-For": "198.51.100.20, 10.0.0.1"})
    assert resp.status_code == 200
    assert resp.json()["ip"] == "198.51.100.20"


def test_global_rate_limit_returns_429_without_500(client):
    from app.core import rate_limit as rate_limit_module

    old_max = rate_limit_module.global_ip_rate_limiter.max_attempts
    rate_limit_module.global_ip_rate_limiter.clear()
    rate_limit_module.global_ip_rate_limiter.max_attempts = 1
    try:
        headers = {"X-Forwarded-For": "203.0.113.12"}
        first = client.get("/api/me", headers=headers)
        second = client.get("/api/me", headers=headers)
    finally:
        rate_limit_module.global_ip_rate_limiter.max_attempts = old_max
        rate_limit_module.global_ip_rate_limiter.clear()

    assert first.status_code in {401, 403}
    assert second.status_code == 429
    assert second.json()["detail"].startswith("Çok fazla istek")
