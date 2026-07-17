#!/usr/bin/env python3
"""Install the central n8n error workflow and attach it to production workflows."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx


TARGET_WORKFLOWS = {
    "SvontAI - WhatsApp Gemini v1",
    "svontai-tool-runner",
}
ERROR_WORKFLOW_NAME = "SvontAI - Central Error Handler"


def _workflow_payload(workflow: dict) -> dict:
    return {
        "name": workflow["name"],
        "nodes": workflow.get("nodes", []),
        "connections": workflow.get("connections", {}),
        "settings": workflow.get("settings", {}),
    }


def main() -> int:
    base_url = os.environ["N8N_BASE_URL"].rstrip("/")
    headers = {"X-N8N-API-KEY": os.environ["N8N_API_KEY"]}
    template_path = Path(__file__).resolve().parents[1] / "n8n" / "templates" / "svontai-error-handler.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))

    with httpx.Client(timeout=30) as client:
        response = client.get(f"{base_url}/api/v1/workflows", headers=headers, params={"limit": 100})
        response.raise_for_status()
        summaries = response.json().get("data", [])
        by_name = {item["name"]: item for item in summaries}

        existing = by_name.get(ERROR_WORKFLOW_NAME)
        if existing:
            response = client.put(
                f"{base_url}/api/v1/workflows/{existing['id']}",
                headers=headers,
                json=_workflow_payload(template),
            )
        else:
            response = client.post(
                f"{base_url}/api/v1/workflows",
                headers=headers,
                json=_workflow_payload(template),
            )
        response.raise_for_status()
        error_workflow_id = str(response.json()["id"])

        attached = []
        for summary in summaries:
            if summary.get("name") not in TARGET_WORKFLOWS:
                continue
            detail_response = client.get(
                f"{base_url}/api/v1/workflows/{summary['id']}",
                headers=headers,
            )
            detail_response.raise_for_status()
            detail = detail_response.json()
            settings = dict(detail.get("settings") or {})
            settings["errorWorkflow"] = error_workflow_id
            detail["settings"] = settings
            update_response = client.put(
                f"{base_url}/api/v1/workflows/{summary['id']}",
                headers=headers,
                json=_workflow_payload(detail),
            )
            update_response.raise_for_status()
            attached.append(summary["name"])

    print({"error_workflow_id": error_workflow_id, "attached": sorted(attached)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
