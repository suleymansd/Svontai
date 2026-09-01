#!/usr/bin/env python3
"""Fail before deploy when the Oracle env contract is incomplete or unsafe."""

from __future__ import annotations

from pathlib import Path
import os
import stat
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.oracle"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized = value.strip()
        if len(normalized) >= 2 and normalized[0] == normalized[-1] == "'":
            normalized = normalized[1:-1].replace("\\'", "'").replace("\\\\", "\\")
        elif len(normalized) >= 2 and normalized[0] == normalized[-1] == '"':
            normalized = decode_double_quoted(normalized[1:-1])
        values[key.strip()] = normalized
    return values


def decode_double_quoted(value: str) -> str:
    """Decode the subset emitted by import-railway-secrets.py."""
    decoded: list[str] = []
    index = 0
    while index < len(value):
        current = value[index]
        following = value[index + 1] if index + 1 < len(value) else ""
        if current == "\\" and following in {"\\", '"'}:
            decoded.append(following)
            index += 2
            continue
        if current == "$" and following == "$":
            decoded.append("$")
            index += 2
            continue
        decoded.append(current)
        index += 1
    return "".join(decoded)


def main() -> int:
    if not ENV_PATH.exists():
        raise SystemExit("Missing .env.oracle. Run scripts/generate-secrets.py first.")

    mode = stat.S_IMODE(ENV_PATH.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise SystemExit(f"{ENV_PATH} must not be group/world accessible; run chmod 600")

    values = parse_env(ENV_PATH)
    errors: list[str] = []
    placeholders = [
        key
        for key, value in values.items()
        if "CHANGE_ME" in value or "REPLACE_WITH_" in value
    ]
    if placeholders:
        errors.append("unresolved placeholders: " + ", ".join(sorted(placeholders)))

    required = {
        "ACME_EMAIL",
        "FRONTEND_URL",
        "API_DOMAIN",
        "VOICE_DOMAIN",
        "N8N_DOMAIN",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "JWT_SECRET_KEY",
        "API_KEY_HASH_SECRET",
        "ENCRYPTION_KEY",
        "GEMINI_API_KEY",
        "RESEND_API_KEY",
        "OPENWA_API_KEY",
        "OPENWA_API_KEY_PEPPER",
        "OPENWA_WEBHOOK_SECRET",
        "N8N_API_KEY",
        "N8N_ENCRYPTION_KEY",
        "N8N_RUNNERS_AUTH_TOKEN",
        "N8N_INCOMING_WORKFLOW_ID",
        "N8N_ERROR_WEBHOOK_SECRET",
        "N8N_REPLY_BEARER_TOKEN",
        "SENTRY_DSN",
        "NEXT_PUBLIC_SENTRY_DSN",
        "WEB_PUSH_VAPID_PUBLIC_KEY",
        "WEB_PUSH_VAPID_PRIVATE_KEY_B64",
        "ARTIFACT_R2_ENDPOINT_URL",
        "ARTIFACT_R2_ACCESS_KEY_ID",
        "ARTIFACT_R2_SECRET_ACCESS_KEY",
        "ARTIFACT_R2_BUCKET",
        "DATABASE_BACKUP_ENCRYPTION_KEY_B64",
        "DATABASE_BACKUP_R2_ENDPOINT_URL",
        "DATABASE_BACKUP_R2_ACCESS_KEY_ID",
        "DATABASE_BACKUP_R2_SECRET_ACCESS_KEY",
        "DATABASE_BACKUP_R2_BUCKET",
        "RESTIC_PASSWORD",
        "VOICE_GATEWAY_TO_SVONTAI_SECRET",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
    }
    missing = sorted(key for key in required if not values.get(key))
    if missing:
        errors.append("missing required values: " + ", ".join(missing))

    for key in ("FRONTEND_URL", "BACKEND_URL", "WEBHOOK_PUBLIC_URL", "VOICE_GATEWAY_PUBLIC_URL"):
        parsed = urlparse(values.get(key, ""))
        if parsed.scheme != "https" or not parsed.hostname:
            errors.append(f"{key} must be an https URL")

    if values.get("BACKEND_URL") != f"https://{values.get('API_DOMAIN', '')}":
        errors.append("BACKEND_URL must match API_DOMAIN")
    if values.get("VOICE_GATEWAY_PUBLIC_URL") != f"https://{values.get('VOICE_DOMAIN', '')}":
        errors.append("VOICE_GATEWAY_PUBLIC_URL must match VOICE_DOMAIN")
    if values.get("ENVIRONMENT") != "prod":
        errors.append("ENVIRONMENT must be prod")
    if values.get("POSTGRES_USER") != "svontai":
        errors.append("POSTGRES_USER must remain svontai for the migration contract")
    if values.get("POSTGRES_DB") != "svontai":
        errors.append("POSTGRES_DB must remain svontai for the migration contract")
    if values.get("RATE_LIMIT_BACKEND") != "redis" or values.get("RATE_LIMIT_FAIL_CLOSED") != "true":
        errors.append("production rate limiting must use fail-closed Redis")

    if errors:
        raise SystemExit("Oracle environment validation failed:\n- " + "\n- ".join(errors))

    print("Oracle environment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
