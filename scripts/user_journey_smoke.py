#!/usr/bin/env python3
"""No-charge end-user journey smoke for SmartWA.

This script exercises the customer SaaS path without sending WhatsApp messages,
charging cards, or placing real phone calls. Voice automation is validated only
through the dry-run intent/job API surface.

Environment:
  BACKEND_URL or SMARTWA_BACKEND_URL: API base URL, default http://127.0.0.1:8001
  SMOKE_EMAIL_PREFIX: optional email prefix, default user-smoke
  SMOKE_DOMAIN: optional email domain, default example.com
  SMOKE_WAIT_FOR_WORKER_SECONDS: optional worker completion wait, default 0
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any


TIMEOUT_SECONDS = 20


@dataclass
class Step:
    name: str
    ok: bool
    detail: str


class SmokeError(RuntimeError):
    pass


def _base_url() -> str:
    return (
        os.getenv("SMARTWA_BACKEND_URL")
        or os.getenv("BACKEND_URL")
        or "http://127.0.0.1:8001"
    ).strip().rstrip("/")


def _request(
    method: str,
    path: str,
    *,
    base_url: str,
    token: str | None = None,
    tenant_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[int, str, Any]:
    headers = {
        "User-Agent": "SmartWA-user-journey-smoke/1.0",
        "Accept": "application/json",
    }
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    req = urllib.request.Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(300_000).decode("utf-8", errors="replace")
            parsed = _parse_json(raw)
            return response.status, raw, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read(50_000).decode("utf-8", errors="replace")
        return exc.code, raw, _parse_json(raw)


def _request_multipart(
    path: str,
    *,
    base_url: str,
    token: str,
    tenant_id: str,
    fields: dict[str, str],
    filename: str,
    content_type: str,
    content: bytes,
) -> tuple[int, str, Any]:
    boundary = f"----SvontAISmoke{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode("utf-8"),
            b"\r\n",
        ])
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=b"".join(chunks),
        headers={
            "User-Agent": "SmartWA-user-journey-smoke/1.0",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": tenant_id,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(300_000).decode("utf-8", errors="replace")
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
        raise SmokeError(f"{name}: expected {sorted(expected)}, got {status}, body={raw[:300]!r}")


def _extract_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    if not match:
        raise SmokeError(f"could not extract verification code from message={message!r}")
    return match.group(1)


def _record(steps: list[Step], name: str, detail: str) -> None:
    steps.append(Step(name=name, ok=True, detail=detail))


def run() -> int:
    base_url = _base_url()
    email_prefix = (os.getenv("SMOKE_EMAIL_PREFIX") or "user-smoke").strip()
    domain = (os.getenv("SMOKE_DOMAIN") or "example.com").strip()
    nonce = int(time.time())
    email = f"{email_prefix}-{nonce}@{domain}".lower()
    password = "Password123!"
    tenant_name = f"Smoke Tenant {nonce}"
    steps: list[Step] = []

    try:
        status, raw, parsed = _request("GET", "/health", base_url=base_url)
        _expect(status, {200}, raw, "health")
        if not isinstance(parsed, dict) or parsed.get("environment") is None:
            raise SmokeError("health endpoint does not look like SmartWA backend")
        _record(steps, "health", parsed.get("status", "ok") if isinstance(parsed, dict) else "ok")

        status, raw, _ = _request(
            "POST",
            "/auth/register",
            base_url=base_url,
            payload={"email": email, "password": password, "full_name": "Smoke User"},
        )
        _expect(status, {201}, raw, "register")
        _record(steps, "register", email)

        status, raw, parsed = _request(
            "POST",
            "/auth/email-verification/request",
            base_url=base_url,
            payload={"email": email},
        )
        _expect(status, {200}, raw, "email verification request")
        if not isinstance(parsed, dict):
            raise SmokeError("email verification request did not return JSON object")
        code = _extract_code(str(parsed.get("message") or ""))
        _record(steps, "email verification code", "received")

        status, raw, _ = _request(
            "POST",
            "/auth/email-verification/confirm",
            base_url=base_url,
            payload={"email": email, "code": code},
        )
        _expect(status, {200}, raw, "email verification confirm")
        _record(steps, "email verification confirm", "ok")

        status, raw, parsed = _request(
            "POST",
            "/auth/login",
            base_url=base_url,
            payload={"email": email, "password": password, "portal": "tenant"},
        )
        _expect(status, {200}, raw, "login")
        if not isinstance(parsed, dict) or not parsed.get("access_token"):
            raise SmokeError("login did not return access_token")
        token = parsed["access_token"]
        _record(steps, "login", "token issued")

        status, raw, parsed = _request(
            "POST",
            "/tenants",
            base_url=base_url,
            token=token,
            payload={"name": tenant_name},
        )
        _expect(status, {201}, raw, "tenant create")
        if not isinstance(parsed, dict) or not parsed.get("id"):
            raise SmokeError("tenant create did not return id")
        tenant_id = parsed["id"]
        _record(steps, "tenant create", tenant_id)

        status, raw, parsed = _request("GET", "/api/me", base_url=base_url, token=token, tenant_id=tenant_id)
        _expect(status, {200}, raw, "me context")
        _record(steps, "me context", "ok")

        status, raw, parsed = _request("GET", "/onboarding/setup/status", base_url=base_url, token=token, tenant_id=tenant_id)
        _expect(status, {200}, raw, "onboarding status")
        if not isinstance(parsed, dict) or parsed.get("current_step") != "business_profile":
            raise SmokeError(f"unexpected onboarding current_step={parsed!r}")
        _record(steps, "onboarding initial", parsed["current_step"])

        status, raw, parsed = _request(
            "POST",
            "/onboarding/setup/business-profile",
            base_url=base_url,
            token=token,
            tenant_id=tenant_id,
            payload={
                "setup_mode": os.getenv("SMOKE_SETUP_MODE", "self_serve"),
                "industry": "service",
                "primary_goal": "appointment",
                "tone": "professional",
                "handoff_rules": ["complaint", "unknown_question"],
                "website_url": "",
                "instagram_url": "",
                "business_summary": "",
            },
        )
        _expect(status, {200}, raw, "business profile save")
        if not isinstance(parsed, dict) or parsed.get("current_step") != "autopilot_setup":
            raise SmokeError(f"business profile did not advance to autopilot_setup: {parsed!r}")
        _record(steps, "business profile save", "optional knowledge sources accepted")

        status, raw, parsed = _request(
            "POST",
            "/onboarding/setup/run-autopilot",
            base_url=base_url,
            token=token,
            tenant_id=tenant_id,
        )
        _expect(status, {200}, raw, "run autopilot")
        if not isinstance(parsed, dict) or parsed.get("is_completed") is not True:
            raise SmokeError(f"autopilot setup did not complete: {parsed!r}")
        _record(steps, "run autopilot", "completed")

        for name, path, expected_type in [
            ("dashboard autopilot", "/setup/autopilot/status", dict),
            ("integration diagnostics", "/integrations/diagnostics", dict),
            ("bots", "/bots", list),
            ("leads", "/leads", list),
            ("appointments", "/appointments", list),
            ("calls", "/calls", list),
        ]:
            status, raw, parsed = _request("GET", path, base_url=base_url, token=token, tenant_id=tenant_id)
            _expect(status, {200}, raw, name)
            if not isinstance(parsed, expected_type):
                raise SmokeError(f"{name}: expected {expected_type.__name__}, got {type(parsed).__name__}")
            _record(steps, name, "ok")

        status, raw, parsed = _request(
            "GET",
            "/bots/assistant-profile",
            base_url=base_url,
            token=token,
            tenant_id=tenant_id,
        )
        _expect(status, {200}, raw, "assistant profile")
        if not isinstance(parsed, dict) or parsed.get("assistant", {}).get("assistant_type") != "primary":
            raise SmokeError(f"primary assistant is missing: {parsed!r}")
        _record(steps, "primary assistant", "ready")

        status, raw, parsed = _request(
            "PUT",
            "/bots/assistant-profile/training",
            base_url=base_url,
            token=token,
            tenant_id=tenant_id,
            payload={
                "goal": "appointments",
                "tone": "professional",
                "response_length": "concise",
                "price_policy": "known_only",
                "handoff_mode": "automatic",
                "business_summary": "Smoke hizmet işletmesi randevu taleplerini yönetir.",
            },
        )
        _expect(status, {200}, raw, "assistant guided training")
        if not isinstance(parsed, dict) or parsed.get("completion_percent") != 100:
            raise SmokeError(f"assistant training did not complete: {parsed!r}")
        _record(steps, "assistant guided training", "completed")

        status, raw, parsed = _request_multipart(
            "/media",
            base_url=base_url,
            token=token,
            tenant_id=tenant_id,
            fields={
                "title": "Smoke katalog",
                "description": "Smoke ürün kataloğu",
                "keywords": "katalog, ürünler",
            },
            filename="smoke-catalog.pdf",
            content_type="application/pdf",
            content=b"%PDF-1.4\nSvontAI smoke catalog",
        )
        _expect(status, {201}, raw, "assistant media upload")
        if not isinstance(parsed, dict) or parsed.get("media_type") != "catalog":
            raise SmokeError(f"media upload failed: {parsed!r}")
        _record(steps, "assistant media upload", "private catalog stored")

        status, raw, parsed = _request(
            "GET",
            "/bots/assistant-profile",
            base_url=base_url,
            token=token,
            tenant_id=tenant_id,
        )
        _expect(status, {200}, raw, "assistant media capability")
        media_capability = next(
            (item for item in parsed.get("capabilities", []) if item.get("key") == "media_catalog"),
            None,
        ) if isinstance(parsed, dict) else None
        if not media_capability or media_capability.get("status") != "active":
            raise SmokeError(f"media capability is not active: {parsed!r}")
        _record(steps, "assistant media capability", "active")

        status, raw, parsed = _request("GET", "/voice-automation/settings", base_url=base_url, token=token, tenant_id=tenant_id)
        _expect(status, {200}, raw, "voice settings")
        if not isinstance(parsed, dict):
            raise SmokeError("voice settings did not return object")
        _record(steps, "voice settings read", "ok")

        status, raw, parsed = _request(
            "PATCH",
            "/voice-automation/settings",
            base_url=base_url,
            token=token,
            tenant_id=tenant_id,
            payload={"enabled": True, "provider": "vapi", "from_number": "+905551112233"},
        )
        _expect(status, {200}, raw, "voice settings update")
        if not isinstance(parsed, dict) or parsed.get("enabled") is not True:
            raise SmokeError(f"voice settings update failed: {parsed!r}")
        _record(steps, "voice settings update", "enabled dry-run")

        status, raw, parsed = _request(
            "POST",
            "/voice-automation/test-call",
            base_url=base_url,
            token=token,
            tenant_id=tenant_id,
            payload={"customer_phone": "+905559998877", "customer_name": "Smoke Lead"},
        )
        _expect(status, {200}, raw, "voice test call")
        if not isinstance(parsed, dict) or parsed.get("status") != "queued":
            raise SmokeError(f"voice test call was not queued: {parsed!r}")
        _record(steps, "voice test call", "queued")

        status, raw, parsed = _request("GET", "/voice-automation/jobs", base_url=base_url, token=token, tenant_id=tenant_id)
        _expect(status, {200}, raw, "voice jobs")
        if not isinstance(parsed, list) or not parsed:
            raise SmokeError("voice jobs list is empty after test-call")
        job_status = parsed[0].get("status")
        _record(steps, "voice jobs", f"latest={job_status}")

        status, raw, parsed = _request("GET", "/voice-automation/intents", base_url=base_url, token=token, tenant_id=tenant_id)
        _expect(status, {200}, raw, "voice intents")
        if not isinstance(parsed, list) or not parsed:
            raise SmokeError("voice intents list is empty after test-call")
        _record(steps, "voice intents", f"latest={parsed[0].get('status')}")

        worker_wait_seconds = max(0, int(os.getenv("SMOKE_WAIT_FOR_WORKER_SECONDS") or "0"))
        if worker_wait_seconds:
            deadline = time.monotonic() + worker_wait_seconds
            latest_job_status = job_status
            calls: list[dict[str, Any]] = []
            while time.monotonic() < deadline:
                status, raw, parsed = _request(
                    "GET",
                    "/voice-automation/jobs",
                    base_url=base_url,
                    token=token,
                    tenant_id=tenant_id,
                )
                _expect(status, {200}, raw, "voice worker jobs")
                if isinstance(parsed, list) and parsed:
                    latest_job_status = parsed[0].get("status")
                if latest_job_status == "failed":
                    raise SmokeError(f"voice worker job failed: {parsed[0]!r}")

                status, raw, parsed_calls = _request(
                    "GET",
                    "/calls",
                    base_url=base_url,
                    token=token,
                    tenant_id=tenant_id,
                )
                _expect(status, {200}, raw, "voice worker calls")
                calls = parsed_calls if isinstance(parsed_calls, list) else []
                if latest_job_status == "completed" and calls:
                    break
                time.sleep(1)

            if latest_job_status != "completed" or not calls:
                raise SmokeError(
                    f"worker did not complete dry-run within {worker_wait_seconds}s "
                    f"(job={latest_job_status}, calls={len(calls)})"
                )
            _record(steps, "voice worker completion", f"job={latest_job_status}, calls={len(calls)}")

    except Exception as exc:
        for step in steps:
            print(f"[OK] {step.name}: {step.detail}")
        print(f"[FAIL] {exc}")
        return 1

    for step in steps:
        print(f"[OK] {step.name}: {step.detail}")
    print("No-charge end-user journey smoke completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
