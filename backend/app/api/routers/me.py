"""
/api/me endpoint for aggregated user context.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant, get_current_membership, get_access_token_payload
from app.models.user import User
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.schemas.me import MeResponse
from app.schemas.rbac import RoleResponse
from app.core.permissions import PERMISSIONS
from app.services.rbac_service import RbacService
from app.services.subscription_service import SubscriptionService
from app.services.feature_flag_service import FeatureFlagService

router = APIRouter(prefix="/api/me", tags=["Me"])


def _resolve_admin_tenant_context(
    current_user: User,
    db: Session,
    x_tenant_id: UUID | None
) -> tuple[Tenant | None, TenantMembership | None]:
    tenant: Tenant | None
    membership: TenantMembership | None = None

    if x_tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == x_tenant_id).first()
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="İşletme bulunamadı"
            )
    else:
        tenant = db.query(Tenant).filter(Tenant.owner_id == current_user.id).first()
        if tenant is None:
            membership = db.query(TenantMembership).filter(
                TenantMembership.user_id == current_user.id,
                TenantMembership.status == "active"
            ).first()
            tenant = membership.tenant if membership else None

    if tenant is None:
        return None, None

    if membership is None:
        membership = db.query(TenantMembership).filter(
            TenantMembership.user_id == current_user.id,
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.status == "active"
        ).first()

    return tenant, membership


@router.get("", response_model=MeResponse)
async def get_context(
    current_user: User = Depends(get_current_user),
    token_payload: dict = Depends(get_access_token_payload),
    db: Session = Depends(get_db),
    x_tenant_id: UUID | None = Header(default=None, alias="X-Tenant-ID")
) -> MeResponse:
    """Return aggregated user context."""
    rbac_service = RbacService(db)
    subscription_service = SubscriptionService(db)
    feature_flag_service = FeatureFlagService(db)

    current_tenant: Tenant | None
    membership: TenantMembership | None

    if current_user.is_admin:
        portal = (token_payload.get("portal") or "tenant").strip()
        # Super admin portal: do not auto-pick a tenant unless explicitly selected.
        if portal == "super_admin" and x_tenant_id is None:
            current_tenant, membership = None, None
        else:
            current_tenant, membership = _resolve_admin_tenant_context(current_user, db, x_tenant_id)
    else:
        current_tenant = await get_current_tenant(
            current_user=current_user,
            db=db,
            x_tenant_id=x_tenant_id
        )
        membership = await get_current_membership(
            current_user=current_user,
            current_tenant=current_tenant,
            db=db
        )

    entitlements: dict = {}
    feature_flags: dict = {}

    if current_tenant:
        entitlements = subscription_service.get_usage_stats(current_tenant.id)
        feature_flags = entitlements.get("features", {}).copy()
        tenant_flags = feature_flag_service.get_flags_for_tenant(current_tenant.id)
        feature_flags.update(tenant_flags)

    if current_user.is_admin:
        role = rbac_service.get_role_by_name("system_admin")
        if role is None and membership is not None:
            db.refresh(membership, ["role"])
            role = membership.role
        permissions = PERMISSIONS
    else:
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işletmeye erişim yetkiniz yok"
            )
        # Refresh only direct relationships; nested paths aren't supported by refresh()
        db.refresh(membership, ["role"])
        role = membership.role
        permissions = [perm.key for perm in role.permissions]

    return MeResponse(
        user=current_user,
        tenant=current_tenant,
        role=RoleResponse.model_validate(role) if role else None,
        permissions=permissions,
        entitlements=entitlements,
        feature_flags=feature_flags
    )
