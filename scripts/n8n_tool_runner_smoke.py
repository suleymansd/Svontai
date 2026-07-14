#!/usr/bin/env python3
"""Exercise the live n8n tool runner with signed, no-charge-safe requests."""

from __future__ import annotations

import os
import uuid

import httpx

from app.core.config import settings
from app.core.n8n_security import create_n8n_jwt_token, generate_svontai_to_n8n_headers


def _payload(tenant_id: str, tool_slug: str, text: str) -> dict:
    return {
        "tenant_id": tenant_id,
        "user_id": str(uuid.uuid4()),
        "request_id": f"smoke-{tool_slug}-{uuid.uuid4()}",
        "tool_slug": tool_slug,
        "tool_input": {"text": text},
        "context": {
            "locale": "tr-TR",
            "timezone": "Europe/Istanbul",
            "channel": "smoke",
            "memory": {},
        },
        "svontai": {
            "tenant_id": tenant_id,
            "token": create_n8n_jwt_token(tenant_id),
            "endpoints": {
                "ai_generate": f"{settings.BACKEND_URL.rstrip('/')}/api/v1/n8n/ai/generate",
            },
        },
    }


def _post(client: httpx.Client, url: str, payload: dict, *, signed: bool = True) -> dict:
    headers = generate_svontai_to_n8n_headers(payload, payload["tenant_id"]) if signed else {}
    response = client.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def main() -> int:
    tenant_id = str(uuid.uuid4())
    url = f"{os.environ['N8N_BASE_URL'].rstrip('/')}/webhook/svontai-tool-runner"
    results: dict[str, object] = {}

    with httpx.Client(timeout=90) as client:
        for tool_slug, text in (
            ("meeting_summary", "Müşteri demo tarihini onayladı. Ayşe sunumu hazırlayacak."),
            ("report_generator", "Bu ay 24 yeni müşteri ve yüzde 18 dönüşüm elde edildi."),
        ):
            response = _post(client, url, _payload(tenant_id, tool_slug, text))
            summary = str((response.get("data") or {}).get("summary") or "").strip()
            if response.get("success") is not True or not summary:
                raise RuntimeError(f"{tool_slug} failed: {response.get('error') or response}")
            results[tool_slug] = {"success": True, "non_empty_output": True}

        unsupported = _post(client, url, _payload(tenant_id, "gmail_summary", "test"))
        unsupported_code = (unsupported.get("error") or {}).get("code")
        if unsupported.get("success") is not False or unsupported_code != "UNSUPPORTED_TOOL_SLUG":
            raise RuntimeError(f"Unsupported tool was not rejected: {unsupported}")
        results["unsupported_tool"] = unsupported_code

        unsigned = _post(client, url, _payload(tenant_id, "meeting_summary", "test"), signed=False)
        unsigned_code = (unsigned.get("error") or {}).get("code")
        if unsigned.get("success") is not False or unsigned_code != "AUTH_FAILED":
            raise RuntimeError(f"Unsigned request was not rejected: {unsigned}")
        results["unsigned_request"] = unsigned_code

    print({"success": True, "checks": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
