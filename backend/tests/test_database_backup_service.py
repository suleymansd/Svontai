from __future__ import annotations

import base64
import shutil
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.services.database_backup_service import DatabaseBackupError, DatabaseBackupService


@pytest.fixture
def backup_settings():
    names = (
        "DATABASE_BACKUP_ENCRYPTION_KEY_B64",
        "DATABASE_BACKUP_R2_ENDPOINT_URL",
        "DATABASE_BACKUP_R2_ACCESS_KEY_ID",
        "DATABASE_BACKUP_R2_SECRET_ACCESS_KEY",
        "DATABASE_BACKUP_R2_BUCKET",
        "DATABASE_BACKUP_R2_PREFIX",
        "DATABASE_BACKUP_RETENTION_DAYS",
    )
    previous = {name: getattr(settings, name) for name in names}
    settings.DATABASE_BACKUP_ENCRYPTION_KEY_B64 = base64.b64encode(b"k" * 32).decode()
    settings.DATABASE_BACKUP_R2_ENDPOINT_URL = "https://account.r2.cloudflarestorage.com"
    settings.DATABASE_BACKUP_R2_ACCESS_KEY_ID = "access"
    settings.DATABASE_BACKUP_R2_SECRET_ACCESS_KEY = "secret"
    settings.DATABASE_BACKUP_R2_BUCKET = "svontai-backups"
    settings.DATABASE_BACKUP_R2_PREFIX = "postgres"
    settings.DATABASE_BACKUP_RETENTION_DAYS = 30
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(settings, name, value)


def test_encrypt_decrypt_round_trip_and_tamper_detection(tmp_path, backup_settings):
    service = DatabaseBackupService()
    source = tmp_path / "database.dump"
    encrypted = tmp_path / "database.dump.aes256gcm"
    restored = tmp_path / "database.restore.dump"
    source.write_bytes((b"database-content" * 8192) + b"end")

    service._encrypt(source, encrypted)
    service._decrypt(encrypted, restored)

    assert restored.read_bytes() == source.read_bytes()
    payload = bytearray(encrypted.read_bytes())
    payload[-20] ^= 1
    encrypted.write_bytes(payload)

    with pytest.raises(DatabaseBackupError, match="authentication failed"):
        service._decrypt(encrypted, restored)


def test_encryption_key_must_be_exactly_32_bytes(backup_settings):
    settings.DATABASE_BACKUP_ENCRYPTION_KEY_B64 = base64.b64encode(b"short").decode()

    with pytest.raises(DatabaseBackupError, match="32 bytes"):
        DatabaseBackupService()


def test_delete_expired_only_removes_old_objects(monkeypatch, backup_settings):
    now = datetime.now(timezone.utc)

    class FakeClient:
        def __init__(self):
            self.deleted = []

        def list_objects_v2(self, **kwargs):
            return {
                "IsTruncated": False,
                "Contents": [
                    {"Key": "postgres/old.dump", "LastModified": now - timedelta(days=31)},
                    {"Key": "postgres/current.dump", "LastModified": now - timedelta(days=31)},
                    {"Key": "postgres/recent.dump", "LastModified": now - timedelta(days=2)},
                ],
            }

        def delete_objects(self, **kwargs):
            self.deleted.extend(kwargs["Delete"]["Objects"])

    client = FakeClient()
    monkeypatch.setattr(DatabaseBackupService, "_r2_client", staticmethod(lambda: client))

    removed = DatabaseBackupService()._delete_expired("postgres/current.dump", now)

    assert removed == 1
    assert client.deleted == [{"Key": "postgres/old.dump"}]


def test_postgres_env_keeps_password_out_of_commands(backup_settings):
    previous = settings.DATABASE_URL
    settings.DATABASE_URL = "postgresql+psycopg://backup_user:encoded%20password@db.internal:5432/svontai?sslmode=require"
    try:
        env = DatabaseBackupService._postgres_env()
    finally:
        settings.DATABASE_URL = previous

    assert env["PGHOST"] == "db.internal"
    assert env["PGUSER"] == "backup_user"
    assert env["PGPASSWORD"] == "encoded password"
    assert env["PGDATABASE"] == "svontai"
    assert env["PGSSLMODE"] == "require"


