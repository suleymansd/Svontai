#!/usr/bin/env python3
"""
Lightweight smoke test for Tool Engine + Integrations endpoints.

No pytest dependency, standard library only.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class SmokeError(RuntimeError):
    pass


@dataclass
class HttpResult:
    status: int
    text: str
    json_data: dict | list | None


def log(msg: str) -> None:
    print(f"[smoke] {msg}")


def http_call(
    base_url: str,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
    timeout: int = 25,
) -> HttpResult:
    url = f"{base_url.rstrip('/')}{path}"
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    data = None
    if payload is not None:
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = None
            if raw:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
            return HttpResult(status=resp.status, text=raw, json_data=parsed)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        parsed = None
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
        return HttpResult(status=exc.code, text=raw, json_data=parsed)
    except urllib.error.URLError as exc:
        raise SmokeError(f"Network error for {method} {path}: {exc}") from exc


def expect_status(result: HttpResult, allowed: set[int], label: str) -> None:
    if result.status not in allowed:
        raise SmokeError(f"{label} failed. status={result.status} body={result.text[:800]}")


def extract_code_from_message(message: str) -> str | None:
    match = re.search(r"(\d{6})", message or "")
    return match.group(1) if match else None


def ensure_server_up(base_url: str) -> None:
    health = http_call(base_url, "GET", "/health")
    if health.status == 200:
        log("/health OK")
        return
    root = http_call(base_url, "GET", "/")
    if root.status == 200:
        log("/ OK (health endpoint unavailable)")
        return
    raise SmokeError(f"Server not healthy. /health={health.status}, /= {root.status}")


def obtain_access_and_tenant(base_url: str) -> tuple[str, str]:
    env_token = (os.getenv("SMOKE_ACCESS_TOKEN") or "").strip()
    env_tenant = (os.getenv("SMOKE_TENANT_ID") or "").strip()
    if env_token and env_tenant:
        log("Using SMOKE_ACCESS_TOKEN + SMOKE_TENANT_ID")
        return env_token, env_tenant

    email = (os.getenv("SMOKE_EMAIL") or f"smoke-{int(time.time())}@example.com").strip().lower()
    password = (os.getenv("SMOKE_PASSWORD") or "Password123!").strip()
    full_name = (os.getenv("SMOKE_FULL_NAME") or "Smoke Test User").strip()

    register = http_call(
        base_url,
        "POST",
        "/auth/register",
        payload={"email": email, "password": password, "full_name": full_name},
    )
    if register.status not in {201, 400}:
        raise SmokeError(f"Register failed: status={register.status} body={register.text[:800]}")

    verify_request = http_call(
        base_url,
        "POST",
        "/auth/email-verification/request",
        payload={"email": email},
    )
    expect_status(verify_request, {200}, "email-verification/request")

    verification_code = (os.getenv("SMOKE_VERIFICATION_CODE") or "").strip()
    if not verification_code:
        message = ""
        if isinstance(verify_request.json_data, dict):
            message = str(verify_request.json_data.get("message") or "")
        verification_code = extract_code_from_message(message) or ""

    if verification_code:
        confirm = http_call(
            base_url,
            "POST",
            "/auth/email-verification/confirm",
            payload={"email": email, "code": verification_code},
        )
        expect_status(confirm, {200}, "email-verification/confirm")
        log("Email verified")
    else:
        log("Verification code not found in response; login will be attempted directly")

    login = http_call(
        base_url,
        "POST",
        "/auth/login",
        payload={"email": email, "password": password},
    )
    expect_status(login, {200}, "auth/login")
    if not isinstance(login.json_data, dict) or not login.json_data.get("access_token"):
        raise SmokeError(f"Login response missing access_token: {login.text[:800]}")

    access_token = str(login.json_data["access_token"])
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    tenant_name = (os.getenv("SMOKE_TENANT_NAME") or f"Smoke Tenant {int(time.time())}").strip()
    create_tenant = http_call(
        base_url,
        "POST",
        "/tenants",
        headers=auth_headers,
        payload={"name": tenant_name},
    )

    if create_tenant.status == 201 and isinstance(create_tenant.json_data, dict) and create_tenant.json_data.get("id"):
        tenant_id = str(create_tenant.json_data["id"])
        log(f"Tenant created: {tenant_id}")
        return access_token, tenant_id

    if create_tenant.status == 400:
        my_tenants = http_call(base_url, "GET", "/tenants/my", headers=auth_headers)
        expect_status(my_tenants, {200}, "tenants/my")
        if not isinstance(my_tenants.json_data, list) or not my_tenants.json_data:
            raise SmokeError("User has no tenant and tenant creation failed")
        tenant_id = str(my_tenants.json_data[0]["id"])
        log(f"Using existing tenant: {tenant_id}")
        return access_token, tenant_id

    raise SmokeError(f"Tenant bootstrap failed: status={create_tenant.status} body={create_tenant.text[:800]}")


def run_smoke(base_url: str) -> None:
    ensure_server_up(base_url)
    access_token, tenant_id = obtain_access_and_tenant(base_url)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Tenant-ID": tenant_id,
    }

    status_resp = http_call(base_url, "GET", "/integrations/status", headers=headers)
    expect_status(status_resp, {200}, "GET /integrations/status")
    if not isinstance(status_resp.json_data, dict):
        raise SmokeError("/integrations/status response is not JSON object")
    integration_states = {k: (v.get("status") if isinstance(v, dict) else v) for k, v in status_resp.json_data.items()}
    log(f"Integrations: {integration_states}")

    tools_resp = http_call(base_url, "GET", "/tools", headers=headers)
    expect_status(tools_resp, {200}, "GET /tools")
    if not isinstance(tools_resp.json_data, list):
        raise SmokeError("/tools response is not JSON array")
    log(f"Tools count: {len(tools_resp.json_data)}")

    desired_slug = (os.getenv("SMOKE_TOOL_SLUG") or "pdf_summary").strip()
    if not any(isinstance(item, dict) and item.get("slug") == desired_slug for item in tools_resp.json_data):
        raise SmokeError(f"Tool slug not found in /tools: {desired_slug}")

    enable_resp = http_call(
        base_url,
        "PUT",
        f"/tools/{urllib.parse.quote(desired_slug)}/settings",
        headers=headers,
        payload={"enabled": True, "config": {}},
    )
    expect_status(enable_resp, {200}, f"PUT /tools/{desired_slug}/settings")

    request_id = (os.getenv("SMOKE_REQUEST_ID") or f"smoke-{desired_slug}-{int(time.time())}").strip()
    run_resp = http_call(
        base_url,
        "POST",
        "/tools/run",
        headers=headers,
        payload={
            "requestId": request_id,
            "toolSlug": desired_slug,
            "toolInput": {
                "pdf_url": "https://example.com/demo.pdf",
                "language": "tr",
            },
            "context": {
                "locale": "tr-TR",
                "timezone": "Europe/Istanbul",
                "channel": "api",
                "memory": {},
            },
        },
    )
    expect_status(run_resp, {200}, "POST /tools/run")
    if not isinstance(run_resp.json_data, dict):
        raise SmokeError("/tools/run response is not JSON object")
    if str(run_resp.json_data.get("requestId") or "") != request_id:
        raise SmokeError(f"/tools/run requestId mismatch: expected={request_id} got={run_resp.json_data.get('requestId')}")

    run_success = bool(run_resp.json_data.get("success"))
    if not run_success:
        err_msg = ""
        if isinstance(run_resp.json_data.get("error"), dict):
            err_msg = str(run_resp.json_data["error"].get("message") or "")
        log(f"Tool run returned success=false (acceptable in smoke): {err_msg or 'unknown error'}")

    runs_resp = http_call(base_url, "GET", "/tools/runs?limit=20&offset=0", headers=headers)
    expect_status(runs_resp, {200}, "GET /tools/runs")
    if not isinstance(runs_resp.json_data, list):
        raise SmokeError("/tools/runs response is not JSON array")
    if not any(isinstance(item, dict) and item.get("requestId") == request_id for item in runs_resp.json_data):
        raise SmokeError("Created request_id not found in /tools/runs list")

    run_detail = http_call(base_url, "GET", f"/tools/runs/{urllib.parse.quote(request_id)}", headers=headers)
    expect_status(run_detail, {200}, "GET /tools/runs/{request_id}")
    if not isinstance(run_detail.json_data, dict):
        raise SmokeError("/tools/runs/{request_id} response is not JSON object")
    if str(run_detail.json_data.get("requestId") or "") != request_id:
        raise SmokeError("Run detail requestId mismatch")

    log("Smoke test completed successfully")


def main() -> int:
    base_url = (os.getenv("SMOKE_BASE_URL") or "http://127.0.0.1:8000").strip()
    try:
        run_smoke(base_url)
        return 0
    except SmokeError as exc:
        print(f"[smoke][ERROR] {exc}")
        return 1
    except Exception as exc:
        print(f"[smoke][ERROR] Unexpected failure: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
