#!/usr/bin/env python3
"""Backup/restore drill for the encrypted PostgreSQL backups (audit A24).

Subcommands:
  seed            Insert a small, recognisable data set into a migrated database.
  create-archive  Dump + AES-256-GCM encrypt the database with DatabaseBackupService.
  restore         Restore an archive into a throw-away database on a scratch server,
                  print row counts and the newest message timestamp, exit non-zero on
                  a failed or empty restore.

The restore step never touches the database named in the scratch URL; it creates
``svontai_drill_<timestamp>`` next to it and drops it afterwards unless
``--keep-database`` is given. Remote hosts are refused unless ``--allow-remote`` is
passed, so the drill cannot be pointed at production by accident.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

ENCRYPTED_SUFFIX = ".aes256gcm"
COUNT_TABLES = ("tenants", "users", "messages", "appointments")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class DrillError(RuntimeError):
    pass


def _pg_env(url_text: str, database: str | None = None) -> dict[str, str]:
    url = make_url(url_text)
    if not url.drivername.startswith("postgresql"):
        raise DrillError("The drill requires a postgresql:// URL")
    env = os.environ.copy()
    env.update({
        "PGHOST": str(url.host or "127.0.0.1"),
        "PGPORT": str(url.port or 5432),
        "PGUSER": str(url.username or ""),
        "PGPASSWORD": str(url.password or ""),
        "PGDATABASE": database or str(url.database or "postgres"),
        "PGCONNECT_TIMEOUT": "20",
    })
    if url.query.get("sslmode"):
        env["PGSSLMODE"] = str(url.query["sslmode"])
    return env


def _run(command: list[str], env: dict[str, str], timeout: int) -> str:
    completed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout).strip().splitlines()[-5:]
        raise DrillError(f"{command[0]} failed ({completed.returncode}): " + " | ".join(tail))
    return completed.stdout


def _scalar(env: dict[str, str], sql: str) -> str:
    return _run(["psql", "--tuples-only", "--no-align", "--command", sql], env, timeout=60).strip()


def cmd_seed(args: argparse.Namespace) -> int:
    os.environ["DATABASE_URL"] = args.database_url
    from app.db.session import SessionLocal
    from app.models.appointment import Appointment
    from app.models.bot import Bot
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.tenant import Tenant
    from app.models.user import User

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    token = secrets.token_hex(4)
    with SessionLocal() as db:
        user = User(email=f"drill-{token}@example.invalid", password_hash="drill-not-a-login", full_name="Restore Drill")
        db.add(user)
        db.flush()
        tenant = Tenant(name=f"Restore Drill {token}", owner_id=user.id)
        db.add(tenant)
        db.flush()
        bot = Bot(tenant_id=tenant.id, name="Drill Bot")
        db.add(bot)
        db.flush()
        conversation = Conversation(bot_id=bot.id, external_user_id=f"drill-{token}")
        db.add(conversation)
        db.flush()
        for index in range(args.messages):
            db.add(Message(
                conversation_id=conversation.id,
                sender="user" if index % 2 == 0 else "bot",
                content=f"drill message {index}",
                created_at=now - timedelta(minutes=args.messages - index),
            ))
        db.add(Appointment(tenant_id=tenant.id, customer_name="Drill Customer", subject="Drill", starts_at=now + timedelta(days=1)))
        db.commit()
    print(json.dumps({"seeded": {"tenants": 1, "users": 1, "messages": args.messages, "appointments": 1}, "token": token}))
    return 0


def cmd_create_archive(args: argparse.Namespace) -> int:
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    if not os.environ.get("DATABASE_BACKUP_ENCRYPTION_KEY_B64"):
        raise DrillError("DATABASE_BACKUP_ENCRYPTION_KEY_B64 must be set to create an archive")
    from app.services.database_backup_service import DatabaseBackupService

    output = Path(args.output)
    if not output.name.endswith(f".dump{ENCRYPTED_SUFFIX}"):
        raise DrillError(f"--output must end with .dump{ENCRYPTED_SUFFIX}")
    output.parent.mkdir(parents=True, exist_ok=True)
    service = DatabaseBackupService()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="svontai-drill-") as temp_dir:
        dump_path = Path(temp_dir) / "database.dump"
        service._create_dump(dump_path)
        heads = service._migration_heads()
        service._encrypt(dump_path, output)
    manifest = {
        "archive": output.name,
        "encrypted_size": output.stat().st_size,
        "encrypted_sha256": service._sha256(output),
        "migration_heads": list(heads),
        "encryption": "aes-256-gcm",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dump_seconds": round(time.monotonic() - started, 2),
    }
    output.with_suffix(output.suffix + ".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))
    return 0


def _decrypt(archive: Path, destination: Path, key_b64: str) -> None:
    os.environ["DATABASE_BACKUP_ENCRYPTION_KEY_B64"] = key_b64
    from app.services.database_backup_service import DatabaseBackupError, DatabaseBackupService

    try:
        DatabaseBackupService()._decrypt(archive, destination)
    except DatabaseBackupError as exc:
        raise DrillError(str(exc)) from exc


def cmd_restore(args: argparse.Namespace) -> int:
    archive = Path(args.archive)
    if not archive.is_file() or archive.stat().st_size == 0:
        raise DrillError(f"Archive is missing or empty: {archive}")
    scratch = make_url(args.database_url)
    if scratch.host not in LOCAL_HOSTS and not args.allow_remote:
        raise DrillError(f"Refusing to restore onto non-local host {scratch.host!r} without --allow-remote")

    maintenance_env = _pg_env(args.database_url)
    drill_database = f"svontai_drill_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{secrets.token_hex(3)}"
    result: dict[str, object] = {"archive": str(archive), "database": drill_database, "ok": False}
    started = time.monotonic()
    created = False
    try:
        with tempfile.TemporaryDirectory(prefix="svontai-drill-") as temp_dir:
            dump_path = archive
            if archive.name.endswith(ENCRYPTED_SUFFIX):
                encryption_material = os.environ.get("DATABASE_BACKUP_ENCRYPTION_KEY_B64", "")
                if args.encryption_key_b64:
                    encryption_material = args.encryption_key_b64
                if not encryption_material:
                    raise DrillError("Encrypted archive needs --encryption-key-b64 or DATABASE_BACKUP_ENCRYPTION_KEY_B64")
                dump_path = Path(temp_dir) / "database.dump"
                _decrypt(archive, dump_path, encryption_material)
                result["decrypted"] = True
            _run(["pg_restore", "--list", str(dump_path)], maintenance_env, timeout=300)
            _run(["createdb", drill_database], maintenance_env, timeout=120)
            created = True
            restore_env = _pg_env(args.database_url, drill_database)
            _run(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error", "--dbname", drill_database, str(dump_path)], restore_env, timeout=args.timeout)
            result["restore_seconds"] = round(time.monotonic() - started, 2)

            present = _scalar(restore_env, "SELECT " + ", ".join(f"to_regclass('public.{t}') IS NOT NULL" for t in COUNT_TABLES)).split("|")
            missing = [t for t, flag in zip(COUNT_TABLES, present) if flag != "t"]
            if missing:
                raise DrillError(f"Restored database lacks tables: {missing}")
            counts = {t: int(_scalar(restore_env, f"SELECT count(*) FROM {t}")) for t in COUNT_TABLES}
            result["counts"] = counts
            result["newest_message_at"] = _scalar(restore_env, "SELECT max(created_at) FROM messages") or None
            result["migration_heads"] = [h for h in _scalar(restore_env, "SELECT version_num FROM alembic_version ORDER BY version_num").splitlines() if h]
            if counts["tenants"] < args.min_tenants or counts["users"] < args.min_users or counts["messages"] < args.min_messages:
                raise DrillError(f"Restore looks empty: {counts}")
            result["ok"] = True
    except DrillError as exc:
        result["error"] = str(exc)
    finally:
        if created and not args.keep_database:
            subprocess.run(["dropdb", "--if-exists", "--force", drill_database], env=maintenance_env, capture_output=True, text=True, timeout=120, check=False)
            result["database_dropped"] = True
        result["total_seconds"] = round(time.monotonic() - started, 2)
        if args.result_json:
            Path(args.result_json).write_text(json.dumps(result, indent=2, default=str) + "\n")
        print(json.dumps(result, default=str))
    return 0 if result["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="Insert a tenant, user, conversation, messages and an appointment")
    seed.add_argument("--database-url", required=True)
    seed.add_argument("--messages", type=int, default=5)
    seed.set_defaults(func=cmd_seed)

    create = sub.add_parser("create-archive", help="Dump and encrypt DATABASE_URL with the backup service")
    create.add_argument("--output", required=True, help=f"Path ending in .dump{ENCRYPTED_SUFFIX}")
    create.add_argument("--database-url", help="Overrides DATABASE_URL from the environment")
    create.set_defaults(func=cmd_create_archive)

    restore = sub.add_parser("restore", help="Restore an archive into a throw-away database and report")
    restore.add_argument("archive", help=f"database.dump or database.dump{ENCRYPTED_SUFFIX}")
    restore.add_argument("--database-url", required=True, help="Scratch PostgreSQL server (its database is only used for createdb/dropdb)")
    restore.add_argument("--encryption-key-b64", default="", help="Defaults to DATABASE_BACKUP_ENCRYPTION_KEY_B64")
    restore.add_argument("--allow-remote", action="store_true")
    restore.add_argument("--keep-database", action="store_true")
    restore.add_argument("--result-json", help="Also write the result to this file")
    restore.add_argument("--min-tenants", type=int, default=1)
    restore.add_argument("--min-users", type=int, default=1)
    restore.add_argument("--min-messages", type=int, default=0)
    restore.add_argument("--timeout", type=int, default=2 * 3600)
    restore.set_defaults(func=cmd_restore)

    args = parser.parse_args()
    try:
        return args.func(args)
    except DrillError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
