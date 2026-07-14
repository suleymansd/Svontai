#!/usr/bin/env python3
"""Replace live n8n tool-runner OpenAI nodes with the secured Gemini backend."""

from __future__ import annotations

import json
import os
import sys

import httpx


WORKFLOW_NAME = "svontai-tool-runner"
REMOVE_NODES = {
    "Edit Fields2",
    "Agent Router",
    "Edit Fields4",
    "AR - Normalize Input",
    "Message a model2",
    "AR - Extract Router",
    "Prepare PDF Input",
    "OpenAI - PDF Summary",
    "Gemini - PDF Summary",
    "Build PDF Summary Response",
    "Get many messages",
    "Parse tool_input",
    "HTTP Request",
    "Upload file",
    "Clarify Response",
}
RENAME_NODES = {
    "Message a model": "Gemini - Meeting Summary",
    "OpenAI - PDF Summary": "Gemini - PDF Summary",
    "OpenAI - Report Generator": "Gemini - Report Generator",
}
PURPOSES = {
    "Gemini - Meeting Summary": "meeting_summary",
    "Gemini - Report Generator": "report_generator",
}
MANAGED_NODES = {"Verify Signature", "Auth OK?", "Auth Fail", "Unsupported Tool"}


def _api() -> tuple[str, dict[str, str]]:
    base_url = os.environ.get("N8N_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("N8N_API_KEY", "")
    if not base_url or not api_key:
        raise RuntimeError("N8N_BASE_URL and N8N_API_KEY are required")
    return base_url, {"X-N8N-API-KEY": api_key}


def _find_workflow(client: httpx.Client, base_url: str, headers: dict[str, str]) -> dict:
    response = client.get(f"{base_url}/api/v1/workflows", headers=headers, params={"limit": 100})
    response.raise_for_status()
    match = next((item for item in response.json().get("data", []) if item.get("name") == WORKFLOW_NAME), None)
    if not match:
        raise RuntimeError(f"Workflow not found: {WORKFLOW_NAME}")
    response = client.get(f"{base_url}/api/v1/workflows/{match['id']}", headers=headers)
    response.raise_for_status()
    return response.json()


def _http_parameters(purpose: str) -> dict:
    source = '$node["Verify Signature"].json'
    text_expression = (
        "={{ (() => { const v = " + source + ".tool_input || {}; "
        "return String(v.text || v.content || v.prompt || v.transcript || ''); })() }}"
    )
    return {
        "method": "POST",
        "url": "={{ " + source + ".svontai.endpoints.ai_generate }}",
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {"name": "Authorization", "value": "=Bearer {{ " + source + ".svontai.token }}"},
                {"name": "X-Tenant-Id", "value": "={{ " + source + ".tenant_id }}"},
                {"name": "Content-Type", "value": "application/json"},
            ]
        },
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": (
            "={{ { tenantId: "
            + source
            + f".tenant_id, purpose: '{purpose}', text: "
            + text_expression[3:-3]
            + " } }}"
        ),
        "options": {"timeout": 60000},
    }


def _security_nodes() -> list[dict]:
    verify_code = r"""const crypto = require('crypto');
const req = $input.first().json || {};
let body = req.body || {};
if (typeof body === 'string') { try { body = JSON.parse(body); } catch { body = {}; } }
const headers = req.headers || {};
const header = (name) => { const key = Object.keys(headers).find((k) => k.toLowerCase() === name.toLowerCase()); return key ? headers[key] : undefined; };
const stable = (obj) => { if (obj === null || obj === undefined || typeof obj !== 'object') return obj; if (Array.isArray(obj)) return obj.map(stable); const out = {}; for (const key of Object.keys(obj).sort()) out[key] = stable(obj[key]); return out; };
const canonical = (obj) => JSON.stringify(stable(obj)).replace(/[^\x00-\x7F]/g, (char) => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`);
const timestamp = Number(header('X-SvontAI-Timestamp'));
const signature = String(header('X-SvontAI-Signature') || '');
const secret = $env.SVONTAI_TO_N8N_SECRET || '';
let authOk = false; let authError = '';
if (!secret) authError = 'Missing shared secret';
else if (!Number.isFinite(timestamp) || !signature) authError = 'Missing signature headers';
else if (Math.abs(Math.floor(Date.now() / 1000) - timestamp) > 300) authError = 'Signature expired';
else { const payload = canonical(body); const expected = crypto.createHmac('sha256', secret).update(`${timestamp}.${payload}`, 'utf8').digest('hex'); const a = Buffer.from(signature); const e = Buffer.from(expected); authOk = a.length === e.length && crypto.timingSafeEqual(a, e); if (!authOk) authError = 'Invalid signature'; }
return [{ json: { ...body, authOk, authError } }];"""
    return [
        {
            "id": "tool-verify-signature",
            "name": "Verify Signature",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [-1800, 96],
            "parameters": {"jsCode": verify_code},
        },
        {
            "id": "tool-auth-ok",
            "name": "Auth OK?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [-1550, 96],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "typeValidation": "strict"},
                    "conditions": [
                        {
                            "leftValue": "={{ $json.authOk }}",
                            "rightValue": "",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                        }
                    ],
                }
            },
        },
        {
            "id": "tool-auth-fail",
            "name": "Auth Fail",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [-1250, 280],
            "parameters": {
                "jsCode": "return [{json:{request_id:$json.request_id||'',success:false,data:{},error:{message:$json.authError||'Authentication failed',code:'AUTH_FAILED'},usage:{time_ms:0,tokens:null,cost:null},artifacts:[]}}];"
            },
        },
    ]


