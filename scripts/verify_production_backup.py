#!/usr/bin/env python3
"""Verify the latest encrypted R2 backup, optionally creating one first."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.services.database_backup_service import DatabaseBackupService


def _latest_object(service: DatabaseBackupService) -> dict:
    client = service._r2_client()
    prefix = settings.DATABASE_BACKUP_R2_PREFIX.strip("/") or "postgres"
    response = client.list_objects_v2(
        Bucket=settings.DATABASE_BACKUP_R2_BUCKET,
        Prefix=f"{prefix}/",
    )
    objects = response.get("Contents") or []
    if not objects:
        raise RuntimeError("R2 bucket does not contain a database backup")
    latest = max(objects, key=lambda item: item["LastModified"])
    head = client.head_object(
        Bucket=settings.DATABASE_BACKUP_R2_BUCKET,
        Key=latest["Key"],
    )
    metadata = head.get("Metadata") or {}
    required = {
        "encryption": "aes-256-gcm",
        "restore-verified": "true",
        "backup-format": "postgresql-custom",
    }
    for name, expected in required.items():
        if metadata.get(name) != expected:
            raise RuntimeError(f"Latest R2 backup has invalid {name} metadata")
    checksum = metadata.get("sha256") or ""
    if len(checksum) != 64:
        raise RuntimeError("Latest R2 backup checksum metadata is invalid")
    if not metadata.get("alembic-heads"):
        raise RuntimeError("Latest R2 backup has no Alembic head metadata")
    size = int(head.get("ContentLength") or 0)
    if size <= 64:
        raise RuntimeError("Latest R2 backup is unexpectedly small")
    modified = latest["LastModified"].astimezone(timezone.utc)
    return {
        "object_key": latest["Key"],
        "size_bytes": size,
        "last_modified": modified.isoformat(),
        "age_seconds": int((datetime.now(timezone.utc) - modified).total_seconds()),
        "encryption": metadata["encryption"],
        "restore_verified": True,
        "backup_format": metadata["backup-format"],
        "alembic_heads": metadata["alembic-heads"].split(","),
        "checksum_recorded": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-and-verify",
        action="store_true",
        help="Create, restore-test, encrypt, upload, and then inspect a new backup.",
    )
    args = parser.parse_args()
    if settings.ENVIRONMENT != "prod":
        raise RuntimeError("Backup verification must run with ENVIRONMENT=prod")
    if not settings.DATABASE_BACKUP_VERIFY_RESTORE:
        raise RuntimeError("DATABASE_BACKUP_VERIFY_RESTORE must be enabled")

    service = DatabaseBackupService()
    created = None
    if args.run_and_verify:
        result = service.run()
        if not result.restore_verified:
            raise RuntimeError("New backup did not complete its restore test")
        created = result.object_key
    verified = _latest_object(service)
    if created and verified["object_key"] != created:
        raise RuntimeError("The newly created backup is not the latest R2 object")
    print(json.dumps({"status": "ok", "created": created, "latest": verified}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Production backup verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
