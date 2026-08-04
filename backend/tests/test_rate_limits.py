from fastapi import Request
import asyncio
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.rate_limit import RateLimiter, client_ip


class _FakeRedisClient:
    def __init__(self):
        self.counts: dict[str, int] = {}

    def eval(self, _script, _key_count, key, _window):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


def test_redis_rate_limiter_is_shared_by_hashed_key(monkeypatch):
    from app.core import rate_limit as rate_limit_module

    fake_client = _FakeRedisClient()
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(rate_limit_module, "redis", object())
    first_instance = RateLimiter(2, 60, "distributed-test")
    second_instance = RateLimiter(2, 60, "distributed-test")
    first_instance._redis_client = fake_client
    second_instance._redis_client = fake_client

    assert first_instance.allow("tenant:secret-user-key") is True
    assert second_instance.allow("tenant:secret-user-key") is True
    assert first_instance.allow("tenant:secret-user-key") is False
    stored_key = next(iter(fake_client.counts))
    assert "secret-user-key" not in stored_key


def test_redis_failure_falls_back_to_memory(monkeypatch):
    from app.core import rate_limit as rate_limit_module

    class _UnavailableRedis:
        def eval(self, *_args):
            raise ConnectionError("offline")

    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_FAIL_CLOSED", False)
    monkeypatch.setattr(rate_limit_module, "redis", object())
    limiter = RateLimiter(1, 60, "fallback-test")
    limiter._redis_client = _UnavailableRedis()

    assert limiter.allow("same-key") is True
    assert limiter.allow("same-key") is False


def test_redis_failure_rejects_requests_when_fail_closed(monkeypatch):
    from app.core import rate_limit as rate_limit_module

    class _UnavailableRedis:
        def eval(self, *_args):
            raise ConnectionError("offline")

    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_FAIL_CLOSED", True)
    monkeypatch.setattr(rate_limit_module, "redis", object())
    limiter = RateLimiter(10, 60, "fail-closed-test")
    limiter._redis_client = _UnavailableRedis()

    assert limiter.allow("same-key") is False


def test_register_rate_limit_blocks_repeated_attempts(client):
    payload = {"email": "ratelimit@example.com", "password": "Password123!", "full_name": "Rate Limit", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-08-04", "privacy_version": "2026-08-04", "kvkk_notice_version": "2026-08-04"}
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


def test_client_ip_ignores_spoofed_forwarding_from_untrusted_peer(monkeypatch):
    from app.core import rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module.settings, "ENVIRONMENT", "prod")
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"1.2.3.4")],
        "client": ("198.51.100.50", 443),
    })

    assert client_ip(request) == "198.51.100.50"


def test_client_ip_uses_rightmost_public_address_behind_trusted_proxy(monkeypatch):
    from app.core import rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module.settings, "ENVIRONMENT", "prod")
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"1.2.3.4, 203.0.113.9")],
        "client": ("10.0.0.5", 443),
    })

    assert client_ip(request) == "203.0.113.9"


def test_api_security_headers_and_request_id(client):
    request_id = "security-test-123"
    response = client.get("/health", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


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


def test_whatsapp_outbound_tenant_rate_limit(client, monkeypatch):
    from app.core import rate_limit as rate_limit_module
    from app.models.whatsapp_account import WhatsAppAccount
    from app.services.openwa_client import openwa_client
    from app.services.whatsapp_gateway_service import whatsapp_gateway_service

    _ = client
    old_max = rate_limit_module.whatsapp_send_minute_rate_limiter.max_attempts
    rate_limit_module.whatsapp_send_minute_rate_limiter.clear()
    rate_limit_module.whatsapp_send_minute_rate_limiter.max_attempts = 1
    monkeypatch.setattr(
        openwa_client,
        "send_text",
        AsyncMock(return_value={"messageId": "outbound-1"}),
    )
    account = WhatsAppAccount(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        provider="openwa",
        provider_session_id="82d1023f-998b-4ada-bf1c-a1e192e933c6",
        token_status="active",
        webhook_status="verified",
        is_active=True,
        is_verified=True,
    )
    try:
        first = asyncio.run(
            whatsapp_gateway_service.send_text(account, to="+905551112233", text="Bir")
        )
        assert first["message_id"] == "outbound-1"
        with pytest.raises(RuntimeError, match="Dakikalık"):
            asyncio.run(
                whatsapp_gateway_service.send_text(account, to="+905551112233", text="İki")
            )
    finally:
        rate_limit_module.whatsapp_send_minute_rate_limiter.max_attempts = old_max
        rate_limit_module.whatsapp_send_minute_rate_limiter.clear()