def _unsupported_node() -> dict:
    return {
        "id": "tool-unsupported",
        "name": "Unsupported Tool",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [250, 650],
        "parameters": {
            "jsCode": "return [{json:{request_id:$json.request_id||'',success:false,data:{},error:{message:`Unsupported or unavailable tool: ${$json.tool_slug||'unknown'}`,code:'UNSUPPORTED_TOOL_SLUG'},usage:{time_ms:0,tokens:null,cost:null},artifacts:[]}}];"
        },
    }


def _rename_connections(connections: dict) -> dict:
    renamed = {}
    for source, outputs in connections.items():
        if source in REMOVE_NODES:
            continue
        source_name = RENAME_NODES.get(source, source)
        clean_outputs = []
        for branch in outputs.get("main", []):
            clean_branch = []
            for target in branch:
                if target.get("node") in REMOVE_NODES:
                    continue
                item = dict(target)
                item["node"] = RENAME_NODES.get(item.get("node"), item.get("node"))
                clean_branch.append(item)
            clean_outputs.append(clean_branch)
        renamed[source_name] = {"main": clean_outputs}
    return renamed


def migrate(workflow: dict) -> dict:
    nodes = []
    for original in workflow["nodes"]:
        if original["name"] in REMOVE_NODES or original["name"] in MANAGED_NODES:
            continue
        node = dict(original)
        node["name"] = RENAME_NODES.get(node["name"], node["name"])
        if node["name"] in PURPOSES:
            node["type"] = "n8n-nodes-base.httpRequest"
            node["typeVersion"] = 4.4
            node["parameters"] = _http_parameters(PURPOSES[node["name"]])
            node.pop("credentials", None)
        nodes.append(node)

    nodes.extend(_security_nodes())
    nodes.append(_unsupported_node())
    connections = _rename_connections(workflow["connections"])
    connections["Webhook"] = {"main": [[{"node": "Verify Signature", "type": "main", "index": 0}]]}
    connections["Verify Signature"] = {"main": [[{"node": "Auth OK?", "type": "main", "index": 0}]]}
    connections["Auth OK?"] = {
        "main": [
            [{"node": "Switch", "type": "main", "index": 0}],
            [{"node": "Auth Fail", "type": "main", "index": 0}],
        ]
    }
    connections["Auth Fail"] = {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]}
    connections["Switch"] = {
        "main": [
            [{"node": "Prepare Meeting Input", "type": "main", "index": 0}],
            [{"node": "Unsupported Tool", "type": "main", "index": 0}],
            [{"node": "Unsupported Tool", "type": "main", "index": 0}],
            [{"node": "Unsupported Tool", "type": "main", "index": 0}],
            [{"node": "Edit Fields", "type": "main", "index": 0}],
            [{"node": "Unsupported Tool", "type": "main", "index": 0}],
            [{"node": "Unsupported Tool", "type": "main", "index": 0}],
        ]
    }
    connections["Unsupported Tool"] = {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]}

    replacements = {**RENAME_NODES, "Edit Fields2": "Verify Signature"}
    for node in nodes:
        raw = json.dumps(node.get("parameters", {}), ensure_ascii=False)
        for old, new in replacements.items():
            raw = raw.replace(old, new)
        node["parameters"] = json.loads(raw)

    return {
        "name": workflow["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": workflow.get("settings", {}).get("executionOrder", "v1")},
    }


def main() -> int:
    base_url, headers = _api()
    with httpx.Client(timeout=30) as client:
        workflow = _find_workflow(client, base_url, headers)
        payload = migrate(workflow)
        if "--apply" not in sys.argv:
            ai_nodes = [node["name"] for node in payload["nodes"] if "Gemini" in node["name"]]
            print({"mode": "dry-run", "id": workflow["id"], "active": workflow["active"], "ai_nodes": ai_nodes})
            return 0
        response = client.put(f"{base_url}/api/v1/workflows/{workflow['id']}", headers=headers, json=payload)
        if response.is_error:
            print({"status": response.status_code, "body": response.text[:1000]})
        response.raise_for_status()
        updated = response.json()
        print({"mode": "apply", "id": updated["id"], "active": updated["active"], "name": updated["name"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
