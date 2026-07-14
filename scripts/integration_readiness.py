#!/usr/bin/env python3
"""No-secret readiness checks for SmartWA live integrations.

This script only checks whether required environment variables are present.
It never prints secret values and it never calls paid/live provider APIs.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


CHECKS = {
    "meta_whatsapp": [
        "META_APP_ID",
        "META_APP_SECRET",
        "META_CONFIG_ID",
        "META_REDIRECT_URI",
        "WEBHOOK_PUBLIC_URL",
        "BACKEND_URL",
    ],
    "stripe": [
        "PAYMENTS_ENABLED",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_IDS",
        "STRIPE_SUCCESS_URL",
        "STRIPE_CANCEL_URL",
        "STRIPE_PORTAL_RETURN_URL",
    ],
    "voice_twilio": [
        "VOICE_GATEWAY_TO_SVONTAI_SECRET",
        "VOICE_GATEWAY_PUBLIC_URL",
        "VOICE_OUTBOUND_MODE",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
    ],
    "n8n": [
        "USE_N8N",
        "N8N_BASE_URL",
        "N8N_API_KEY",
        "SVONTAI_TO_N8N_SECRET",
        "N8N_TO_SVONTAI_SECRET",
    ],
    "frontend": [
        "NEXT_PUBLIC_BACKEND_URL",
    ],
}


INSECURE_DEFAULTS = {
    "JWT_SECRET_KEY": {"your-super-secret-jwt-key-change-this-in-production"},
    "VOICE_GATEWAY_TO_SVONTAI_SECRET": {"change-this-voice-gateway-secret"},
    "SVONTAI_TO_N8N_SECRET": {"change-this-secret"},
    "N8N_TO_SVONTAI_SECRET": {"change-this-secret"},
    "WEBHOOK_USERNAME": {"", "admin", "localdev"},
    "WEBHOOK_PASSWORD": {"", "password", "localdevpass"},
}


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_value(key: str, loaded: dict[str, str]) -> str:
    return os.environ.get(key) or loaded.get(key, "")


def _present(key: str, loaded: dict[str, str]) -> bool:
    return bool(_env_value(key, loaded).strip())


def _enabled(key: str, loaded: dict[str, str]) -> bool:
    return _env_value(key, loaded).strip().lower() in {"1", "true", "yes", "on", "live"}


def _print_check(name: str, status: str, detail: str) -> None:
    print(f"[{status}] {name}: {detail}")


def _missing(keys: list[str], loaded: dict[str, str]) -> list[str]:
    return [key for key in keys if not _present(key, loaded)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check SmartWA live integration environment readiness.")
    parser.add_argument("--env-file", default="", help="Optional .env file to read without printing values.")
    parser.add_argument("--profile", choices=["dev", "prod"], default=os.environ.get("ENVIRONMENT", "dev"))
    args = parser.parse_args()

    loaded = _load_env_file(Path(args.env_file)) if args.env_file else {}
    strict = args.profile == "prod"
    failures = 0

    for name, keys in CHECKS.items():
        active = strict
        if name == "stripe":
            active = strict or _enabled("PAYMENTS_ENABLED", loaded)
        elif name == "voice_twilio":
            active = strict or _env_value("VOICE_OUTBOUND_MODE", loaded).strip().lower() == "live"
        elif name == "n8n":
            active = strict or _enabled("USE_N8N", loaded)
        elif name in {"meta_whatsapp", "frontend"}:
            active = strict or any(_present(key, loaded) for key in keys)

        missing = _missing(keys, loaded)
        if not active and missing:
            _print_check(name, "SKIP", "integration not enabled in this environment")
            continue
        if missing:
            failures += 1
            _print_check(name, "FAIL", f"missing {', '.join(missing)}")
        else:
            _print_check(name, "OK", "required variables are present")

    insecure = []
    for key, defaults in INSECURE_DEFAULTS.items():
        value = _env_value(key, loaded).strip()
        if value in defaults:
            insecure.append(key)
    if insecure:
        if strict:
            failures += 1
            _print_check("secrets", "FAIL", f"insecure/default values: {', '.join(insecure)}")
        else:
            _print_check("secrets", "WARN", f"insecure/default values: {', '.join(insecure)}")
    else:
        _print_check("secrets", "OK", "no known insecure defaults detected")

    if failures:
        print(f"Readiness failed with {failures} issue(s).")
        return 1
    print("Readiness checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
