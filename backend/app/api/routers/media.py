"""Tenant-scoped assistant media library endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import assistant_rate_limiter, rate_limit_key, require_rate_limit
from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.assistant_media import AssistantMediaAsset
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.assistant_media import AssistantMediaResponse, AssistantMediaUpdate
from app.services.assistant_media_service import AssistantMediaService
from app.services.assistant_profile_service import AssistantProfileService
from app.services.audit_log_service import AuditLogService
from app.services.system_event_service import SystemEventService
from app.services.media_enrichment_service import MediaEnrichmentService

router = APIRouter(prefix="/media", tags=["Assistant Media"])


@router.get("", response_model=list[AssistantMediaResponse])
async def list_media(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> list[dict]:
    service = AssistantMediaService(db)
    return [service.response_data(asset) for asset in service.list(current_tenant.id)]


@router.post("", response_model=AssistantMediaResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    request: Request,
    title: str = Form(..., min_length=1, max_length=160),
    description: str = Form(default="", max_length=1200),
    keywords: str = Form(default="", max_length=800),
    file: UploadFile = File(...),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"])),
) -> dict:
    require_rate_limit(
        assistant_rate_limiter,
        rate_limit_key(request, "media-upload", current_tenant.id, current_user.id),
        "Çok fazla medya yükleme isteği. Lütfen daha sonra tekrar deneyin.",
    )
    max_size = min(max(1, int(settings.ARTIFACT_MAX_FILE_SIZE_BYTES)), 25 * 1024 * 1024)
    data = await file.read(max_size + 1)
    await file.close()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Boş dosya yüklenemez.")
    if len(data) > max_size:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Dosya boyutu 25 MB sınırını aşıyor.")

    service = AssistantMediaService(db)
    try:
        detected_media_type, detected_mime_type = service.detect_media(data)
        enrichment = await MediaEnrichmentService().enrich(
            data=data,
            mime_type=detected_mime_type,
            media_type=detected_media_type,
            title=title,
            description=description,
            filename=file.filename or "media",
            keywords=keywords.split(","),
        )
        asset = service.create(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            title=title,
            description=enrichment.description,
            keywords=enrichment.keywords,
            filename=file.filename or "media",
            claimed_mime_type=file.content_type,
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    AssistantProfileService(db).update_capability(
        current_tenant,
        "media_catalog",
        enabled=True,
        config={},
    )

    AuditLogService(db).log(
        action="assistant_media.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="assistant_media",
        resource_id=str(asset.id),
        payload={
            "media_type": asset.media_type,
            "file_size_bytes": asset.file_size_bytes,
            "ai_analyzed": enrichment.ai_analyzed,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    SystemEventService(db).log(
        tenant_id=str(current_tenant.id),
        source="media_library",
        level="info",
        code="ASSISTANT_MEDIA_CREATED",
        message="Assistant media asset uploaded",
        meta_json={
            "asset_id": str(asset.id),
            "media_type": asset.media_type,
            "ai_analyzed": enrichment.ai_analyzed,
        },
    )
    return service.response_data(asset)


@router.patch("/{asset_id}", response_model=AssistantMediaResponse)
async def update_media(
    asset_id: UUID,
    payload: AssistantMediaUpdate,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"])),
) -> dict:
    require_rate_limit(
        assistant_rate_limiter,
        rate_limit_key(request, "media-update", current_tenant.id, current_user.id),
        "Çok fazla medya güncelleme isteği. Lütfen daha sonra tekrar deneyin.",
    )
    service = AssistantMediaService(db)
    asset = service.get(current_tenant.id, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medya bulunamadı.")
    update = payload.model_dump(exclude_unset=True)
    for key, value in update.items():
        if key == "title" and value is not None:
            value = value.strip()
        if key == "description" and value is not None:
            value = value.strip() or None
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    AuditLogService(db).log(
        action="assistant_media.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="assistant_media",
        resource_id=str(asset.id),
        payload={"fields": sorted(update)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    SystemEventService(db).log(
        tenant_id=str(current_tenant.id),
        source="media_library",
        level="info",
        code="ASSISTANT_MEDIA_UPDATED",
        message="Assistant media asset updated",
        meta_json={"asset_id": str(asset.id), "fields": sorted(update)},
    )
    return service.response_data(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    asset_id: UUID,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"])),
) -> None:
    require_rate_limit(
        assistant_rate_limiter,
        rate_limit_key(request, "media-delete", current_tenant.id, current_user.id),
        "Çok fazla medya silme isteği. Lütfen daha sonra tekrar deneyin.",
    )
    service = AssistantMediaService(db)
    asset = service.get(current_tenant.id, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medya bulunamadı.")
    media_type = asset.media_type
    service.delete(asset)
    AuditLogService(db).log(
        action="assistant_media.delete",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="assistant_media",
        resource_id=str(asset_id),
        payload={"media_type": media_type},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    SystemEventService(db).log(
        tenant_id=str(current_tenant.id),
        source="media_library",
        level="info",
        code="ASSISTANT_MEDIA_DELETED",
        message="Assistant media asset deleted",
        meta_json={"asset_id": str(asset_id), "media_type": media_type},
    )