def test_upload_requires_encryption_and_restore_metadata(monkeypatch, tmp_path, backup_settings):
    encrypted = tmp_path / "database.dump.aes256gcm"
    encrypted.write_bytes(b"encrypted-backup")

    class FakeClient:
        def __init__(self):
            self.metadata = {}

        def upload_file(self, _path, _bucket, _key, ExtraArgs):
            self.metadata = ExtraArgs["Metadata"]

        def head_object(self, **_kwargs):
            return {
                "ContentLength": encrypted.stat().st_size,
                "Metadata": self.metadata,
            }

    client = FakeClient()
    monkeypatch.setattr(DatabaseBackupService, "_r2_client", staticmethod(lambda: client))

    DatabaseBackupService()._upload(
        encrypted,
        "postgres/latest.dump.aes256gcm",
        "a" * 64,
        ("046",),
        True,
    )

    assert client.metadata["encryption"] == "aes-256-gcm"
    assert client.metadata["restore-verified"] == "true"
    assert client.metadata["backup-format"] == "postgresql-custom"


def test_remote_backup_verification_downloads_authenticates_and_restores(monkeypatch, tmp_path, backup_settings):
    service = DatabaseBackupService()
    source = tmp_path / "original.dump"
    source.write_bytes(b"pg-dump-fixture")
    remote = tmp_path / "remote.aes256gcm"
    service._encrypt(source, remote)
    restored = []

    class FakeClient:
        def download_file(self, bucket, key, filename):
            assert bucket == settings.DATABASE_BACKUP_R2_BUCKET
            assert key == "postgres/latest.dump.aes256gcm"
            shutil.copyfile(remote, filename)

    monkeypatch.setattr(service, "_r2_client", lambda: FakeClient())
    monkeypatch.setattr(service, "_verify_restore", lambda path, heads: restored.append((path.read_bytes(), heads)))
    checksum = service._sha256(remote)
    service.verify_stored_backup("postgres/latest.dump.aes256gcm", checksum, ("056",))
    assert restored == [(b"pg-dump-fixture", ("056",))]
    with pytest.raises(DatabaseBackupError, match="checksum"):
        service.verify_stored_backup("postgres/latest.dump.aes256gcm", "0" * 64, ("056",))
    assert len(restored) == 1


def test_latest_backup_checks_all_pages_and_rejects_stale_objects(monkeypatch, backup_settings):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("verify_backup", Path(__file__).resolve().parents[2] / "scripts" / "verify_production_backup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    now = datetime.now(timezone.utc)
    recent = {"Key": "postgres/new.dump.aes256gcm", "LastModified": now - timedelta(hours=1)}

    class FakeClient:
        def get_paginator(self, operation):
            assert operation == "list_objects_v2"
            return self

        def paginate(self, **kwargs):
            yield {"Contents": [{"Key": "postgres/old.dump.aes256gcm", "LastModified": now - timedelta(days=7)}]}
            yield {"Contents": [recent, {"Key": "postgres/note.txt", "LastModified": now}]}

        def head_object(self, **kwargs):
            assert kwargs["Key"] == recent["Key"]
            return {"ContentLength": 1024, "Metadata": {
                "encryption": "aes-256-gcm", "restore-verified": "true", "backup-format": "postgresql-custom",
                "sha256": "a" * 64, "alembic-heads": "056",
            }}

    service = DatabaseBackupService()
    monkeypatch.setattr(service, "_r2_client", lambda: FakeClient())
    assert module._latest_object(service)["object_key"] == recent["Key"]
    recent["LastModified"] = now - timedelta(days=4)
    with pytest.raises(RuntimeError, match="stale"):
        module._latest_object(service)


def test_restore_cleanup_never_drops_a_database_it_did_not_create(monkeypatch, tmp_path, backup_settings):
    service = DatabaseBackupService()
    commands = []
    monkeypatch.setattr(service, "_postgres_env", lambda *args: {})

    def fail_create(command, **kwargs):
        commands.append(command[0])
        raise DatabaseBackupError("createdb denied")

    monkeypatch.setattr(service, "_run_command", fail_create)
    with pytest.raises(DatabaseBackupError, match="createdb denied"):
        service._verify_restore(tmp_path / "fixture.dump", ("056",))
    assert commands == ["createdb"]
