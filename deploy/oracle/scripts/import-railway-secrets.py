#!/usr/bin/env python3
"""Fill matching Oracle placeholders from Railway without printing values."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.oracle"

SERVICE_ENV_KEYS = {
    "RAILWAY_API_SERVICE": "Svontai",
    "RAILWAY_WORKER_SERVICE": "Worker",
    "RAILWAY_VOICE_SERVICE": "Voice-Gateway",
    "RAILWAY_OPENWA_SERVICE": "OpenWA",
    "RAILWAY_N8N_SERVICE": "n8n",
    "RAILWAY_N8N_RUNNERS_SERVICE": "n8n-runners",
}

ALIASES = {
    "OPENWA_API_KEY": ("OPENWA_API_KEY", "API_MASTER_KEY"),
    "OPENWA_API_KEY_PEPPER": ("OPENWA_API_KEY_PEPPER", "API_KEY_PEPPER"),
    "NEXT_PUBLIC_SENTRY_DSN": ("NEXT_PUBLIC_SENTRY_DSN", "SENTRY_DSN"),
}


def railway_variables(service: str) -> dict[str, str]:
    result = subprocess.run(
        ["railway", "variable", "list", "--service", service, "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Railway returned invalid variables for {service}")
    return {
        str(key): str(value)
        for key, value in payload.items()
        if value is not None
        and str(value) != ""
        and "${{" not in str(value)
        and "${" not in str(value)
    }


def encode_env_value(value: str) -> str:
    """Use escaped Compose double-quoted syntax for arbitrary one-line values."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
    return f'"{escaped}"'


def main() -> int:
    if not ENV_PATH.exists():
        raise SystemExit("Missing .env.oracle. Run generate-secrets.py first.")

    combined: dict[str, str] = {}
    for env_key, default_name in SERVICE_ENV_KEYS.items():
        service = os.getenv(env_key, default_name)
        try:
            for key, value in railway_variables(service).items():
                # Keep the first concrete value. Railway reference variables in
                # another service must not replace the source secret.
                combined.setdefault(key, value)
        except subprocess.CalledProcessError as exc:
            raise SystemExit(
                f"Could not read Railway variables for {service}. "
                f"Check project linking and {env_key}."
            ) from exc

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    imported: list[str] = []
    output: list[str] = []
    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            output.append(line)
            continue

        key, current = line.split("=", 1)
        if "CHANGE_ME" not in current and "REPLACE_WITH_" not in current:
            output.append(line)
            continue

        candidates = ALIASES.get(key, (key,))
        value = next((combined[name] for name in candidates if combined.get(name)), "")
        if not value or "${{" in value or "${" in value:
            output.append(line)
            continue
        if "\n" in value or "\r" in value:
            raise SystemExit(f"Refusing multiline Railway value for {key}")

        output.append(f"{key}={encode_env_value(value)}")
        imported.append(key)

    ENV_PATH.write_text("\n".join(output) + "\n", encoding="utf-8")
    ENV_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(
        f"Imported {len(imported)} matching Railway values without displaying them. "
        "Run validate-env.py and fill any remaining placeholders manually."
    )
    if imported:
        print("Imported keys: " + ", ".join(sorted(imported)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
