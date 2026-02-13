"""
Feature flag management router.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.user import User
from app.models.feature_flag import FeatureFlag
from app.schemas.feature_flag import FeatureFlagResponse, FeatureFlagUpsert
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/feature-flags", tags=["Feature Flags"])


@router.get("", response_model=list[FeatureFlagResponse])
async def list_feature_flags(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[FeatureFlag]:
    """List feature flags for the tenant."""
    return db.query(FeatureFlag).filter(
        FeatureFlag.tenant_id == current_tenant.id
    ).all()


@router.put("/{flag_key}", response_model=FeatureFlagResponse)
async def upsert_feature_flag(
    flag_key: str,
    payload: FeatureFlagUpsert,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["settings:write"]))
) -> FeatureFlag:
    """Create or update a feature flag for the tenant."""
    feature_flag = db.query(FeatureFlag).filter(
        FeatureFlag.tenant_id == current_tenant.id,
        FeatureFlag.key == flag_key
    ).first()

    if feature_flag:
        feature_flag.enabled = payload.enabled
        feature_flag.payload_json = payload.payload_json
    else:
        feature_flag = FeatureFlag(
            tenant_id=current_tenant.id,
            key=flag_key,
            enabled=payload.enabled,
            payload_json=payload.payload_json
        )
        db.add(feature_flag)

    db.commit()
    db.refresh(feature_flag)
    AuditLogService(db).log(
        action="feature_flag.upsert",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="feature_flag",
        resource_id=flag_key,
        payload={"enabled": feature_flag.enabled},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    return feature_flag


@router.delete("/{flag_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature_flag(
    flag_key: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["settings:write"]))
) -> None:
    """Delete a feature flag for the tenant."""
    feature_flag = db.query(FeatureFlag).filter(
        FeatureFlag.tenant_id == current_tenant.id,
        FeatureFlag.key == flag_key
    ).first()

    if feature_flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flag bulunamadı"
        )

    db.delete(feature_flag)
    db.commit()
    AuditLogService(db).log(
        action="feature_flag.delete",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="feature_flag",
        resource_id=flag_key,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
