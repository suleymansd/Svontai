"""
Admin API routes for system administration.
"""

from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.lead import Lead
from app.schemas.user import UserResponse, UserAdminUpdate
from app.schemas.tenant import TenantResponse
from app.core.security import get_password_hash

from pydantic import BaseModel, EmailStr


router = APIRouter(prefix="/admin", tags=["admin"])


# Schemas
class AdminStats(BaseModel):
    """Admin dashboard statistics."""
    total_users: int
    active_users: int
    total_tenants: int
    total_bots: int
    active_bots: int
    total_conversations: int
    total_messages: int
    total_leads: int
    new_users_today: int
    new_users_week: int
    messages_today: int
    messages_week: int


class UserListResponse(BaseModel):
    """Paginated user list response."""
    users: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TenantListResponse(BaseModel):
    """Paginated tenant list response."""
    tenants: list[TenantResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TenantWithOwner(TenantResponse):
    """Tenant with owner information."""
    owner_email: str
    owner_name: str
    bots_count: int
    conversations_count: int


class TenantDetailResponse(BaseModel):
    """Detailed tenant response for admin."""
    tenants: list[TenantWithOwner]
    total: int
    page: int
    page_size: int
    total_pages: int


class ActivityLog(BaseModel):
    """Activity log entry."""
    id: str
    action: str
    user_email: str | None
    details: str
    timestamp: datetime


class SystemHealth(BaseModel):
    """System health status."""
    status: str
    database: str
    api: str
    uptime: str


class CreateUserAdmin(BaseModel):
    """Admin create user schema."""
    email: EmailStr
    full_name: str
    password: str
    is_admin: bool = False


# Helper function to check admin
async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# Routes
@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get admin dashboard statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    
    # User counts
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.is_active == True)
    )
    new_users_today = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )
    new_users_week = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= week_start)
    )
    
    # Tenant counts
    total_tenants = await db.scalar(select(func.count(Tenant.id)))
    
    # Bot counts
    total_bots = await db.scalar(select(func.count(Bot.id)))
    active_bots = await db.scalar(
        select(func.count(Bot.id)).where(Bot.is_active == True)
    )
    
    # Conversation counts
    total_conversations = await db.scalar(select(func.count(Conversation.id)))
    
    # Message counts
    total_messages = await db.scalar(select(func.count(Message.id)))
    messages_today = await db.scalar(
        select(func.count(Message.id)).where(Message.created_at >= today_start)
    )
    messages_week = await db.scalar(
        select(func.count(Message.id)).where(Message.created_at >= week_start)
    )
    
    # Lead counts
    total_leads = await db.scalar(select(func.count(Lead.id)))
    
    return AdminStats(
        total_users=total_users or 0,
        active_users=active_users or 0,
        total_tenants=total_tenants or 0,
        total_bots=total_bots or 0,
        active_bots=active_bots or 0,
        total_conversations=total_conversations or 0,
        total_messages=total_messages or 0,
        total_leads=total_leads or 0,
        new_users_today=new_users_today or 0,
        new_users_week=new_users_week or 0,
        messages_today=messages_today or 0,
        messages_week=messages_week or 0
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_admin: Optional[bool] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """List all users with pagination and filters."""
    query = select(User)
    count_query = select(func.count(User.id))
    
    # Apply filters
    if search:
        search_filter = User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    if is_admin is not None:
        query = query.where(User.is_admin == is_admin)
        count_query = count_query.where(User.is_admin == is_admin)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    
    # Get total count
    total = await db.scalar(count_query) or 0
    total_pages = (total + page_size - 1) // page_size
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: CreateUserAdmin,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create a new user (admin only)."""
    # Check if email already exists
    existing = await db.scalar(
        select(User).where(User.email == user_data.email)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=get_password_hash(user_data.password),
        is_admin=user_data.is_admin,
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get user by ID."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_update: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update user (admin only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-demotion
    if user.id == admin.id and user_update.is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin privileges"
        )
    
    # Update fields
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete user (admin only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deletion
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    await db.delete(user)
    await db.commit()


@router.get("/tenants", response_model=TenantDetailResponse)
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """List all tenants with pagination."""
    query = select(Tenant, User).join(User, Tenant.owner_id == User.id)
    count_query = select(func.count(Tenant.id))
    
    if search:
        search_filter = Tenant.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    total = await db.scalar(count_query) or 0
    total_pages = (total + page_size - 1) // page_size
    
    offset = (page - 1) * page_size
    query = query.order_by(Tenant.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    rows = result.all()
    
    tenants = []
    for tenant, owner in rows:
        # Get bot count
        bot_count = await db.scalar(
            select(func.count(Bot.id)).where(Bot.tenant_id == tenant.id)
        ) or 0
        
        # Get conversation count
        conv_count = await db.scalar(
            select(func.count(Conversation.id))
            .join(Bot, Conversation.bot_id == Bot.id)
            .where(Bot.tenant_id == tenant.id)
        ) or 0
        
        tenants.append(TenantWithOwner(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            owner_email=owner.email,
            owner_name=owner.full_name,
            bots_count=bot_count,
            conversations_count=conv_count
        ))
    
    return TenantDetailResponse(
        tenants=tenants,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete tenant (admin only)."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    await db.delete(tenant)
    await db.commit()


@router.get("/health", response_model=SystemHealth)
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get system health status."""
    # Check database
    try:
        await db.execute(select(1))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    return SystemHealth(
        status="operational",
        database=db_status,
        api="healthy",
        uptime="N/A"
    )


@router.post("/make-admin/{user_id}", response_model=UserResponse)
async def make_user_admin(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Make a user admin."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_admin = True
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)

