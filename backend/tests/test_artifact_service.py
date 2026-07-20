from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.responses import FileResponse, RedirectResponse
import pytest

from app.core.config import settings
from app.schemas.tool_runner import ToolRunArtifact
from app.services.artifact_service import ArtifactService


def test_artifact_service_store_and_signed_download(client, tmp_path):
    from app.db import session as session_module

    old_provider = settings.ARTIFACT_STORAGE_PROVIDER
    old_local_path = settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH

    settings.ARTIFACT_STORAGE_PROVIDER = "local"
    settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH = str(tmp_path / "artifacts")

    db = session_module.SessionLocal()
    try:
        tenant_id = uuid.uuid4()
        request_id = "req-artifact-001"
        service = ArtifactService(db)

        persisted = service.persist_tool_artifacts(
            tenant_id=tenant_id,
            request_id=request_id,
            tool_slug="pdf_summary",
            artifacts=[
                ToolRunArtifact(
                    type="file",
                    name="summary.txt",
                    meta={
                        "content_base64": base64.b64encode(b"hello-artifact").decode("utf-8"),
                        "content_type": "text/plain",
                    },
                )
            ],
        )

        assert len(persisted) == 1
        signed_url = persisted[0].url
        assert signed_url and "/tools/artifacts/" in signed_url

        parsed = urlparse(signed_url)
        artifact_id = parsed.path.split("/tools/artifacts/")[1].split("/download")[0]
        query = parse_qs(parsed.query)
        expires = int(query["expires"][0])
        sig = query["sig"][0]

        artifact = service.verify_signed_download(uuid.UUID(artifact_id), expires, sig)
        assert artifact.storage_provider == "local"
        assert artifact.path

        response = service.build_download_response(uuid.UUID(artifact_id), expires, sig)
        assert isinstance(response, FileResponse)
        assert Path(response.path).read_bytes() == b"hello-artifact"
        assert response.headers["cache-control"] == "private, no-store, max-age=0"
        assert response.headers["x-content-type-options"] == "nosniff"
    finally:
        db.close()
        settings.ARTIFACT_STORAGE_PROVIDER = old_provider
        settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH = old_local_path


def test_supabase_bucket_is_created_once(monkeypatch):
    from app.services import artifact_service as artifact_module

    calls: list[tuple[str, str]] = []

    class _Response:
        def __init__(self, status_code: int):
            self.status_code = status_code

    class _Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url, **_kwargs):
            calls.append(("GET", url))
            return _Response(404)

        def post(self, url, **_kwargs):
            calls.append(("POST", url))
            return _Response(200)

    old_url = settings.SUPABASE_URL
    old_key = settings.SUPABASE_SERVICE_ROLE_KEY
    old_bucket = settings.SUPABASE_STORAGE_BUCKET
    settings.SUPABASE_URL = "https://project.supabase.co"
    settings.SUPABASE_SERVICE_ROLE_KEY = "service-key"
    settings.SUPABASE_STORAGE_BUCKET = "svontai-artifacts"
    monkeypatch.setattr(artifact_module.httpx, "Client", _Client)
    try:
        provider = artifact_module._SupabaseStorageProvider()
        provider.ensure_bucket()
        provider.ensure_bucket()
    finally:
        settings.SUPABASE_URL = old_url
        settings.SUPABASE_SERVICE_ROLE_KEY = old_key
        settings.SUPABASE_STORAGE_BUCKET = old_bucket

    assert [method for method, _url in calls] == ["GET", "POST"]


def test_railway_volume_sanitizes_paths_and_uses_private_permissions(client, tmp_path):
    from app.db import session as session_module

    old_provider = settings.ARTIFACT_STORAGE_PROVIDER
    old_local_path = settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH
    old_size_limit = settings.ARTIFACT_MAX_FILE_SIZE_BYTES
    settings.ARTIFACT_STORAGE_PROVIDER = "railway_volume"
    settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH = str(tmp_path / "volume")
    settings.ARTIFACT_MAX_FILE_SIZE_BYTES = 8

    db = session_module.SessionLocal()
    try:
        service = ArtifactService(db)
        persisted = service.persist_tool_artifacts(
            tenant_id=uuid.uuid4(),
            request_id="../../outside",
            tool_slug="report_generator",
            artifacts=[
                ToolRunArtifact(
                    type="file",
                    name="../../secret.txt",
                    meta={"content_base64": base64.b64encode(b"private").decode("utf-8")},
                )
            ],
        )
        stored_path = Path(persisted[0].path or "")
        assert persisted[0].storage_provider == "railway_volume"
        assert ".." not in stored_path.parts
        absolute_path = service._local_provider.resolve_path(str(stored_path))
        assert absolute_path.is_file()
        assert os.stat(absolute_path).st_mode & 0o777 == 0o600

        with pytest.raises(ValueError, match="size limit"):
            service.persist_tool_artifacts(
                tenant_id=uuid.uuid4(),
                request_id="oversized",
                tool_slug="report_generator",
                artifacts=[
                    ToolRunArtifact(
                        type="file",
                        name="large.txt",
                        meta={"content_base64": base64.b64encode(b"123456789").decode("utf-8")},
                    )
                ],
            )
    finally:
        db.close()
        settings.ARTIFACT_STORAGE_PROVIDER = old_provider
        settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH = old_local_path
        settings.ARTIFACT_MAX_FILE_SIZE_BYTES = old_size_limit


