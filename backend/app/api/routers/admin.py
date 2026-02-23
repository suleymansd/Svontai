"""
Admin API routes for system administration.
"""

import logging
from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import select, func, and_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_access_token_payload
from app.models.user import User
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.lead import Lead
from app.models.automation import AutomationRun
from app.models.subscription import TenantSubscription
from app.models.feature_flag import FeatureFlag
from app.models.incident import Incident
from app.models.plan import Plan
from app.models.tool import Tool
from app.models.onboarding import AuditLog
from app.models.real_estate import RealEstatePackSettings
from app.schemas.user import UserResponse, UserAdminUpdate
from app.schemas.tenant import TenantResponse
from app.schemas.plan import PlanCreate, PlanUpdate, PlanResponse
from app.schemas.tool import ToolCreate, ToolUpdate, ToolResponse
from app.core.security import get_password_hash
from app.services.real_estate_service import RealEstateService
from app.services.tool_seed_service import seed_initial_tools

from pydantic import BaseModel, EmailStr


router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


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


class RecentRun(BaseModel):
    id: str
    status: str
    created_at: datetime


class RecentIncident(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    created_at: datetime


class TenantAdminDetail(BaseModel):
    tenant: TenantResponse
    owner_email: str
    owner_name: str
    plan_name: str | None
    feature_flags: list[str]
    recent_runs: list[RecentRun]
    recent_incidents: list[RecentIncident]


class AuditLogResponse(BaseModel):
    id: str
    tenant_id: str | None
    user_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    payload_json: dict | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class FeatureFlagUpdate(BaseModel):
    enabled_flags: list[str]


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


class PlanListResponse(BaseModel):
    items: list[PlanResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ToolListResponse(BaseModel):
    items: list[ToolResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ToolSeedResponse(BaseModel):
    created: int
    updated: int
    total: int


class RealEstatePackAdminUpdate(BaseModel):
    enabled: bool
    lead_limit_monthly: int = 300
    pdf_limit_monthly: int = 200
    followup_limit_monthly: int = 600


class RealEstatePackAdminResponse(BaseModel):
    tenant_id: str
    enabled: bool
    lead_limit_monthly: int
    pdf_limit_monthly: int
    followup_limit_monthly: int
    followup_days: int
    followup_attempts: int
    persona: str


# Helper function to check admin
async def require_admin(
    current_user: User = Depends(get_current_user),
    token_payload: dict = Depends(get_access_token_payload),
) -> User:
    """Require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    portal = (token_payload.get("portal") or "tenant").strip()
    if portal != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin paneline erişmek için Super Admin girişi yapın."
        )
    return current_user


def log_admin_action(
    db: Session,
    admin: User,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    payload: dict | None = None,
    request: Request | None = None
) -> None:
    db.add(
        AuditLog(
            tenant_id=None,
            user_id=admin.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload_json=payload,
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("User-Agent") if request else None
        )
    )


# Routes
@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get admin dashboard statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    
    # User counts
    total_users = db.execute(
        select(func.count()).select_from(User)
    ).scalar() or 0
    active_users = db.execute(
        select(func.count()).select_from(User).where(User.is_active.is_(True))
    ).scalar() or 0
    new_users_today = db.execute(
        select(func.count()).select_from(User).where(User.created_at >= today_start)
    ).scalar() or 0
    new_users_week = db.execute(
        select(func.count()).select_from(User).where(User.created_at >= week_start)
    ).scalar() or 0

    # Tenant counts
    total_tenants = db.execute(
        select(func.count()).select_from(Tenant)
    ).scalar() or 0

    # Bot counts
    total_bots = db.execute(
        select(func.count()).select_from(Bot)
    ).scalar() or 0
    active_bots = db.execute(
        select(func.count()).select_from(Bot).where(Bot.is_active.is_(True))
    ).scalar() or 0

    # Conversation counts
    total_conversations = db.execute(
        select(func.count()).select_from(Conversation)
    ).scalar() or 0

    # Message counts
    total_messages = db.execute(
        select(func.count()).select_from(Message)
    ).scalar() or 0
    messages_today = db.execute(
        select(func.count()).select_from(Message).where(Message.created_at >= today_start)
    ).scalar() or 0
    messages_week = db.execute(
        select(func.count()).select_from(Message).where(Message.created_at >= week_start)
    ).scalar() or 0

    # Lead counts
    total_leads = db.execute(
        select(func.count()).select_from(Lead)
    ).scalar() or 0
    
    return AdminStats(
        total_users=total_users,
        active_users=active_users,
        total_tenants=total_tenants,
        total_bots=total_bots,
        active_bots=active_bots,
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_leads=total_leads,
        new_users_today=new_users_today,
        new_users_week=new_users_week,
        messages_today=messages_today,
        messages_week=messages_week
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_admin: Optional[bool] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """List all users with pagination and filters."""
    query = db.query(User)
    count_query = db.query(func.count(User.id))
    
    # Apply filters
    if search:
        search_filter = User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%")
        query = query.filter(search_filter)
        count_query = count_query.filter(search_filter)
    
    if is_admin is not None:
        query = query.filter(User.is_admin == is_admin)
        count_query = count_query.filter(User.is_admin == is_admin)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
        count_query = count_query.filter(User.is_active == is_active)
    
    # Get total count
    total = count_query.scalar() or 0
    total_pages = (total + page_size - 1) // page_size
    
    # Apply pagination
    offset = (page - 1) * page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()
    
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
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    """Create a new user (admin only)."""
    # Check if email already exists
    existing = db.query(User).filter(User.email == user_data.email).first()
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
    log_admin_action(
        db,
        admin,
        "admin.user.create",
        "user",
        None,
        {"email": user.email, "is_admin": user.is_admin},
        request=request
    )
    db.commit()
    db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get user by ID."""
    user = db.get(User, user_id)
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
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    """Update user (admin only)."""
    user = db.get(User, user_id)
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

    if update_data:
        log_admin_action(
            db,
            admin,
            "admin.user.update",
            "user",
            str(user.id),
            update_data,
            request=request
        )

    db.commit()
    db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    """Delete user (admin only)."""
    user = db.get(User, user_id)
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

    log_admin_action(
        db,
        admin,
        "admin.user.delete",
        "user",
        str(user.id),
        {"email": user.email},
        request=request
    )

    db.delete(user)
    db.commit()


@router.get("/tenants", response_model=TenantDetailResponse)
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """List all tenants with pagination."""
    bot_counts = (
        db.query(
            Bot.tenant_id.label("tenant_id"),
            func.count(Bot.id).label("bot_count")
        )
        .group_by(Bot.tenant_id)
        .subquery()
    )
    conv_counts = (
        db.query(
            Bot.tenant_id.label("tenant_id"),
            func.count(Conversation.id).label("conv_count")
        )
        .join(Conversation, Conversation.bot_id == Bot.id)
        .group_by(Bot.tenant_id)
        .subquery()
    )

    query = (
        db.query(
            Tenant,
            User,
            func.coalesce(bot_counts.c.bot_count, 0).label("bot_count"),
            func.coalesce(conv_counts.c.conv_count, 0).label("conv_count")
        )
        .join(User, Tenant.owner_id == User.id)
        .outerjoin(bot_counts, bot_counts.c.tenant_id == Tenant.id)
        .outerjoin(conv_counts, conv_counts.c.tenant_id == Tenant.id)
    )
    count_query = db.query(func.count(Tenant.id))
    
    if search:
        search_filter = Tenant.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        query = query.filter(search_filter)
        count_query = count_query.filter(search_filter)
    
    total = count_query.scalar() or 0
    total_pages = (total + page_size - 1) // page_size
    
    offset = (page - 1) * page_size
    rows = query.order_by(Tenant.created_at.desc()).offset(offset).limit(page_size).all()
    
    tenants = []
    for tenant, owner, bot_count, conv_count in rows:
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


@router.get("/tenants/{tenant_id}", response_model=TenantAdminDetail)
async def get_tenant_detail(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    owner = db.get(User, tenant.owner_id)
    subscription = db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant.id).first()
    plan_name = None
    if subscription:
        plan = db.get(Plan, subscription.plan_id)
        plan_name = plan.display_name if plan else None

    flags = db.query(FeatureFlag).filter(
        FeatureFlag.tenant_id == tenant.id,
        FeatureFlag.enabled == True
    ).all()
    feature_flags = [flag.key for flag in flags]

    runs = db.query(AutomationRun).filter(
        AutomationRun.tenant_id == str(tenant.id)
    ).order_by(AutomationRun.created_at.desc()).limit(5).all()

    incidents = db.query(Incident).filter(
        Incident.tenant_id == str(tenant.id)
    ).order_by(Incident.created_at.desc()).limit(5).all()

    return TenantAdminDetail(
        tenant=TenantResponse.model_validate(tenant),
        owner_email=owner.email if owner else "",
        owner_name=owner.full_name if owner else "",
        plan_name=plan_name,
        feature_flags=feature_flags,
        recent_runs=[RecentRun(id=r.id, status=r.status, created_at=r.created_at) for r in runs],
        recent_incidents=[RecentIncident(id=i.id, title=i.title, severity=i.severity, status=i.status, created_at=i.created_at) for i in incidents],
    )


@router.patch("/tenants/{tenant_id}/feature-flags", response_model=TenantAdminDetail)
async def update_tenant_feature_flags(
    tenant_id: UUID,
    payload: FeatureFlagUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    existing_flags = db.query(FeatureFlag).filter(FeatureFlag.tenant_id == tenant.id).all()
    existing_map = {flag.key: flag for flag in existing_flags}

    for key, flag in existing_map.items():
        flag.enabled = key in payload.enabled_flags

    for key in payload.enabled_flags:
        if key not in existing_map:
            db.add(FeatureFlag(tenant_id=tenant.id, key=key, enabled=True))

    log_admin_action(
        db,
        admin,
        "admin.tenant.feature_flags.update",
        "tenant",
        str(tenant.id),
        {"enabled_flags": payload.enabled_flags},
        request=request
    )

    db.commit()

    return await get_tenant_detail(tenant_id, db, admin)


@router.post("/tenants/{tenant_id}/suspend", status_code=status.HTTP_200_OK)
async def suspend_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    tenant.settings = {**(tenant.settings or {}), "suspended": True}
    log_admin_action(
        db,
        admin,
        "admin.tenant.suspend",
        "tenant",
        str(tenant.id),
        {"suspended": True},
        request=request
    )
    db.commit()
    return {"status": "suspended"}


@router.post("/tenants/{tenant_id}/unsuspend", status_code=status.HTTP_200_OK)
async def unsuspend_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    tenant.settings = {**(tenant.settings or {}), "suspended": False}
    log_admin_action(
        db,
        admin,
        "admin.tenant.unsuspend",
        "tenant",
        str(tenant.id),
        {"suspended": False},
        request=request
    )
    db.commit()
    return {"status": "active"}


@router.get("/tenants/{tenant_id}/real-estate-pack", response_model=RealEstatePackAdminResponse)
async def get_tenant_real_estate_pack(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    service = RealEstateService(db)
    settings = service.get_or_create_settings(tenant.id)
    enabled = settings.enabled or bool(db.query(FeatureFlag).filter(
        FeatureFlag.tenant_id == tenant.id,
        FeatureFlag.key == "real_estate_pack",
        FeatureFlag.enabled.is_(True)
    ).first())

    return RealEstatePackAdminResponse(
        tenant_id=str(tenant.id),
        enabled=enabled,
        lead_limit_monthly=settings.lead_limit_monthly,
        pdf_limit_monthly=settings.pdf_limit_monthly,
        followup_limit_monthly=settings.followup_limit_monthly,
        followup_days=settings.followup_days,
        followup_attempts=settings.followup_attempts,
        persona=settings.persona,
    )


@router.put("/tenants/{tenant_id}/real-estate-pack", response_model=RealEstatePackAdminResponse)
async def update_tenant_real_estate_pack(
    tenant_id: UUID,
    payload: RealEstatePackAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    service = RealEstateService(db)
    settings = service.upsert_settings(
        tenant.id,
        {
            "enabled": payload.enabled,
            "lead_limit_monthly": payload.lead_limit_monthly,
            "pdf_limit_monthly": payload.pdf_limit_monthly,
            "followup_limit_monthly": payload.followup_limit_monthly,
        }
    )

    log_admin_action(
        db,
        admin,
        "admin.tenant.real_estate_pack.update",
        "tenant",
        str(tenant.id),
        payload.model_dump(),
        request=request
    )
    db.commit()

    return RealEstatePackAdminResponse(
        tenant_id=str(tenant.id),
        enabled=settings.enabled,
        lead_limit_monthly=settings.lead_limit_monthly,
        pdf_limit_monthly=settings.pdf_limit_monthly,
        followup_limit_monthly=settings.followup_limit_monthly,
        followup_days=settings.followup_days,
        followup_attempts=settings.followup_attempts,
        persona=settings.persona,
    )


@router.get("/audit", response_model=list[AuditLogResponse])
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    tenant_id: Optional[str] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = db.query(AuditLog)
    if tenant_id:
        query = query.filter(AuditLog.tenant_id == tenant_id)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/plans", response_model=PlanListResponse)
async def list_plans_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_public: Optional[bool] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = db.query(Plan)
    count_query = db.query(func.count(Plan.id))

    if search:
        search_filter = Plan.name.ilike(f"%{search}%") | Plan.display_name.ilike(f"%{search}%")
        query = query.filter(search_filter)
        count_query = count_query.filter(search_filter)

    if is_active is not None:
        query = query.filter(Plan.is_active == is_active)
        count_query = count_query.filter(Plan.is_active == is_active)

    if is_public is not None:
        query = query.filter(Plan.is_public == is_public)
        count_query = count_query.filter(Plan.is_public == is_public)

    total = count_query.scalar() or 0
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    plans = query.order_by(Plan.sort_order.asc(), Plan.created_at.desc()).offset(offset).limit(page_size).all()

    return PlanListResponse(
        items=[PlanResponse.model_validate(plan) for plan in plans],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan_admin(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    existing = db.query(Plan).filter(Plan.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan name already exists")

    plan = Plan(**payload.model_dump())
    db.add(plan)
    log_admin_action(
        db,
        admin,
        "admin.plan.create",
        "plan",
        None,
        payload.model_dump(),
        request=request
    )
    db.commit()
    db.refresh(plan)
    return PlanResponse.model_validate(plan)


@router.put("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan_admin(
    plan_id: UUID,
    payload: PlanUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    if payload.name and payload.name != plan.name:
        existing = db.query(Plan).filter(Plan.name == payload.name).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan name already exists")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)

    log_admin_action(
        db,
        admin,
        "admin.plan.update",
        "plan",
        str(plan.id),
        update_data,
        request=request
    )
    db.commit()
    db.refresh(plan)
    return PlanResponse.model_validate(plan)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan_admin(
    plan_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    log_admin_action(
        db,
        admin,
        "admin.plan.delete",
        "plan",
        str(plan.id),
        {"name": plan.name},
        request=request
    )
    db.delete(plan)
    db.commit()


@router.get("/tools", response_model=ToolListResponse)
async def list_tools_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    coming_soon: Optional[bool] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = db.query(Tool)
    count_query = db.query(func.count(Tool.id))

    if search:
        search_filter = Tool.name.ilike(f"%{search}%") | Tool.key.ilike(f"%{search}%")
        query = query.filter(search_filter)
        count_query = count_query.filter(search_filter)

    if category:
        query = query.filter(Tool.category == category)
        count_query = count_query.filter(Tool.category == category)

    if status_filter:
        query = query.filter(Tool.status == status_filter)
        count_query = count_query.filter(Tool.status == status_filter)

    if coming_soon is not None:
        query = query.filter(Tool.coming_soon == coming_soon)
        count_query = count_query.filter(Tool.coming_soon == coming_soon)

    total = count_query.scalar() or 0
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    tools = query.order_by(Tool.created_at.desc()).offset(offset).limit(page_size).all()

    return ToolListResponse(
        items=[ToolResponse.model_validate(tool) for tool in tools],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.post("/tools", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool_admin(
    payload: ToolCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    try:
        # First-run fallback: if tool catalog is empty, seed safe defaults.
        if db.query(Tool.id).first() is None:
            try:
                seeded = seed_initial_tools(db)
                logger.info("Admin tool create fallback seed executed: %s", seeded)
            except Exception as seed_exc:
                db.rollback()
                logger.exception("Admin tool create fallback seed failed: %s", seed_exc)

        existing = db.query(Tool).filter(Tool.key == payload.key).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool key already exists")

        create_data = payload.model_dump(exclude_unset=False)
        create_data["key"] = (create_data.get("key") or "").strip()
        create_data["slug"] = (create_data.get("slug") or create_data["key"]).strip()

        if not create_data["key"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tool key is required"
            )
        if not create_data["slug"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tool slug is required"
            )

        # Required model field defaults for resilient production creates.
        create_data["tags"] = create_data.get("tags") or []
        create_data["required_integrations_json"] = create_data.get("required_integrations_json") or []
        create_data["input_schema_json"] = create_data.get("input_schema_json") or {}
        create_data["output_schema_json"] = create_data.get("output_schema_json") or {}
        create_data["n8n_workflow_id"] = (create_data.get("n8n_workflow_id") or "svontai-tool-runner").strip()

        existing_slug = db.query(Tool).filter(Tool.slug == create_data["slug"]).first()
        if existing_slug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool slug already exists")

        tool = Tool(**create_data)
        db.add(tool)
        log_admin_action(
            db,
            admin,
            "admin.tool.create",
            "tool",
            None,
            create_data,
            request=request
        )
        db.commit()
        db.refresh(tool)
        return ToolResponse.model_validate(tool)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        error_detail = str(getattr(exc, "orig", exc))
        logger.exception("Admin tool create integrity error: %s", error_detail)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tool validation failed: {error_detail}"
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Admin tool create database error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while creating tool: {exc}"
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Admin tool create unexpected error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tool: {exc}"
        )


@router.put("/tools/{tool_id}", response_model=ToolResponse)
async def update_tool_admin(
    tool_id: UUID,
    payload: ToolUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    tool = db.get(Tool, tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    if payload.key and payload.key != tool.key:
        existing = db.query(Tool).filter(Tool.key == payload.key).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool key already exists")

    update_data = payload.model_dump(exclude_unset=True)
    if "slug" in update_data and update_data["slug"]:
        existing_slug = db.query(Tool).filter(Tool.slug == update_data["slug"], Tool.id != tool.id).first()
        if existing_slug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool slug already exists")
    if "slug" in update_data and isinstance(update_data["slug"], str):
        update_data["slug"] = update_data["slug"].strip() or None

    for key, value in update_data.items():
        setattr(tool, key, value)

    log_admin_action(
        db,
        admin,
        "admin.tool.update",
        "tool",
        str(tool.id),
        update_data,
        request=request
    )
    db.commit()
    db.refresh(tool)
    return ToolResponse.model_validate(tool)


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool_admin(
    tool_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    tool = db.get(Tool, tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    log_admin_action(
        db,
        admin,
        "admin.tool.delete",
        "tool",
        str(tool.id),
        {"key": tool.key},
        request=request
    )
    db.delete(tool)
    db.commit()


@router.post("/tools/seed-initial", response_model=ToolSeedResponse)
async def seed_initial_tools_admin(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None,
):
    result = seed_initial_tools(db)
    log_admin_action(
        db,
        admin,
        "admin.tool.seed_initial",
        "tool",
        None,
        result,
        request=request,
    )
    return ToolSeedResponse(**result)


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    """Delete tenant (admin only)."""
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    log_admin_action(
        db,
        admin,
        "admin.tenant.delete",
        "tenant",
        str(tenant.id),
        {"name": tenant.name},
        request=request
    )

    db.delete(tenant)
    db.commit()


@router.get("/health", response_model=SystemHealth)
async def get_system_health(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get system health status."""
    # Check database
    try:
        db.execute(select(1))
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
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    """Make a user admin."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_admin = True
    log_admin_action(
        db,
        admin,
        "admin.user.make_admin",
        "user",
        str(user.id),
        {"email": user.email},
        request=request
    )
    db.commit()
    db.refresh(user)
    
    return UserResponse.model_validate(user)
