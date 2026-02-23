"""Artifact persistence and signed-download utilities."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx
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
    def __init__(self) -> None:
        base_path = Path(settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH or "storage/artifacts")
        if not base_path.is_absolute():
            base_path = Path.cwd() / base_path
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_name(name: str, fallback: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9._-]+", "_", (name or "").strip())
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
    ) -> StoredArtifact:
        fallback_name = f"{tool_slug}-{uuid.uuid4().hex[:8]}.bin"
        safe_name = self._safe_name(file_name, fallback_name)
        relative = Path(str(tenant_id)) / request_id / safe_name
        full_path = self.base_path / relative
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(data)
        return StoredArtifact(storage_provider="local", path=str(relative), url=None)

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

    def is_configured(self) -> bool:
        return bool(self.base_url and self.service_key and self.bucket)

    def store_bytes(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: str,
        tool_slug: str,
        file_name: str,
        data: bytes,
    ) -> StoredArtifact:
        if not self.is_configured():
            raise RuntimeError("Supabase storage is not configured")

        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", (file_name or "").strip()) or f"{tool_slug}.bin"
        object_path = f"{tenant_id}/{request_id}/{safe_name}"
        upload_url = f"{self.base_url}/storage/v1/object/{self.bucket}/{quote(object_path)}"
        headers = {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
            "x-upsert": "true",
            "Content-Type": "application/octet-stream",
        }
        with httpx.Client(timeout=20) as client:
            response = client.post(upload_url, content=data, headers=headers)
            if response.status_code not in (200, 201):
                raise RuntimeError(f"Supabase upload failed ({response.status_code})")
        return StoredArtifact(storage_provider="supabase", path=object_path, url=None)

    def create_signed_url(self, path: str, expires_seconds: int) -> str:
        if not self.is_configured():
            raise RuntimeError("Supabase storage is not configured")

        sign_url = f"{self.base_url}/storage/v1/object/sign/{self.bucket}/{quote(path)}"
        headers = {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
            "Content-Type": "application/json",
        }
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


class ArtifactService:
    def __init__(self, db: Session):
        self.db = db
        self._local_provider = _LocalStorageProvider()
        self._supabase_provider = _SupabaseStorageProvider()

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
        return base64.b64decode(value, validate=True)

    def _selected_storage_provider(self) -> str:
        return (settings.ARTIFACT_STORAGE_PROVIDER or "local").strip().lower()

    def _store_file_bytes(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: str,
        tool_slug: str,
        file_name: str,
        data: bytes,
    ) -> StoredArtifact:
        provider = self._selected_storage_provider()
        if provider == "supabase":
            return self._supabase_provider.store_bytes(
                tenant_id=tenant_id,
                request_id=request_id,
                tool_slug=tool_slug,
                file_name=file_name,
                data=data,
            )
        return self._local_provider.store_bytes(
            tenant_id=tenant_id,
            request_id=request_id,
            tool_slug=tool_slug,
            file_name=file_name,
            data=data,
        )

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
                except (binascii.Error, ValueError) as exc:
                    raise ValueError(f"Invalid artifact base64 payload at index {index}") from exc

                stored = self._store_file_bytes(
                    tenant_id=tenant_id,
                    request_id=request_id,
                    tool_slug=tool_slug,
                    file_name=artifact.name or f"{tool_slug}-{index + 1}.bin",
                    data=file_bytes,
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

        if artifact.storage_provider == "local" and artifact.path:
            file_path = self._local_provider.resolve_path(artifact.path)
            if not file_path.exists():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file not found")
            media_type = (artifact.meta_json or {}).get("content_type")
            return FileResponse(path=file_path, filename=artifact.name, media_type=media_type)

        if artifact.storage_provider == "supabase" and artifact.path:
            try:
                signed = self._supabase_provider.create_signed_url(artifact.path, remaining_seconds)
                return RedirectResponse(url=signed, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
            except Exception as exc:
                logger.warning("Supabase signed url generation failed: %s", exc)
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Supabase signed URL failed")

        if artifact.url:
            return RedirectResponse(url=artifact.url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact source unavailable")
