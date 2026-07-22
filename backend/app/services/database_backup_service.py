"""Encrypted PostgreSQL backup and private Cloudflare R2 storage."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy.engine import make_url

from app.core.config import settings


MAGIC = b"SVONTAI_DB_BACKUP_V1\x00"
NONCE_BYTES = 12
TAG_BYTES = 16
CHUNK_BYTES = 8 * 1024 * 1024
CRITICAL_TABLES = ("tenants", "users", "messages", "sales_inquiries")


class DatabaseBackupError(RuntimeError):
    """Raised when a dump, verification, encryption, or upload fails."""


@dataclass(frozen=True)
class DatabaseBackupResult:
    object_key: str
    encrypted_size: int
    encrypted_sha256: str
    migration_heads: tuple[str, ...]
    restore_verified: bool
    expired_removed: int


class DatabaseBackupService:
    def __init__(self) -> None:
        self._key = self._decode_encryption_key()

    @staticmethod
    def _decode_encryption_key() -> bytes:
        try:
            value = base64.b64decode(
                settings.DATABASE_BACKUP_ENCRYPTION_KEY_B64,
                validate=True,
            )
        except Exception as exc:
            raise DatabaseBackupError("Database backup encryption key is invalid") from exc
        if len(value) != 32:
            raise DatabaseBackupError("Database backup encryption key must decode to 32 bytes")
        return value

    @staticmethod
    def _postgres_env(database: str | None = None) -> dict[str, str]:
        try:
            url = make_url(settings.DATABASE_URL)
        except Exception as exc:
            raise DatabaseBackupError("Production database URL is invalid") from exc
        if not url.drivername.startswith("postgresql"):
            raise DatabaseBackupError("Database backups require PostgreSQL")

        query = dict(url.query)
        env = os.environ.copy()
        env.update(
            {
                "PGHOST": str(url.host or settings.PGHOST or ""),
                "PGPORT": str(url.port or settings.PGPORT or 5432),
                "PGUSER": str(url.username or settings.PGUSER or ""),
                "PGPASSWORD": str(url.password or settings.PGPASSWORD or ""),
                "PGDATABASE": database or str(url.database or settings.PGDATABASE or ""),
                "PGCONNECT_TIMEOUT": "20",
            }
        )
        if query.get("sslmode"):
            env["PGSSLMODE"] = str(query["sslmode"])
        if not env["PGHOST"] or not env["PGUSER"] or not env["PGDATABASE"]:
            raise DatabaseBackupError("PostgreSQL connection settings are incomplete")
        return env

    @staticmethod
    def _run_command(
        command: list[str],
        *,
        env: dict[str, str],
        timeout_seconds: int,
    ) -> str:
        executable = shutil.which(command[0])
        if not executable:
            raise DatabaseBackupError(f"Required PostgreSQL client is unavailable: {command[0]}")
        try:
            result = subprocess.run(
                [executable, *command[1:]],
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return result.stdout
        except subprocess.TimeoutExpired as exc:
            raise DatabaseBackupError(f"{command[0]} timed out") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "unknown error").strip()[:1000]
            raise DatabaseBackupError(f"{command[0]} failed: {detail}") from exc

    def _create_dump(self, path: Path) -> None:
        self._run_command(
            [
                "pg_dump",
                "--format=custom",
                "--compress=6",
                "--no-owner",
                "--no-privileges",
                "--file",
                str(path),
            ],
            env=self._postgres_env(),
            timeout_seconds=2 * 3600,
        )
        if not path.is_file() or path.stat().st_size == 0:
            raise DatabaseBackupError("pg_dump produced an empty backup")
        path.chmod(0o600)
        self._run_command(
            ["pg_restore", "--list", str(path)],
            env=self._postgres_env(),
            timeout_seconds=300,
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(CHUNK_BYTES):
                digest.update(chunk)
        return digest.hexdigest()

    def _encrypt(self, source: Path, destination: Path) -> None:
        nonce = os.urandom(NONCE_BYTES)
        encryptor = Cipher(algorithms.AES(self._key), modes.GCM(nonce)).encryptor()
        with source.open("rb") as source_handle, destination.open("wb") as destination_handle:
            destination_handle.write(MAGIC)
            destination_handle.write(nonce)
            while chunk := source_handle.read(CHUNK_BYTES):
                destination_handle.write(encryptor.update(chunk))
            destination_handle.write(encryptor.finalize())
            destination_handle.write(encryptor.tag)
        destination.chmod(0o600)

    def _decrypt(self, source: Path, destination: Path) -> None:
        total_size = source.stat().st_size
        minimum_size = len(MAGIC) + NONCE_BYTES + TAG_BYTES
        if total_size <= minimum_size:
            raise DatabaseBackupError("Encrypted backup is truncated")

        try:
            with source.open("rb") as source_handle:
                if source_handle.read(len(MAGIC)) != MAGIC:
                    raise DatabaseBackupError("Encrypted backup header is invalid")
                nonce = source_handle.read(NONCE_BYTES)
                source_handle.seek(-TAG_BYTES, os.SEEK_END)
                tag = source_handle.read(TAG_BYTES)
                ciphertext_size = total_size - minimum_size
                source_handle.seek(len(MAGIC) + NONCE_BYTES)

                decryptor = Cipher(algorithms.AES(self._key), modes.GCM(nonce, tag)).decryptor()
                remaining = ciphertext_size
                with destination.open("wb") as destination_handle:
                    while remaining:
                        chunk = source_handle.read(min(CHUNK_BYTES, remaining))
                        if not chunk:
                            raise DatabaseBackupError("Encrypted backup ended unexpectedly")
                        remaining -= len(chunk)
                        destination_handle.write(decryptor.update(chunk))
                    destination_handle.write(decryptor.finalize())
        except InvalidTag as exc:
            destination.unlink(missing_ok=True)
            raise DatabaseBackupError("Encrypted backup authentication failed") from exc
        destination.chmod(0o600)

    def _migration_heads(self) -> tuple[str, ...]:
        output = self._run_command(
            ["psql", "--tuples-only", "--no-align", "--command", "SELECT version_num FROM alembic_version ORDER BY version_num"],
            env=self._postgres_env(),
            timeout_seconds=60,
        )
        heads = tuple(line.strip() for line in output.splitlines() if line.strip())
        if not heads:
            raise DatabaseBackupError("Production database has no Alembic head")
        return heads

    def _verify_restore(self, dump_path: Path, expected_heads: tuple[str, ...]) -> None:
        restore_database = f"svontai_restore_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{secrets.token_hex(3)}"
        maintenance_env = self._postgres_env("postgres")
        try:
            self._run_command(
                ["createdb", "--maintenance-db=postgres", restore_database],
                env=maintenance_env,
                timeout_seconds=120,
            )
            restore_env = self._postgres_env(restore_database)
            self._run_command(
                ["pg_restore", "--no-owner", "--no-privileges", "--dbname", restore_database, str(dump_path)],
                env=restore_env,
                timeout_seconds=2 * 3600,
            )
            restored_heads_output = self._run_command(
                ["psql", "--tuples-only", "--no-align", "--command", "SELECT version_num FROM alembic_version ORDER BY version_num"],
                env=restore_env,
                timeout_seconds=60,
            )
            restored_heads = tuple(
                line.strip() for line in restored_heads_output.splitlines() if line.strip()
            )
            if restored_heads != expected_heads:
                raise DatabaseBackupError(
                    f"Restored Alembic heads do not match production: {restored_heads} != {expected_heads}"
                )

            table_list = ", ".join(f"to_regclass('public.{table}')" for table in CRITICAL_TABLES)
            tables_output = self._run_command(
                ["psql", "--tuples-only", "--no-align", "--field-separator=|", "--command", f"SELECT {table_list}"],
                env=restore_env,
                timeout_seconds=60,
            ).strip()
            restored_tables = tuple(part.strip() for part in tables_output.split("|"))
            if restored_tables != CRITICAL_TABLES:
                raise DatabaseBackupError(f"Restored critical tables are incomplete: {restored_tables}")
        finally:
            self._run_command(
                ["dropdb", "--if-exists", "--force", restore_database],
                env=maintenance_env,
                timeout_seconds=120,
            )

    @staticmethod
    def _r2_client():
        return boto3.client(
            "s3",
            endpoint_url=settings.DATABASE_BACKUP_R2_ENDPOINT_URL,
            aws_access_key_id=settings.DATABASE_BACKUP_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.DATABASE_BACKUP_R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 5, "mode": "standard"},
                connect_timeout=20,
                read_timeout=180,
            ),
        )

    @staticmethod
    def _object_key(now: datetime) -> str:
        prefix = settings.DATABASE_BACKUP_R2_PREFIX.strip("/") or "postgres"
        return f"{prefix}/{now:%Y/%m}/svontai-{now:%Y%m%dT%H%M%SZ}.dump.aes256gcm"

    def _upload(
        self,
        encrypted_path: Path,
        object_key: str,
        encrypted_sha256: str,
        migration_heads: tuple[str, ...],
        restore_verified: bool,
    ) -> None:
        client = self._r2_client()
        client.upload_file(
            str(encrypted_path),
            settings.DATABASE_BACKUP_R2_BUCKET,
            object_key,
            ExtraArgs={
                "ContentType": "application/octet-stream",
                "Metadata": {
                    "sha256": encrypted_sha256,
                    "alembic-heads": ",".join(migration_heads),
                    "encryption": "aes-256-gcm",
                    "restore-verified": "true" if restore_verified else "false",
                    "backup-format": "postgresql-custom",
                },
            },
        )
        head = client.head_object(
            Bucket=settings.DATABASE_BACKUP_R2_BUCKET,
            Key=object_key,
        )
        if int(head.get("ContentLength") or 0) != encrypted_path.stat().st_size:
            raise DatabaseBackupError("R2 backup size verification failed")
        metadata = head.get("Metadata") or {}
        if metadata.get("sha256") != encrypted_sha256:
            raise DatabaseBackupError("R2 backup checksum metadata verification failed")
        if metadata.get("encryption") != "aes-256-gcm":
            raise DatabaseBackupError("R2 backup encryption metadata verification failed")
        expected_restore = "true" if restore_verified else "false"
        if metadata.get("restore-verified") != expected_restore:
            raise DatabaseBackupError("R2 backup restore metadata verification failed")

    def _delete_expired(self, current_key: str, now: datetime) -> int:
        client = self._r2_client()
        prefix = settings.DATABASE_BACKUP_R2_PREFIX.strip("/") or "postgres"
        cutoff = now - timedelta(days=settings.DATABASE_BACKUP_RETENTION_DAYS)
        expired: list[dict[str, str]] = []
        continuation_token: str | None = None
        while True:
            kwargs = {
                "Bucket": settings.DATABASE_BACKUP_R2_BUCKET,
                "Prefix": f"{prefix}/",
            }
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            response = client.list_objects_v2(**kwargs)
            for item in response.get("Contents") or []:
                key = str(item.get("Key") or "")
                modified = item.get("LastModified")
                if key and key != current_key and modified and modified.astimezone(timezone.utc) < cutoff:
                    expired.append({"Key": key})
            if not response.get("IsTruncated"):
                break
            continuation_token = str(response.get("NextContinuationToken") or "")

        for offset in range(0, len(expired), 1000):
            client.delete_objects(
                Bucket=settings.DATABASE_BACKUP_R2_BUCKET,
                Delete={"Objects": expired[offset : offset + 1000], "Quiet": True},
            )
        return len(expired)

    def run(self) -> DatabaseBackupResult:
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory(prefix="svontai-db-backup-") as temp_dir:
            directory = Path(temp_dir)
            directory.chmod(0o700)
            dump_path = directory / "database.dump"
            encrypted_path = directory / "database.dump.aes256gcm"
            decrypted_path = directory / "database.restore.dump"

            self._create_dump(dump_path)
            plaintext_sha256 = self._sha256(dump_path)
            migration_heads = self._migration_heads()
            self._encrypt(dump_path, encrypted_path)
            self._decrypt(encrypted_path, decrypted_path)
            if self._sha256(decrypted_path) != plaintext_sha256:
                raise DatabaseBackupError("Encrypted backup round-trip checksum failed")

            restore_verified = False
            if settings.DATABASE_BACKUP_VERIFY_RESTORE:
                self._verify_restore(decrypted_path, migration_heads)
                restore_verified = True

            encrypted_sha256 = self._sha256(encrypted_path)
            object_key = self._object_key(now)
            self._upload(
                encrypted_path,
                object_key,
                encrypted_sha256,
                migration_heads,
                restore_verified,
            )
            expired_removed = self._delete_expired(object_key, now)
            return DatabaseBackupResult(
                object_key=object_key,
                encrypted_size=encrypted_path.stat().st_size,
                encrypted_sha256=encrypted_sha256,
                migration_heads=migration_heads,
                restore_verified=restore_verified,
                expired_removed=expired_removed,
            )
