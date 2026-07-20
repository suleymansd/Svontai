"""Artifact persistence and signed-download utilities."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import ipaddress
import logging
import os
import re
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

import boto3
import httpx
from botocore.config import Config as BotoConfig
from fastapi import HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.artifact import Artifact
from app.schemas.tool_runner import ToolRunArtifact

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StoredArtifact:
    storage_provider: str
    path: str | None
    url: str | None


class _LocalStorageProvider:
    def __init__(self, provider_name: str = "local") -> None:
        self.provider_name = provider_name
        base_path = Path(settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH or "storage/artifacts")
        if not base_path.is_absolute():
            base_path = Path.cwd() / base_path
        self.base_path = base_path.resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.base_path.chmod(0o700)

    @staticmethod
    def _safe_name(name: str, fallback: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9._-]+", "_", (name or "").strip())[:180]
        normalized = normalized.strip("._")
        return normalized or fallback

    def store_bytes(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: str,
        tool_slug: str,
        file_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredArtifact:
        max_size = max(1, int(settings.ARTIFACT_MAX_FILE_SIZE_BYTES))
        if len(data) > max_size:
            raise ValueError(f"Artifact exceeds the {max_size} byte size limit")

        safe_request_id = self._safe_name(request_id, uuid.uuid4().hex)
        fallback_name = f"{self._safe_name(tool_slug, 'artifact')}-{uuid.uuid4().hex[:8]}.bin"
        safe_name = self._safe_name(file_name, fallback_name)
        relative = Path(str(tenant_id)) / safe_request_id / safe_name
        full_path = (self.base_path / relative).resolve()
        if self.base_path not in full_path.parents:
            raise ValueError("Invalid artifact destination")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.parent.chmod(0o700)

        fd, temporary_name = tempfile.mkstemp(prefix=".upload-", dir=full_path.parent)
        try:
            with os.fdopen(fd, "wb") as temporary_file:
                temporary_file.write(data)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, full_path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return StoredArtifact(storage_provider=self.provider_name, path=str(relative), url=None)

    def resolve_path(self, relative_path: str) -> Path:
        candidate = (self.base_path / relative_path).resolve()
        if self.base_path.resolve() not in candidate.parents and candidate != self.base_path.resolve():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid artifact path")
        return candidate


class _SupabaseStorageProvider:
    def __init__(self) -> None:
        self.base_url = (settings.SUPABASE_URL or "").rstrip("/")
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY or ""
        self.bucket = settings.SUPABASE_STORAGE_BUCKET or "svontai-artifacts"
        self._bucket_ready = False

    def is_configured(self) -> bool:
        return bool(self.base_url and self.service_key and self.bucket)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
            "Content-Type": "application/json",
        }

    def ensure_bucket(self) -> None:
        if not self.is_configured():
            raise RuntimeError("Supabase storage is not configured")
        if self._bucket_ready:
            return

        with httpx.Client(timeout=20) as client:
            response = client.get(
                f"{self.base_url}/storage/v1/bucket/{quote(self.bucket, safe='')}",
                headers=self._headers(),
            )
            if response.status_code == 404:
                response = client.post(
                    f"{self.base_url}/storage/v1/bucket",
                    headers=self._headers(),
                    json={
                        "id": self.bucket,
                        "name": self.bucket,
                        "public": False,
                        "file_size_limit": 25 * 1024 * 1024,
                    },
                )
            if response.status_code not in (200, 201):
                raise RuntimeError(f"Supabase bucket check failed ({response.status_code})")
        self._bucket_ready = True

    def store_bytes(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: str,
        tool_slug: str,
        file_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredArtifact:
        if not self.is_configured():
            raise RuntimeError("Supabase storage is not configured")
        self.ensure_bucket()

        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", (file_name or "").strip()) or f"{tool_slug}.bin"
        object_path = f"{tenant_id}/{request_id}/{safe_name}"
        upload_url = f"{self.base_url}/storage/v1/object/{self.bucket}/{quote(object_path)}"
        headers = {
            **self._headers(),
            "x-upsert": "true",
            "Content-Type": content_type,
        }
        with httpx.Client(timeout=20) as client:
            response = client.post(upload_url, content=data, headers=headers)
            if response.status_code not in (200, 201):
                raise RuntimeError(f"Supabase upload failed ({response.status_code})")
        return StoredArtifact(storage_provider="supabase", path=object_path, url=None)

    def create_signed_url(self, path: str, expires_seconds: int) -> str:
        if not self.is_configured():
            raise RuntimeError("Supabase storage is not configured")
        self.ensure_bucket()

        sign_url = f"{self.base_url}/storage/v1/object/sign/{self.bucket}/{quote(path)}"
        headers = self._headers()
        with httpx.Client(timeout=20) as client:
            response = client.post(sign_url, headers=headers, json={"expiresIn": max(60, int(expires_seconds))})
            response.raise_for_status()
            payload = response.json() if response.content else {}
        signed = payload.get("signedURL") or payload.get("signedUrl")
        if not signed:
            raise RuntimeError("Supabase signed URL not returned")
        if signed.startswith("http://") or signed.startswith("https://"):
            return signed
        return f"{self.base_url}{signed}"

    def read_bytes(self, path: str) -> bytes:
        if not self.is_configured():
            raise RuntimeError("Supabase storage is not configured")
        self.ensure_bucket()
        url = f"{self.base_url}/storage/v1/object/authenticated/{self.bucket}/{quote(path)}"
        with httpx.Client(timeout=30) as client:
            response = client.get(url, headers=self._headers())
            response.raise_for_status()
            return response.content

    def delete(self, path: str) -> None:
        if not self.is_configured():
            raise RuntimeError("Supabase storage is not configured")
        self.ensure_bucket()
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{quote(path)}"
        with httpx.Client(timeout=20) as client:
            response = client.delete(url, headers=self._headers())
            if response.status_code not in (200, 204, 404):
                response.raise_for_status()


class _R2StorageProvider:
    def __init__(self) -> None:
        self.endpoint_url = (settings.ARTIFACT_R2_ENDPOINT_URL or "").rstrip("/")
        self.access_key = settings.ARTIFACT_R2_ACCESS_KEY_ID or ""
        self.secret_key = settings.ARTIFACT_R2_SECRET_ACCESS_KEY or ""
        self.bucket = settings.ARTIFACT_R2_BUCKET or ""
        self.prefix = (settings.ARTIFACT_R2_PREFIX or "artifacts").strip("/")
        self._client = None

    def is_configured(self) -> bool:
        return bool(
            self.endpoint_url.startswith("https://")
            and self.access_key
            and self.secret_key
            and self.bucket
        )

    def _s3(self):
        if not self.is_configured():
            raise RuntimeError("R2 artifact storage is not configured")
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name="auto",
                config=BotoConfig(
                    connect_timeout=5,
                    read_timeout=10,
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )
        return self._client

    @staticmethod
    def _safe_segment(value: str, fallback: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9._-]+", "_", (value or "").strip())[:180]
        return normalized.strip("._") or fallback

    def ensure_bucket(self) -> None:
        self._s3().head_bucket(Bucket=self.bucket)

    def store_bytes(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: str,
        tool_slug: str,
        file_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredArtifact:
        max_size = max(1, int(settings.ARTIFACT_MAX_FILE_SIZE_BYTES))
        if len(data) > max_size:
            raise ValueError(f"Artifact exceeds the {max_size} byte size limit")

        safe_request_id = self._safe_segment(request_id, uuid.uuid4().hex)
        fallback = f"{self._safe_segment(tool_slug, 'artifact')}-{uuid.uuid4().hex[:8]}.bin"
        safe_name = self._safe_segment(file_name, fallback)
        key_parts = [part for part in (self.prefix, str(tenant_id), safe_request_id, safe_name) if part]
        object_key = "/".join(key_parts)
        self._s3().put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
            Metadata={"tenant-id": str(tenant_id), "tool-slug": self._safe_segment(tool_slug, "tool")},
        )
        return StoredArtifact(storage_provider="r2", path=object_key, url=None)

    def create_signed_url(self, path: str, expires_seconds: int) -> str:
        return self._s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": path},
            ExpiresIn=max(60, min(3600, int(expires_seconds))),
        )

    def read_bytes(self, path: str) -> bytes:
        response = self._s3().get_object(Bucket=self.bucket, Key=path)
        return response["Body"].read()

    def delete(self, path: str) -> None:
        self._s3().delete_object(Bucket=self.bucket, Key=path)


class ArtifactService:
    def __init__(self, db: Session):
        self.db = db
        local_name = "railway_volume" if settings.ARTIFACT_STORAGE_PROVIDER == "railway_volume" else "local"
        self._local_provider = _LocalStorageProvider(local_name)
        self._supabase_provider = _SupabaseStorageProvider()
        self._r2_provider = _R2StorageProvider()

    @staticmethod
    def _artifact_signing_secret() -> str:
        return (settings.ARTIFACT_SIGNING_SECRET or settings.JWT_SECRET_KEY or "").strip()

    @staticmethod
    def _now_ts() -> int:
        return int(time.time())

    def _signature_payload(self, artifact: Artifact, expires: int) -> str:
        return f"{artifact.id}:{artifact.tenant_id}:{expires}"

    def _sign(self, payload: str) -> str:
        secret = self._artifact_signing_secret()
        if not secret:
            raise RuntimeError("Artifact signing secret is missing")
        return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _signed_download_url(self, artifact: Artifact, expires_seconds: int | None = None) -> str:
        ttl = expires_seconds or settings.ARTIFACT_SIGNED_URL_EXPIRES_SECONDS or 3600
        expires = self._now_ts() + max(60, int(ttl))
        signature = self._sign(self._signature_payload(artifact, expires))
        base = (settings.BACKEND_URL or "").rstrip("/")
        return f"{base}/tools/artifacts/{artifact.id}/download?expires={expires}&sig={signature}"

    @staticmethod
    def _decode_base64(value: str) -> bytes:
        if "," in value and value.strip().startswith("data:"):
            value = value.split(",", 1)[1]
        max_size = max(1, int(settings.ARTIFACT_MAX_FILE_SIZE_BYTES))
        max_encoded_size = ((max_size + 2) // 3) * 4 + 16
        if len(value) > max_encoded_size:
            raise ValueError(f"Artifact exceeds the {max_size} byte size limit")
        decoded = base64.b64decode(value, validate=True)
        if len(decoded) > max_size:
            raise ValueError(f"Artifact exceeds the {max_size} byte size limit")
        return decoded

    def _selected_storage_provider(self) -> str:
        return (settings.ARTIFACT_STORAGE_PROVIDER or "local").strip().lower()

    def check_storage_health(self) -> tuple[bool, str]:
        provider = self._selected_storage_provider()
        if provider == "supabase":
            try:
                self._supabase_provider.ensure_bucket()
                return True, "Supabase artifact storage bağlantısı doğrulandı."
            except Exception as exc:
                logger.warning("Supabase storage health check failed: %s", exc)
                return False, "Supabase artifact storage erişimi doğrulanamadı."
        if provider == "r2":
            try:
                self._r2_provider.ensure_bucket()
                return True, "R2 artifact storage bağlantısı doğrulandı."
            except Exception as exc:
                logger.warning("R2 artifact storage health check failed: %s", exc)
                return False, "R2 artifact storage erişimi doğrulanamadı."
        if provider == "railway_volume":
            try:
                probe = self._local_provider.base_path / ".healthcheck"
                probe.write_bytes(b"ok")
                probe.chmod(0o600)
                probe.unlink(missing_ok=True)
                return True, "Railway kalıcı artifact volume bağlantısı doğrulandı."
            except OSError as exc:
                logger.warning("Railway volume health check failed: %s", exc)
                return False, "Railway kalıcı artifact volume yazılabilir değil."
        return True, "Local artifact storage etkin."

    def _store_file_bytes(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: str,
        tool_slug: str,
        file_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredArtifact:
        provider = self._selected_storage_provider()
        if provider == "supabase":
            return self._supabase_provider.store_bytes(
                tenant_id=tenant_id,
                request_id=request_id,
                tool_slug=tool_slug,
                file_name=file_name,
                data=data,
                content_type=content_type,
            )
        if provider == "r2":
            return self._r2_provider.store_bytes(
                tenant_id=tenant_id,
                request_id=request_id,
                tool_slug=tool_slug,
                file_name=file_name,
                data=data,
                content_type=content_type,
            )
        return self._local_provider.store_bytes(
            tenant_id=tenant_id,
            request_id=request_id,
            tool_slug=tool_slug,
            file_name=file_name,
            data=data,
            content_type=content_type,
        )

    def persist_bytes(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: str,
        tool_slug: str,
        artifact_type: str,
        file_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        meta: dict | None = None,
    ) -> Artifact:
        stored = self._store_file_bytes(
            tenant_id=tenant_id,
            request_id=request_id,
            tool_slug=tool_slug,
            file_name=file_name,
            data=data,
            content_type=content_type,
        )
        row = Artifact(
            tenant_id=tenant_id,
            request_id=request_id,
            tool_slug=tool_slug,
            type=artifact_type,
            name=file_name,
            storage_provider=stored.storage_provider,
            path=stored.path,
            url=stored.url,
            meta_json={**(meta or {}), "size_bytes": len(data), "content_type": content_type},
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def read_artifact_bytes(self, artifact: Artifact) -> bytes:
        max_size = max(1, int(settings.ARTIFACT_MAX_FILE_SIZE_BYTES))
        if artifact.storage_provider in {"local", "railway_volume"} and artifact.path:
            data = self._local_provider.resolve_path(artifact.path).read_bytes()
        elif artifact.storage_provider == "supabase" and artifact.path:
            data = self._supabase_provider.read_bytes(artifact.path)
        elif artifact.storage_provider == "r2" and artifact.path:
            data = self._r2_provider.read_bytes(artifact.path)
        else:
            raise ValueError("Artifact content is not stored in a private provider")
        if len(data) > max_size:
            raise ValueError("Artifact exceeds the configured size limit")
        return data

    def delete_artifact_bytes(self, artifact: Artifact) -> None:
        if artifact.storage_provider in {"local", "railway_volume"} and artifact.path:
            self._local_provider.resolve_path(artifact.path).unlink(missing_ok=True)
        elif artifact.storage_provider == "supabase" and artifact.path:
            self._supabase_provider.delete(artifact.path)
        elif artifact.storage_provider == "r2" and artifact.path:
            self._r2_provider.delete(artifact.path)

    def persist_tool_artifacts(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: str,
        tool_slug: str,
        artifacts: list[ToolRunArtifact],
    ) -> list[ToolRunArtifact]:
        persisted: list[Artifact] = []
        for index, artifact in enumerate(artifacts):
            meta = dict(artifact.meta or {})
            storage_provider = "external"
            stored_path = None
            stored_url = artifact.url

            raw_base64 = (
                meta.pop("content_base64", None)
                or meta.pop("contentBase64", None)
                or meta.pop("base64_content", None)
            )

            if isinstance(raw_base64, str) and raw_base64.strip():
                try:
                    file_bytes = self._decode_base64(raw_base64.strip())
                except binascii.Error as exc:
                    raise ValueError(f"Invalid artifact base64 payload at index {index}") from exc

                stored = self._store_file_bytes(
                    tenant_id=tenant_id,
                    request_id=request_id,
                    tool_slug=tool_slug,
                    file_name=artifact.name or f"{tool_slug}-{index + 1}.bin",
                    data=file_bytes,
                    content_type=str(meta.get("content_type") or "application/octet-stream"),
                )
                storage_provider = stored.storage_provider
                stored_path = stored.path
                stored_url = stored.url
                meta["size_bytes"] = len(file_bytes)

            row = Artifact(
                tenant_id=tenant_id,
                request_id=request_id,
                tool_slug=tool_slug,
                type=artifact.type,
                name=artifact.name,
                storage_provider=storage_provider,
                path=stored_path,
                url=stored_url,
                meta_json=meta,
            )
            self.db.add(row)
            persisted.append(row)

        if not persisted:
            return []

        self.db.commit()
        for row in persisted:
            self.db.refresh(row)

        return [self.to_response_artifact(row) for row in persisted]

    def get_artifacts_for_request(self, tenant_id: uuid.UUID, request_id: str) -> list[Artifact]:
        return self.db.query(Artifact).filter(
            Artifact.tenant_id == tenant_id,
            Artifact.request_id == request_id,
        ).order_by(Artifact.created_at.asc()).all()

    def to_response_artifact(self, artifact: Artifact) -> ToolRunArtifact:
        meta = dict(artifact.meta_json or {})
        if artifact.url:
            meta.setdefault("sourceUrl", artifact.url)
        return ToolRunArtifact(
            id=str(artifact.id),
            type=artifact.type,
            name=artifact.name,
            url=self._signed_download_url(artifact),
            storageProvider=artifact.storage_provider,
            path=artifact.path,
            meta=meta,
        )

    def verify_signed_download(self, artifact_id: uuid.UUID, expires: int, sig: str) -> Artifact:
        if expires <= self._now_ts():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signed URL expired")

        artifact = self.db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if not artifact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        expected = self._sign(self._signature_payload(artifact, expires))
        if not hmac.compare_digest(expected, sig or ""):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid artifact signature")
        return artifact

    def build_download_response(self, artifact_id: uuid.UUID, expires: int, sig: str) -> Response:
        artifact = self.verify_signed_download(artifact_id, expires, sig)
        remaining_seconds = max(60, expires - self._now_ts())

        private_headers = {
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        }

        if artifact.storage_provider in {"local", "railway_volume"} and artifact.path:
            file_path = self._local_provider.resolve_path(artifact.path)
            if not file_path.exists():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file not found")
            media_type = (artifact.meta_json or {}).get("content_type")
            return FileResponse(
                path=file_path,
                filename=_LocalStorageProvider._safe_name(artifact.name, "artifact.bin"),
                media_type=media_type,
                headers=private_headers,
            )

        if artifact.storage_provider == "supabase" and artifact.path:
            try:
                signed = self._supabase_provider.create_signed_url(artifact.path, remaining_seconds)
                return RedirectResponse(url=signed, status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers=private_headers)
            except Exception as exc:
                logger.warning("Supabase signed url generation failed: %s", exc)
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Supabase signed URL failed")

        if artifact.storage_provider == "r2" and artifact.path:
            try:
                signed = self._r2_provider.create_signed_url(artifact.path, remaining_seconds)
                return RedirectResponse(url=signed, status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers=private_headers)
            except Exception as exc:
                logger.warning("R2 artifact signed url generation failed: %s", exc)
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Artifact download URL failed")

        if artifact.url:
            parsed = urlparse(artifact.url)
            host = (parsed.hostname or "").lower()
            unsafe_host = not host or host == "localhost" or host.endswith(".local")
            try:
                address = ipaddress.ip_address(host)
                unsafe_host = unsafe_host or any(
                    (
                        address.is_private,
                        address.is_loopback,
                        address.is_link_local,
                        address.is_reserved,
                        address.is_unspecified,
                    )
                )
            except ValueError:
                pass
            if parsed.scheme != "https" or parsed.username or parsed.password or unsafe_host:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsafe artifact source URL")
            return RedirectResponse(url=artifact.url, status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers=private_headers)

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact source unavailable")
