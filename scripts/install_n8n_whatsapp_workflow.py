#!/usr/bin/env python3
"""Create or update the production WhatsApp workflow from the committed template."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx


WORKFLOW_NAME = "SvontAI - WhatsApp Gemini v1"
WRITABLE_SETTINGS = {
    "executionOrder",
    "saveDataErrorExecution",
    "saveDataSuccessExecution",
    "saveManualExecutions",
    "saveExecutionProgress",
    "executionTimeout",
    "timezone",
    "callerPolicy",
    "errorWorkflow",
}


def _payload(template: dict, existing: dict | None = None) -> dict:
    settings = {
        key: value
        for key, value in (template.get("settings") or {}).items()
        if key in WRITABLE_SETTINGS
    }
    existing_error = ((existing or {}).get("settings") or {}).get("errorWorkflow")
    if existing_error:
        settings["errorWorkflow"] = existing_error
    return {
        "name": WORKFLOW_NAME,
        "nodes": template["nodes"],
        "connections": template["connections"],
        "settings": settings,
    }


def main() -> int:
    base_url = os.environ["N8N_BASE_URL"].rstrip("/")
    headers = {"X-N8N-API-KEY": os.environ["N8N_API_KEY"]}
    path = Path(__file__).resolve().parents[1] / "n8n" / "workflows" / "SvontAI_WhatsApp_Gemini_v1.json"
    template = json.loads(path.read_text(encoding="utf-8"))

    with httpx.Client(timeout=45) as client:
        response = client.get(f"{base_url}/api/v1/workflows", headers=headers, params={"limit": 100})
        response.raise_for_status()
        summary = next(
            (item for item in response.json().get("data", []) if item.get("name") == WORKFLOW_NAME),
            None,
        )
        existing = None
        if summary:
            detail = client.get(f"{base_url}/api/v1/workflows/{summary['id']}", headers=headers)
            detail.raise_for_status()
            existing = detail.json()
            response = client.put(
                f"{base_url}/api/v1/workflows/{summary['id']}",
                headers=headers,
                json=_payload(template, existing),
            )
        else:
            response = client.post(
                f"{base_url}/api/v1/workflows",
                headers=headers,
                json=_payload(template),
            )
        response.raise_for_status()
        workflow_id = str(response.json()["id"])
        if not (existing or {}).get("active"):
            activate = client.post(f"{base_url}/api/v1/workflows/{workflow_id}/activate", headers=headers)
            activate.raise_for_status()

    print({"workflow": WORKFLOW_NAME, "id": workflow_id, "active": True, "media_nodes": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