def test_r2_stores_private_artifact_and_returns_short_lived_download(client):
    from app.db import session as session_module

    class _S3Client:
        def __init__(self):
            self.upload = None
            self.signed_request = None
            self.health_bucket = None

        def head_bucket(self, **kwargs):
            self.health_bucket = kwargs["Bucket"]

        def put_object(self, **kwargs):
            self.upload = kwargs

        def generate_presigned_url(self, operation, **kwargs):
            self.signed_request = (operation, kwargs)
            return "https://private-r2.example/signed-object"

    previous = {
        "provider": settings.ARTIFACT_STORAGE_PROVIDER,
        "endpoint": settings.ARTIFACT_R2_ENDPOINT_URL,
        "access_key": settings.ARTIFACT_R2_ACCESS_KEY_ID,
        "secret_key": settings.ARTIFACT_R2_SECRET_ACCESS_KEY,
        "bucket": settings.ARTIFACT_R2_BUCKET,
        "prefix": settings.ARTIFACT_R2_PREFIX,
    }
    settings.ARTIFACT_STORAGE_PROVIDER = "r2"
    settings.ARTIFACT_R2_ENDPOINT_URL = "https://account.r2.cloudflarestorage.com"
    settings.ARTIFACT_R2_ACCESS_KEY_ID = "access-key"
    settings.ARTIFACT_R2_SECRET_ACCESS_KEY = "secret-key"
    settings.ARTIFACT_R2_BUCKET = "private-artifacts"
    settings.ARTIFACT_R2_PREFIX = "artifacts"

    db = session_module.SessionLocal()
    try:
        service = ArtifactService(db)
        fake_client = _S3Client()
        service._r2_provider._client = fake_client
        tenant_id = uuid.uuid4()
        persisted = service.persist_tool_artifacts(
            tenant_id=tenant_id,
            request_id="../../request",
            tool_slug="report generator",
            artifacts=[
                ToolRunArtifact(
                    type="file",
                    name="../../private report.txt",
                    meta={"content_base64": base64.b64encode(b"confidential").decode("utf-8")},
                )
            ],
        )

        assert persisted[0].storage_provider == "r2"
        assert persisted[0].path == f"artifacts/{tenant_id}/request/private_report.txt"
        assert fake_client.upload is not None
        assert fake_client.upload["Bucket"] == "private-artifacts"
        assert fake_client.upload["Body"] == b"confidential"
        assert "ACL" not in fake_client.upload
        assert fake_client.upload["Metadata"]["tenant-id"] == str(tenant_id)

        parsed = urlparse(persisted[0].url or "")
        artifact_id = uuid.UUID(parsed.path.split("/tools/artifacts/")[1].split("/download")[0])
        query = parse_qs(parsed.query)
        response = service.build_download_response(
            artifact_id,
            int(query["expires"][0]),
            query["sig"][0],
        )
        assert isinstance(response, RedirectResponse)
        assert response.status_code == 307
        assert response.headers["location"] == "https://private-r2.example/signed-object"
        assert response.headers["cache-control"] == "private, no-store, max-age=0"
        assert fake_client.signed_request is not None
        assert fake_client.signed_request[0] == "get_object"
        assert 60 <= fake_client.signed_request[1]["ExpiresIn"] <= 3600

        healthy, _message = service.check_storage_health()
        assert healthy is True
        assert fake_client.health_bucket == "private-artifacts"
    finally:
        db.close()
        settings.ARTIFACT_STORAGE_PROVIDER = previous["provider"]
        settings.ARTIFACT_R2_ENDPOINT_URL = previous["endpoint"]
        settings.ARTIFACT_R2_ACCESS_KEY_ID = previous["access_key"]
        settings.ARTIFACT_R2_SECRET_ACCESS_KEY = previous["secret_key"]
        settings.ARTIFACT_R2_BUCKET = previous["bucket"]
        settings.ARTIFACT_R2_PREFIX = previous["prefix"]
