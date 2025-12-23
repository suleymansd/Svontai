"""
Tenant management router.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Create a new tenant (business).
    
    Args:
        tenant_data: Tenant creation data.
        current_user: The authenticated user.
        db: Database session.
    
    Returns:
        The created tenant.
    """
    # For MVP, limit to one tenant per user
    existing_tenant = db.query(Tenant).filter(Tenant.owner_id == current_user.id).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zaten bir işletmeniz var. MVP sürümünde kullanıcı başına bir işletme sınırı vardır."
        )
    
    tenant = Tenant(
        name=tenant_data.name,
        owner_id=current_user.id
    )
    
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    
    return tenant


@router.get("/my", response_model=list[TenantResponse])
async def get_my_tenants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> list[Tenant]:
    """
    Get tenants owned by the current user.
    
    Args:
        current_user: The authenticated user.
        db: Database session.
    
    Returns:
        List of tenants owned by the user.
    """
    tenants = db.query(Tenant).filter(Tenant.owner_id == current_user.id).all()
    return tenants


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    tenant_update: TenantUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Update a tenant.
    
    Args:
        tenant_id: The tenant ID.
        tenant_update: Fields to update.
        current_user: The authenticated user.
        db: Database session.
    
    Returns:
        Updated tenant.
    """
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.owner_id == current_user.id
    ).first()
    
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="İşletme bulunamadı"
        )
    
    update_data = tenant_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    db.commit()
    db.refresh(tenant)
    
    return tenant

