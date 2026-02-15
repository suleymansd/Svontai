"""
Tenant API key management endpoints.

Implements:
- generate once
- store hash + last4
- re-auth (password confirm) for create/revoke
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.api_key import TenantApiKey
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.api_key import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyRevokeRequest,
)
from app.services.audit_log_service import AuditLogService
from app.services.api_key_service import ApiKeyService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

MAX_KEYS_PER_TENANT = 10


def _require_api_access(db: Session, tenant_id: UUID) -> None:
    if not SubscriptionService(db).check_feature(tenant_id, "api_access"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API erişimi için planınızı yükseltin (API Access)."
        )


def _require_reauth(user: User, password: str) -> None:
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Şifre doğrulanamadı"
        )


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    include_revoked: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> ApiKeyListResponse:
    _require_api_access(db, tenant.id)

    query = db.query(TenantApiKey).filter(TenantApiKey.tenant_id == tenant.id)
    if not include_revoked:
        query = query.filter(TenantApiKey.revoked_at.is_(None))
    items = query.order_by(TenantApiKey.created_at.desc()).all()
    return ApiKeyListResponse(items=[ApiKeyResponse.model_validate(item) for item in items])


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> ApiKeyCreateResponse:
    _require_api_access(db, tenant.id)
    _require_reauth(current_user, payload.current_password)

    current_count = db.query(TenantApiKey).filter(
        TenantApiKey.tenant_id == tenant.id,
        TenantApiKey.revoked_at.is_(None)
    ).count()
    if current_count >= MAX_KEYS_PER_TENANT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"En fazla {MAX_KEYS_PER_TENANT} aktif API anahtarı oluşturabilirsiniz"
        )

    secret = ApiKeyService.generate_secret()
    last4 = ApiKeyService.last4(secret)
    key_hash = ApiKeyService.hash_secret(secret)

    record = TenantApiKey(
        tenant_id=tenant.id,
        created_by=current_user.id,
        name=payload.name.strip(),
        key_hash=key_hash,
        last4=last4,
        revoked_at=None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    AuditLogService(db).log(
        action="api_key.create",
        tenant_id=str(tenant.id),
        user_id=str(current_user.id),
        resource_type="api_key",
        resource_id=str(record.id),
        payload={"name": record.name, "last4": record.last4},
    )

    return ApiKeyCreateResponse(
        **ApiKeyResponse.model_validate(record).model_dump(),
        secret=secret,
    )


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: UUID,
    payload: ApiKeyRevokeRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> None:
    _require_api_access(db, tenant.id)
    _require_reauth(current_user, payload.current_password)

    record = db.query(TenantApiKey).filter(
        TenantApiKey.id == api_key_id,
        TenantApiKey.tenant_id == tenant.id,
        TenantApiKey.revoked_at.is_(None)
    ).first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API anahtarı bulunamadı")

    record.revoked_at = datetime.utcnow()
    db.commit()

    AuditLogService(db).log(
        action="api_key.revoke",
        tenant_id=str(tenant.id),
        user_id=str(current_user.id),
        resource_type="api_key",
        resource_id=str(record.id),
        payload={"name": record.name, "last4": record.last4},
    )

