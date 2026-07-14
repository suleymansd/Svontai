#!/usr/bin/env python3
"""Audit live n8n workflows without exposing credentials or secret values."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict, deque

import httpx


APPROVED_ACTIVE_WORKFLOWS = {
    "SvontAI - WhatsApp Gemini v1",
    "svontai-tool-runner",
}
REQUIRED_SECURITY_NODES = {"Verify Signature", "Auth OK?", "Auth Fail"}
RISKY_MARKERS = ("webhook.site", "localhost", "127.0.0.1")
NODE_REFERENCE_PATTERNS = (
    re.compile(r'\$node\[\s*["\']([^"\']+)["\']\s*\]'),
    re.compile(r'\$\(\s*["\']([^"\']+)["\']\s*\)'),
)


def _api() -> tuple[str, dict[str, str]]:
    base_url = os.environ.get("N8N_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("N8N_API_KEY", "")
    if not base_url or not api_key:
        raise RuntimeError("N8N_BASE_URL and N8N_API_KEY are required")
    return base_url, {"X-N8N-API-KEY": api_key}


def _workflow_list(client: httpx.Client, base_url: str, headers: dict[str, str]) -> list[dict]:
    response = client.get(f"{base_url}/api/v1/workflows", headers=headers, params={"limit": 100})
    response.raise_for_status()
    return list(response.json().get("data", []))


def _workflow(client: httpx.Client, base_url: str, headers: dict[str, str], workflow_id: str) -> dict:
    response = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers)
    response.raise_for_status()
    return response.json()


def _deactivate_unapproved(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
    workflows: list[dict],
) -> list[str]:
    changed = []
    for workflow in workflows:
        if not workflow.get("active") or workflow.get("name") in APPROVED_ACTIVE_WORKFLOWS:
            continue
        response = client.post(f"{base_url}/api/v1/workflows/{workflow['id']}/deactivate", headers=headers)
        response.raise_for_status()
        changed.append(workflow["name"])
    return changed


def _reachable_nodes(nodes: list[dict], connections: dict) -> set[str]:
    triggers = {
        node["name"]
        for node in nodes
        if node.get("type", "").endswith(".webhook")
        or "Trigger" in node.get("type", "")
        or node.get("type", "").endswith(".executeWorkflowTrigger")
    }
    reachable = set(triggers)
    queue = deque(triggers)
    while queue:
        source = queue.popleft()
        for output_group in connections.get(source, {}).values():
            for branch in output_group:
                for target in branch or []:
                    name = target.get("node")
                    if name and name not in reachable:
                        reachable.add(name)
                        queue.append(name)
    return reachable


def _node_references(parameters: dict) -> set[str]:
    raw = json.dumps(parameters, ensure_ascii=False)
    references = set()
    for pattern in NODE_REFERENCE_PATTERNS:
        references.update(pattern.findall(raw))
    return references


def _audit_workflow(workflow: dict) -> list[str]:
    if not workflow.get("active"):
        return []

    issues = []
    name = workflow["name"]
    nodes = workflow.get("nodes", [])
    connections = workflow.get("connections", {})
    node_names = [node.get("name", "") for node in nodes]
    node_name_set = set(node_names)
    duplicate_names = sorted(item for item, count in Counter(node_names).items() if count > 1)
    if duplicate_names:
        issues.append(f"{name}: duplicate node names {duplicate_names}")

    if name not in APPROVED_ACTIVE_WORKFLOWS:
        issues.append(f"{name}: active workflow is not approved for production")

    missing_security = REQUIRED_SECURITY_NODES - node_name_set
    if missing_security:
        issues.append(f"{name}: missing security nodes {sorted(missing_security)}")

    for source, outputs in connections.items():
        if source not in node_name_set:
            issues.append(f"{name}: connection source does not exist: {source}")
        for output_group in outputs.values():
            for branch in output_group:
                for target in branch or []:
                    if target.get("node") not in node_name_set:
                        issues.append(f"{name}: connection target does not exist: {target.get('node')}")

    reachable = _reachable_nodes(nodes, connections)
    disconnected = sorted(node_name_set - reachable)
    if disconnected:
        issues.append(f"{name}: disconnected nodes {disconnected}")

    for node in nodes:
        node_type = node.get("type", "").lower()
        node_name = node.get("name", "")
        raw = json.dumps(node.get("parameters", {}), ensure_ascii=False)
        if "openai" in node_type or "openai" in node_name.lower():
            issues.append(f"{name}: OpenAI node remains active: {node_name}")
        if node.get("credentials"):
            issues.append(f"{name}: direct n8n credential remains active: {node_name}")
        if re.search(r"Bearer\s+[A-Za-z0-9._-]{20,}", raw):
            issues.append(f"{name}: hardcoded bearer token in {node_name}")
        for marker in RISKY_MARKERS:
            if marker in raw.lower():
                issues.append(f"{name}: risky endpoint marker {marker} in {node_name}")
        for reference in sorted(_node_references(node.get("parameters", {})) - node_name_set):
            issues.append(f"{name}: {node_name} references missing node {reference}")

    return issues


def _duplicate_webhooks(workflows: list[dict]) -> list[str]:
    paths: dict[str, list[str]] = defaultdict(list)
    for workflow in workflows:
        if not workflow.get("active"):
            continue
        for node in workflow.get("nodes", []):
            if node.get("type", "").endswith(".webhook"):
                path = str(node.get("parameters", {}).get("path") or "").strip()
                if path:
                    paths[path].append(workflow["name"])
    return [f"duplicate active webhook {path}: {names}" for path, names in paths.items() if len(names) > 1]


def main() -> int:
    base_url, headers = _api()
    with httpx.Client(timeout=30) as client:
        summaries = _workflow_list(client, base_url, headers)
        if "--fix" in sys.argv:
            changed = _deactivate_unapproved(client, base_url, headers, summaries)
            print({"deactivated": changed})
            summaries = _workflow_list(client, base_url, headers)

        workflows = [_workflow(client, base_url, headers, item["id"]) for item in summaries]
        issues = []
        for workflow in workflows:
            issues.extend(_audit_workflow(workflow))
        issues.extend(_duplicate_webhooks(workflows))

        active = sorted(workflow["name"] for workflow in workflows if workflow.get("active"))
        print({"workflow_count": len(workflows), "active": active, "issue_count": len(issues)})
        for issue in issues:
            print(f"[FAIL] {issue}")
        if issues:
            return 1
        print("[OK] Active n8n workflows passed production audit")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
