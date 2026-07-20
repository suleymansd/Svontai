#!/usr/bin/env python3
"""Production smoke checks for Railway backend and Vercel frontend.

Environment:
  BACKEND_URL or SMARTWA_BACKEND_URL: Railway API base URL
  FRONTEND_URL or SMARTWA_FRONTEND_URL: Vercel frontend base URL
  SMARTWA_SMOKE_ACCESS_TOKEN: optional short-lived bearer token for protected checks
  SMARTWA_SMOKE_EMAIL/SMARTWA_SMOKE_PASSWORD: preferred credentials for a fresh smoke login
  SMARTWA_SMOKE_TENANT_ID: optional tenant context for protected checks
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any


TIMEOUT_SECONDS = 15


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


def _base_url(*names: str) -> str | None:
    for name in names:
        value = (os.getenv(name) or "").strip().rstrip("/")
        if value:
            return value
    return None


def _canonical_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if host == "localhost":
        host = "127.0.0.1"
    port = parsed.port
    default_port = 443 if scheme == "https" else 80
    netloc = host if not port or port == default_port else f"{host}:{port}"
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))


def _request(
    url: str,
    token: str | None = None,
    tenant_id: str | None = None,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[int, str, Any]:
    headers = {"User-Agent": "SmartWA-prod-smoke/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(200_000).decode("utf-8", errors="replace")
            parsed = None
            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                parsed = json.loads(body or "{}")
            return response.status, body, parsed
    except urllib.error.HTTPError as exc:
        body = exc.read(20_000).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body or "{}")
        except json.JSONDecodeError:
            parsed = None
        return exc.code, body, parsed


def _login_for_smoke(backend_url: str, email: str, password: str) -> tuple[str, str | None]:
    status, body, parsed = _request(
        f"{backend_url}/auth/login",
        method="POST",
        payload={"email": email, "password": password, "portal": "tenant"},
    )
    if status != 200 or not isinstance(parsed, dict) or not isinstance(parsed.get("access_token"), str):
        raise RuntimeError(f"smoke login failed: status={status}, body={body[:200]!r}")

    token = parsed["access_token"]
    status, body, me = _request(f"{backend_url}/api/me", token=token)
    if status != 200 or not isinstance(me, dict):
        raise RuntimeError(f"smoke tenant lookup failed: status={status}, body={body[:200]!r}")
    tenant = me.get("tenant")
    tenant_id = str(tenant.get("id")) if isinstance(tenant, dict) and tenant.get("id") else None
    return token, tenant_id


def _check_public(name: str, url: str, expected_statuses: set[int] | None = None, text: str | None = None) -> Result:
    expected = expected_statuses or {200}
    try:
        status, body, _ = _request(url)
    except Exception as exc:
        return Result(name, False, f"request failed: {exc}")
    if status not in expected:
        return Result(name, False, f"status={status}")
    if text and text.lower() not in body.lower():
        return Result(name, False, f"status={status}, missing text={text!r}")
    return Result(name, True, f"status={status}")


def _check_json(name: str, url: str, token: str | None = None, tenant_id: str | None = None) -> Result:
    try:
        status, body, parsed = _request(url, token=token, tenant_id=tenant_id)
    except Exception as exc:
        return Result(name, False, f"request failed: {exc}")
    if status != 200:
        return Result(name, False, f"status={status}, body={body[:300]!r}")
    if parsed is None:
        return Result(name, False, "response was not JSON")
    return Result(name, True, f"status=200 keys={','.join(sorted(parsed.keys())[:6])}")


def _check_json_shape(
    name: str,
    url: str,
    *,
    token: str,
    tenant_id: str | None = None,
    validator: Callable[[Any], str | None] | None = None,
) -> Result:
    try:
        status, body, parsed = _request(url, token=token, tenant_id=tenant_id)
    except Exception as exc:
        return Result(name, False, f"request failed: {exc}")
    if status != 200:
        return Result(name, False, f"status={status}, body={body[:300]!r}")
    if parsed is None:
        return Result(name, False, "response was not JSON")
    if validator:
        message = validator(parsed)
        if message:
            return Result(name, False, message)
    if isinstance(parsed, dict):
        detail = f"dict keys={','.join(sorted(parsed.keys())[:6])}"
    elif isinstance(parsed, list):
        detail = f"list length={len(parsed)}"
    else:
        detail = type(parsed).__name__
    return Result(name, True, f"status=200 {detail}")


def _check_frontend_backend_config(frontend_url: str, backend_url: str) -> Result:
    url = f"{frontend_url}/api/frontend-config"
    try:
        status, body, parsed = _request(url)
    except Exception as exc:
        return Result("frontend backend config", False, f"request failed: {exc}")
    if status != 200:
        return Result("frontend backend config", False, f"status={status}, body={body[:300]!r}")
    if not isinstance(parsed, dict):
        return Result("frontend backend config", False, "response was not JSON object")
    frontend_backend_url = parsed.get("backendUrl")
    if not isinstance(frontend_backend_url, str) or not frontend_backend_url:
        return Result("frontend backend config", False, "missing backendUrl")
    expected = _canonical_url(backend_url)
    actual = _canonical_url(frontend_backend_url)
    if actual != expected:
        return Result(
            "frontend backend config",
            False,
            f"frontend points to {frontend_backend_url!r}, expected {backend_url!r}",
        )
    return Result("frontend backend config", True, f"backendUrl={frontend_backend_url}")


def _expect_dict_keys(*keys: str) -> Callable[[Any], str | None]:
    def _validator(value: Any) -> str | None:
        if not isinstance(value, dict):
            return f"expected JSON object, got {type(value).__name__}"
        missing = [key for key in keys if key not in value]
        if missing:
            return f"missing keys={','.join(missing)}"
        return None

    return _validator


def _expect_list(value: Any) -> str | None:
    if not isinstance(value, list):
        return f"expected JSON list, got {type(value).__name__}"
    return None


def _expect_items_list(value: Any) -> str | None:
    if not isinstance(value, dict):
        return f"expected JSON object, got {type(value).__name__}"
    if not isinstance(value.get("items"), list):
        return "missing list key=items"
    return None


def run() -> int:
    backend_url = _base_url("SMARTWA_BACKEND_URL", "BACKEND_URL")
    frontend_url = _base_url("SMARTWA_FRONTEND_URL", "FRONTEND_URL")
    token = (os.getenv("SMARTWA_SMOKE_ACCESS_TOKEN") or "").strip() or None
    tenant_id = (os.getenv("SMARTWA_SMOKE_TENANT_ID") or "").strip() or None
    smoke_email = (os.getenv("SMARTWA_SMOKE_EMAIL") or "").strip()
    smoke_password = (os.getenv("SMARTWA_SMOKE_PASSWORD") or "").strip()

    if not backend_url and not frontend_url:
        print("Set BACKEND_URL/SMARTWA_BACKEND_URL and/or FRONTEND_URL/SMARTWA_FRONTEND_URL.", file=sys.stderr)
        return 2

    results: list[Result] = []
    started = time.time()

    if backend_url:
        results.append(_check_json("backend /health/ready", f"{backend_url}/health/ready"))
        results.append(_check_json("backend /", f"{backend_url}/"))
        if not token and smoke_email and smoke_password:
            try:
                token, discovered_tenant_id = _login_for_smoke(backend_url, smoke_email, smoke_password)
                tenant_id = tenant_id or discovered_tenant_id
                results.append(Result("protected smoke login", True, "fresh access token issued"))
            except Exception as exc:
                results.append(Result("protected smoke login", False, str(exc)))
        if token:
            if not tenant_id:
                results.append(Result("protected tenant context", False, "no tenant found for smoke account"))
            protected_checks: list[tuple[str, str, Callable[[Any], str | None]]] = [
                ("me context", "/api/me", _expect_dict_keys("user")),
                ("onboarding setup status", "/onboarding/setup/status", _expect_dict_keys("current_step", "steps")),
                ("whatsapp provider status", "/api/onboarding/whatsapp/status", _expect_dict_keys("whatsapp_connected", "openwa_enabled")),
                ("autopilot status", "/setup/autopilot/status", _expect_dict_keys("status", "health_score")),
                ("integration diagnostics", "/integrations/diagnostics", _expect_dict_keys("items", "health_score")),
                ("agency clients", "/agency/clients", _expect_items_list),
                ("voice settings", "/voice-automation/settings", _expect_dict_keys("enabled", "provider")),
                ("voice intents", "/voice-automation/intents", _expect_list),
                ("voice jobs", "/voice-automation/jobs", _expect_list),
                ("calls", "/calls", _expect_list),
                ("bots", "/bots", _expect_list),
                ("leads", "/leads", _expect_list),
                ("appointments", "/appointments", _expect_list),
            ]
            for name, path, validator in protected_checks:
                results.append(
                    _check_json_shape(
                        name,
                        f"{backend_url}{path}",
                        token=token,
                        tenant_id=tenant_id,
                        validator=validator,
                    )
                )
        else:
            results.append(
                Result(
                    "protected API checks",
                    True,
                    "skipped: set SMARTWA_SMOKE_EMAIL/PASSWORD (preferred) or SMARTWA_SMOKE_ACCESS_TOKEN",
                )
            )

    if frontend_url:
        results.append(_check_public("frontend /", f"{frontend_url}/", text="SvontAI"))
        results.append(_check_public("frontend /pricing", f"{frontend_url}/pricing"))
        results.append(_check_public("frontend /tools", f"{frontend_url}/tools"))
        results.append(_check_public("frontend /security", f"{frontend_url}/security"))
        if backend_url:
            results.append(_check_frontend_backend_config(frontend_url, backend_url))

    failed = [result for result in results if not result.ok]
    for result in results:
        prefix = "OK" if result.ok else "FAIL"
        print(f"[{prefix}] {result.name}: {result.detail}")

    print(f"Completed in {time.time() - started:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
