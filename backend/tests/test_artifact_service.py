from __future__ import annotations

import base64
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.responses import FileResponse

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
    finally:
        db.close()
        settings.ARTIFACT_STORAGE_PROVIDER = old_provider
        settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH = old_local_path
