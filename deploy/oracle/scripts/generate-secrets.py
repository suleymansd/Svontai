#!/usr/bin/env python3
"""Create a protected Oracle env file without printing generated secrets."""

from __future__ import annotations

from pathlib import Path
import secrets
import stat


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".env.oracle.example"
TARGET = ROOT / ".env.oracle"


def main() -> int:
    if TARGET.exists():
        raise SystemExit(f"Refusing to overwrite existing {TARGET}")

    content = SOURCE.read_text(encoding="utf-8")
    replacements = {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(36),
        "REDIS_PASSWORD": secrets.token_urlsafe(36),
        "RESTIC_PASSWORD": secrets.token_urlsafe(48),
    }
    output: list[str] = []
    for line in content.splitlines():
        key = line.split("=", 1)[0] if "=" in line else ""
        if key in replacements:
            output.append(f"{key}={replacements[key]}")
        else:
            output.append(line)
    content = "\n".join(output) + "\n"

    TARGET.write_text(content, encoding="utf-8")
    TARGET.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(
        f"Created {TARGET} with mode 0600. PostgreSQL and Redis received new secrets; "
        "copy every existing application/provider secret from Railway unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
