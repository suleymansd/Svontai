"""
Authentication dependencies for FastAPI.
"""

from uuid import UUID
from datetime import datetime
from app.core.time import utc_now_naive
from typing import Any

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import decode_token
from app.core.config import settings
from app.models.session import UserSession
from app.models.user import User
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.services.rbac_service import RbacService
from app.services.tenant_provisioning_service import TenantProvisioningService

# HTTP Bearer scheme for JWT authentication
security = HTTPBearer()

def _decode_and_validate_access_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token geçersiz veya süresi dolmuş",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token türü",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("sub") is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token'da kullanıcı bilgisi bulunamadı",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_access_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """
    Dependency to get the current access token payload.

    Used for portal/session gating without duplicating JWT parsing logic in routers.
    """
    return _decode_and_validate_access_token(credentials.credentials)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    
    Args:
        credentials: The HTTP Bearer credentials.
        db: Database session.
    
    Returns:
        The authenticated User model.
    
    Raises:
        HTTPException: If token is invalid or user not found.
    """
    token = credentials.credentials

    payload = _decode_and_validate_access_token(token)
    try:
        user_id = UUID(str(payload["sub"]))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token'da kullanıcı bilgisi geçersiz",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap devre dışı bırakılmış"
        )

    session_id = payload.get("sid")
    if session_id:
        try:
            session_uuid = UUID(str(session_id))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Oturum geçersiz",
                headers={"WWW-Authenticate": "Bearer"},
            )
        active_session = db.query(UserSession).filter(
            UserSession.id == session_uuid,
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > utc_now_naive(),
        ).first()
        if active_session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Oturum sonlandırılmış veya süresi dolmuş",
                headers={"WWW-Authenticate": "Bearer"},
            )
    elif settings.ENVIRONMENT == "prod":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum bilgisi bulunmayan token kabul edilmedi",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.is_admin and settings.SUPER_ADMIN_REQUIRE_2FA and (
        not user.two_factor_enabled or payload.get("mfa") is not True
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SUPER_ADMIN_MFA_REQUIRED",
                "message": "Bu admin oturumu iki faktörlü doğrulama ile yeniden açılmalıdır.",
            },
        )

    if user.locked_until and user.locked_until > utc_now_naive():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap geçici olarak kilitlendi"
        )
    
    return user


async def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_tenant_id: UUID | None = Header(default=None, alias="X-Tenant-ID")
) -> Tenant:
    """
    Dependency to get the current user's tenant.
    For MVP, we assume each user has exactly one tenant.
    
    Args:
        current_user: The authenticated user.
        db: Database session.
    
    Returns:
        The user's Tenant model.
    
    Raises:
        HTTPException: If user has no tenant.
    """
    if x_tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == x_tenant_id).first()
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="İşletme bulunamadı"
            )
        membership = db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.user_id == current_user.id,
            TenantMembership.status == "active"
        ).first()
        if membership is None and tenant.owner_id != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işletmeye erişim yetkiniz yok"
            )
        if tenant.settings and tenant.settings.get("suspended") and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="İşletme askıya alınmış"
            )
        return tenant

    tenant = db.query(Tenant).filter(Tenant.owner_id == current_user.id).first()
    
    if tenant is None:
        membership = db.query(TenantMembership).filter(
            TenantMembership.user_id == current_user.id,
            TenantMembership.status == "active"
        ).first()
        if membership:
            tenant = membership.tenant
        elif not current_user.is_admin:
            tenant = TenantProvisioningService(db).ensure_for_user(current_user)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Henüz bir işletme oluşturmadınız"
            )

    if tenant.settings and tenant.settings.get("suspended") and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="İşletme askıya alınmış"
        )
    
    return tenant


async def get_current_membership(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> TenantMembership:
    """
    Dependency to get the current user's membership for the active tenant.
    """
    membership = db.query(TenantMembership).filter(
        TenantMembership.user_id == current_user.id,
        TenantMembership.tenant_id == current_tenant.id,
        TenantMembership.status == "active"
    ).first()

    if membership:
        return membership

    if current_tenant.owner_id == current_user.id:
        rbac = RbacService(db)
        rbac.ensure_defaults()
        owner_role = rbac.get_role_by_name("owner")
        if owner_role:
            membership = TenantMembership(
                tenant_id=current_tenant.id,
                user_id=current_user.id,
                role_id=owner_role.id,
                status="active"
            )
            db.add(membership)
            db.commit()
            db.refresh(membership)
            return membership

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bu işletmeye erişim yetkiniz yok"
    )
