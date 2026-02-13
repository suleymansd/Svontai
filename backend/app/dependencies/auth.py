"""
Authentication dependencies for FastAPI.
"""

from uuid import UUID
from datetime import datetime

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.services.rbac_service import RbacService

# HTTP Bearer scheme for JWT authentication
security = HTTPBearer()


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
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token geçersiz veya süresi dolmuş",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token türü",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token'da kullanıcı bilgisi bulunamadı",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    
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

    if user.locked_until and user.locked_until > datetime.utcnow():
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
