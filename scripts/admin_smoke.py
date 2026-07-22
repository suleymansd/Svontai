#!/usr/bin/env python3
"""No-charge admin launch-board smoke for SmartWA.

Environment:
  BACKEND_URL or SMARTWA_BACKEND_URL: API base URL, default http://127.0.0.1:8001
  SMARTWA_ADMIN_ACCESS_TOKEN: preferred super-admin bearer token
  SMARTWA_ADMIN_EMAIL and SMARTWA_ADMIN_PASSWORD: optional login fallback
  SMARTWA_SMOKE_TENANT_ID: optional existing tenant to operate on
  SMOKE_EMAIL_PREFIX: optional customer prefix when creating a disposable tenant
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any


TIMEOUT_SECONDS = 20


def _base_url() -> str:
    return (
        os.getenv("SMARTWA_BACKEND_URL")
        or os.getenv("BACKEND_URL")
        or "http://127.0.0.1:8001"
    ).strip().rstrip("/")


def _request(method: str, url: str, *, token: str | None = None, payload: dict[str, Any] | None = None) -> tuple[int, str, Any]:
    headers = {"User-Agent": "SmartWA-admin-smoke/1.0", "Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(200_000).decode("utf-8", errors="replace")
            return response.status, raw, _parse_json(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read(50_000).decode("utf-8", errors="replace")
        return exc.code, raw, _parse_json(raw)


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return None


def _expect(status: int, expected: set[int], raw: str, name: str) -> None:
    if status not in expected:
        raise RuntimeError(f"{name}: expected {sorted(expected)}, got {status}, body={raw[:300]!r}")


def _admin_token(base_url: str) -> str:
    token = (os.getenv("SMARTWA_ADMIN_ACCESS_TOKEN") or "").strip()
    if token:
        return token
    email = (os.getenv("SMARTWA_ADMIN_EMAIL") or "").strip()
    password = (os.getenv("SMARTWA_ADMIN_PASSWORD") or "").strip()
    if not email or not password:
        raise RuntimeError("Set SMARTWA_ADMIN_ACCESS_TOKEN or SMARTWA_ADMIN_EMAIL/SMARTWA_ADMIN_PASSWORD")
    status, raw, parsed = _request(
        "POST",
        f"{base_url}/auth/login",
        payload={"email": email, "password": password, "portal": "super_admin", "admin_session_note": "admin smoke"},
    )
    _expect(status, {200}, raw, "admin login")
    if not isinstance(parsed, dict) or not parsed.get("access_token"):
        raise RuntimeError("admin login did not return access_token")
    return parsed["access_token"]


def _extract_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    if not match:
        raise RuntimeError(f"could not extract verification code from message={message!r}")
    return match.group(1)


def _create_disposable_tenant(base_url: str) -> str:
    prefix = (os.getenv("SMOKE_EMAIL_PREFIX") or "admin-smoke").strip()
    domain = (os.getenv("SMOKE_DOMAIN") or "example.com").strip()
    nonce = int(time.time())
    email = f"{prefix}-{nonce}@{domain}".lower()
    password = "Password123!"

    status, raw, _ = _request(
        "POST",
        f"{base_url}/auth/register",
        payload={"email": email, "password": password, "full_name": "Admin Smoke Customer", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-07-22", "privacy_version": "2026-07-22", "kvkk_notice_version": "2026-07-22"},
    )
    _expect(status, {201}, raw, "customer register")

    status, raw, parsed = _request("POST", f"{base_url}/auth/email-verification/request", payload={"email": email})
    _expect(status, {200}, raw, "customer verification request")
    code = _extract_code(str(parsed.get("message") if isinstance(parsed, dict) else ""))

    status, raw, _ = _request("POST", f"{base_url}/auth/email-verification/confirm", payload={"email": email, "code": code})
    _expect(status, {200}, raw, "customer verification confirm")

    status, raw, parsed = _request("POST", f"{base_url}/auth/login", payload={"email": email, "password": password, "portal": "tenant"})
    _expect(status, {200}, raw, "customer login")
    if not isinstance(parsed, dict) or not parsed.get("access_token"):
        raise RuntimeError("customer login did not return access_token")

    status, raw, parsed = _request(
        "POST",
        f"{base_url}/tenants",
        token=parsed["access_token"],
        payload={"name": f"Admin Smoke Tenant {nonce}"},
    )
    _expect(status, {201}, raw, "customer tenant create")
    if not isinstance(parsed, dict) or not parsed.get("id"):
        raise RuntimeError("tenant create did not return id")
    return parsed["id"]


def run() -> int:
    base_url = _base_url()
    tenant_id = (os.getenv("SMARTWA_SMOKE_TENANT_ID") or "").strip()
    try:
        token = _admin_token(base_url)
        steps: list[str] = []
        if not tenant_id:
            tenant_id = _create_disposable_tenant(base_url)
            steps.append(f"tenant created={tenant_id}")

        status, raw, parsed = _request("GET", f"{base_url}/admin/launch-board?limit=300", token=token)
        _expect(status, {200}, raw, "launch board")
        if not isinstance(parsed, dict) or "items" not in parsed:
            raise RuntimeError("launch board response shape invalid")
        steps.append(f"launch board items={len(parsed.get('items') or [])}")

        status, raw, parsed = _request(
            "PATCH",
            f"{base_url}/admin/launch-board/{tenant_id}/concierge",
            token=token,
            payload={"status": "in_progress", "note": "Admin smoke concierge check", "create_ticket": True},
        )
        _expect(status, {200}, raw, "concierge update")
        steps.append(f"concierge={parsed.get('concierge_status') if isinstance(parsed, dict) else 'ok'}")

        status, raw, parsed = _request(
            "PATCH",
            f"{base_url}/admin/tenants/{tenant_id}/business-profile",
            token=token,
            payload={
                "industry": "service",
                "tone": "professional",
                "summary": "Admin smoke profile. No live external action.",
                "services": ["smoke-test"],
                "faq": [],
                "status": "ready",
            },
        )
        _expect(status, {200}, raw, "business profile update")
        steps.append(f"profile={parsed.get('business_profile_status') if isinstance(parsed, dict) else 'ok'}")

        status, raw, parsed = _request("POST", f"{base_url}/admin/tenants/{tenant_id}/autopilot/run", token=token)
        _expect(status, {200}, raw, "admin autopilot")
        steps.append(f"autopilot health={parsed.get('health_score') if isinstance(parsed, dict) else 'ok'}")

        for step in steps:
            print(f"[OK] {step}")
        print("No-charge admin launch smoke completed.")
        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
