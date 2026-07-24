"""Tenant data retention policy endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.rate_limit import RateLimiter, rate_limit_key, require_rate_limit
from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_log_service import AuditLogService
from app.services.data_retention_service import DataRetentionService
from app.services.system_event_service import SystemEventService


router = APIRouter(prefix="/data-retention", tags=["data-retention"])
retention_rate_limiter = RateLimiter(5, 3600, "data-retention")


class RetentionPolicyUpdate(BaseModel):
    enabled: bool
    message_content_days: int = Field(ge=30, le=3650)
    raw_payload_days: int = Field(ge=7, le=365)
    product_analytics_days: int = Field(ge=30, le=730)
    usage_log_days: int = Field(ge=90, le=3650)
    system_event_days: int = Field(ge=90, le=3650)


class RetentionPolicyResponse(RetentionPolicyUpdate):
    tenant_id: str
    legal_hold: bool
    last_run_at: datetime | None
    last_result: dict
    updated_at: datetime


@router.get("", response_model=RetentionPolicyResponse)
async def get_retention_policy(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> dict:
    service = DataRetentionService(db)
    return service.serialize(service.get_or_create(tenant.id))


@router.get("/preview")
async def preview_retention(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> dict:
    service = DataRetentionService(db)
    policy = service.get_or_create(tenant.id)
    return {"policy": service.serialize(policy), "eligible_records": service.preview(tenant.id, policy)}


@router.patch("", response_model=RetentionPolicyResponse)
async def update_retention_policy(
    payload: RetentionPolicyUpdate,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"])),
) -> dict:
    service = DataRetentionService(db)
    policy = service.get_or_create(tenant.id)
    for key, value in payload.model_dump().items():
        setattr(policy, key, value)
    db.commit()
    db.refresh(policy)
    AuditLogService(db).log(
        action="data_retention.update",
        tenant_id=str(tenant.id),
        user_id=str(current_user.id),
        resource_type="data_retention_policy",
        resource_id=str(tenant.id),
        payload=payload.model_dump(),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return service.serialize(policy)


@router.post("/run")
async def run_retention_now(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"])),
) -> dict:
    require_rate_limit(
        retention_rate_limiter,
        rate_limit_key(request, "retention-run", tenant.id, current_user.id),
        "Veri temizliği saatte en fazla beş kez çalıştırılabilir.",
    )
    result = DataRetentionService(db).run(tenant.id, force=True)
    AuditLogService(db).log(
        action="data_retention.run",
        tenant_id=str(tenant.id),
        user_id=str(current_user.id),
        resource_type="data_retention_policy",
        resource_id=str(tenant.id),
        payload={"status": result["status"], "deleted": result.get("deleted", {})},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    SystemEventService(db).log(
        tenant_id=str(tenant.id),
        source="retention",
        level="info",
        code="DATA_RETENTION_COMPLETED",
        message="Tenant veri saklama politikası çalıştırıldı.",
        meta_json={"status": result["status"], "deleted": result.get("deleted", {})},
    )
    return result
