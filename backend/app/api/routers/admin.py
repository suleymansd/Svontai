"""
Admin API routes for system administration.
"""

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from app.core.time import utc_now_naive
from uuid import UUID
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_access_token_payload
from app.models.user import User
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.knowledge import BotKnowledgeItem
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.lead import Lead
from app.models.automation import AutomationRun
from app.models.subscription import TenantSubscription
from app.models.feature_flag import FeatureFlag
from app.models.incident import Incident
from app.models.autopilot import IntegrationHealthCheck, SetupRun
from app.models.plan import Plan
from app.models.tool import Tool
from app.models.ticket import Ticket, TicketMessage
from app.models.whatsapp_account import WhatsAppAccount
from app.models.onboarding import AuditLog
from app.models.real_estate import RealEstatePackSettings
from app.models.sales_inquiry import SalesInquiry
from app.models.invoice import Invoice
from app.schemas.user import UserResponse, UserAdminUpdate
from app.schemas.tenant import TenantResponse
from app.schemas.plan import PlanCreate, PlanUpdate, PlanResponse
from app.schemas.tool import ToolCreate, ToolResponse
from app.core.config import settings
from app.core.plans import normalize_plan_code
from app.core.security import get_password_hash
from app.services.real_estate_service import RealEstateService
from app.services.subscription_service import SubscriptionService
from app.services.tool_seed_service import seed_initial_tools
from app.services.audit_log_service import AuditLogService
from app.services.autopilot_service import AutopilotService, DEFAULT_PROFILE_TITLE
from app.services.system_event_service import SystemEventService
from app.services.system_verification_service import SystemVerificationService

from pydantic import BaseModel, EmailStr, Field


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


class SalesInquiryAdminItem(BaseModel):
    id: str
    name: str
    email: str
    company: str | None
    phone: str | None
    plan: str | None
    interval: str | None
    message: str
    status: str
    email_delivered: bool
    created_at: datetime
    updated_at: datetime


class SalesInquiryListResponse(BaseModel):
    items: list[SalesInquiryAdminItem]
    total: int


class SalesInquiryStatusUpdate(BaseModel):
    status: Literal["new", "contacted", "qualified", "closed", "spam"]


class InvoiceLineInput(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: Decimal = Field(gt=0, le=1000000)
    unit: str = Field(default="adet", min_length=1, max_length=30)
    unit_price: Decimal = Field(ge=0, le=999999999)
    tax_rate: Decimal = Field(default=Decimal("20"), ge=0, le=100)


class InvoiceCreate(BaseModel):
    tenant_id: UUID | None = None
    issue_date: date
    due_date: date
    currency: str = Field(default="TRY", min_length=3, max_length=3)
    seller_name: str = Field(min_length=1, max_length=180)
    seller_email: EmailStr | None = None
    seller_phone: str | None = Field(default=None, max_length=40)
    seller_address: str | None = Field(default=None, max_length=1500)
    seller_tax_office: str | None = Field(default=None, max_length=120)
    seller_tax_number: str | None = Field(default=None, max_length=40)
    customer_name: str = Field(min_length=1, max_length=180)
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, max_length=40)
    customer_address: str | None = Field(default=None, max_length=1500)
    customer_tax_office: str | None = Field(default=None, max_length=120)
    customer_tax_number: str | None = Field(default=None, max_length=40)
    items: list[InvoiceLineInput] = Field(min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=3000)


class InvoiceStatusUpdate(BaseModel):
    status: Literal["draft", "sent", "paid", "cancelled"]


class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str
    tenant_id: UUID | None
    document_type: str
    status: str
    issue_date: date
    due_date: date
    currency: str
    seller_name: str
    seller_email: str | None
    seller_phone: str | None
    seller_address: str | None
    seller_tax_office: str | None
    seller_tax_number: str | None
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    customer_address: str | None
    customer_tax_office: str | None
    customer_tax_number: str | None
    items: list[dict]
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    notes: str | None
    legal_notice: str
    created_at: datetime
    updated_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int


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


class ToolAdminOut(BaseModel):
    id: str
    key: str
    slug: str
    name: str
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    tags: list[str] = Field(default_factory=list)
    required_plan: str | None = None
    status: str
    is_public: bool
    coming_soon: bool
    is_premium: bool
    required_integrations_json: list[str] = Field(default_factory=list)
    n8n_workflow_id: str | None = None
    input_schema_json: dict = Field(default_factory=dict)
    output_schema_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ToolListResponse(BaseModel):
    items: list[ToolAdminOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class ToolSeedResponse(BaseModel):
    created: int
    updated: int
    total: int


class LaunchBoardItem(BaseModel):
    tenant_id: str
    tenant_name: str
    owner_name: str
    owner_email: str
    plan_name: str | None = None
    setup_mode: str
    launch_stage: str
    health_score: int
    concierge_status: str
    concierge_ticket_id: str | None = None
    business_profile_status: str
    whatsapp_status: str
    required_user_actions: list[str] = Field(default_factory=list)
    bot_count: int
    open_tickets: int
    open_incidents: int
    latest_setup_run_status: str | None = None
    created_at: datetime


class LaunchBoardResponse(BaseModel):
    items: list[LaunchBoardItem]
    total: int
    pending_concierge: int
    ready_to_launch: int
    blocked_by_user: int


class ConciergeUpdateRequest(BaseModel):
    status: Literal["pending", "in_progress", "ready_for_review", "launched", "blocked"]
    note: str | None = None
    create_ticket: bool = False


class ConciergeActionResponse(BaseModel):
    tenant_id: str
    concierge_status: str
    concierge_ticket_id: str | None = None
    business_profile_status: str
    launch_stage: str


class BusinessProfileAdminUpdate(BaseModel):
    industry: str = "unknown"
    tone: str = "professional"
    summary: str = ""
    services: list[str] = Field(default_factory=list)
    faq: list[dict] = Field(default_factory=list)
    status: Literal["customer_collected", "admin_enriched", "ready"] = "admin_enriched"


class AdminAutopilotRunResponse(BaseModel):
    tenant_id: str
    status: str
    health_score: int
    required_user_actions: list[dict] = Field(default_factory=list)


class AdminVerificationResponse(BaseModel):
    tenant_id: str
    status: str
    ready_for_launch: bool
    score: int
    summary: str
    failed_critical: list[str] = Field(default_factory=list)
    warning_count: int
    checks: list[dict] = Field(default_factory=list)
    run_id: str


def _launch_stage(profile_status: str, concierge_status: str, required_actions: list[str], health_score: int) -> str:
    if required_actions:
        return "blocked_by_user"
    if profile_status != "ready" or concierge_status in {"pending", "in_progress"}:
        return "concierge"
    if health_score >= 80:
        return "ready_to_launch"
    return "needs_attention"


def _required_user_actions_from_health(rows: list[IntegrationHealthCheck]) -> list[str]:
    return [
        row.provider
        for row in rows
        if row.requires_user_action or row.status in {"missing", "expired"}
    ]


def _tenant_settings(tenant: Tenant) -> dict:
    return dict(tenant.settings or {})


def _ensure_concierge_ticket(db: Session, tenant: Tenant, admin: User, note: str | None = None) -> str:
    settings_json = _tenant_settings(tenant)
    concierge = dict(settings_json.get("concierge_enrichment") or {})
    ticket_id = concierge.get("ticket_id")
    if ticket_id and db.get(Ticket, str(ticket_id)):
        return str(ticket_id)

    ticket = Ticket(
        tenant_id=str(tenant.id),
        requester_id=str(tenant.owner_id) if tenant.owner_id else None,
        assigned_to=str(admin.id),
        subject=f"Concierge bilgi formasyonu: {tenant.name}",
        priority="high",
        status="open",
        last_activity_at=utc_now_naive(),
    )
    db.add(ticket)
    db.flush()
    db.add(
        TicketMessage(
            ticket_id=ticket.id,
            sender_id=str(admin.id),
            sender_type="system",
            body=note or "Concierge kurulum ve bilgi formasyonu için operasyon kaydı açıldı.",
        )
    )
    return ticket.id


def _sync_profile_to_bot(db: Session, tenant: Tenant, profile: dict) -> None:
    bot = db.query(Bot).filter(Bot.tenant_id == tenant.id).order_by(Bot.created_at.asc()).first()
    if not bot:
        return

    industry = (profile.get("industry") or "unknown").strip()
    summary = (profile.get("summary") or "").strip()
    tone = (profile.get("tone") or "professional").strip()
    if industry and industry != "unknown":
        bot.description = f"{tenant.name} için {industry} odağında müşteri iletişimini yöneten SmartWA asistanı."
    if summary:
        bot.welcome_message = "Nasıl yardımcı olabilirim?"

    answer = (
        f"İşletme: {tenant.name}\n"
        f"Sektör: {industry or 'Belirtilmedi'}\n"
        f"Ton: {tone}\n"
        f"Özet: {summary or 'Belirtilmedi'}\n"
        f"Hizmetler: {', '.join(map(str, profile.get('services') or [])) or 'Belirtilmedi'}\n"
        "Müşteri sorularında bu işletme profilini esas al; net olmayan konularda insan desteğine yönlendir."
    )
    knowledge = db.query(BotKnowledgeItem).filter(
        BotKnowledgeItem.bot_id == bot.id,
        BotKnowledgeItem.title == DEFAULT_PROFILE_TITLE,
    ).first()
    if knowledge:
        knowledge.answer = answer
    else:
        db.add(
            BotKnowledgeItem(
                bot_id=bot.id,
                title=DEFAULT_PROFILE_TITLE,
                question="Bu işletme hakkında nasıl davranmalısın?",
                answer=answer,
            )
        )


def _admin_operation_result(tenant: Tenant, health_rows: list[IntegrationHealthCheck] | None = None) -> ConciergeActionResponse:
    settings_json = _tenant_settings(tenant)
    profile = dict(settings_json.get("business_profile") or {})
    concierge = dict(settings_json.get("concierge_enrichment") or {})
    rows = health_rows or []
    health_score = int(round(sum(row.health_score for row in rows) / max(1, len(rows)))) if rows else 0
    required_actions = _required_user_actions_from_health(rows)
    profile_status = str(profile.get("status") or "unknown")
    concierge_status = str(concierge.get("status") or "not_started")
    return ConciergeActionResponse(
        tenant_id=str(tenant.id),
        concierge_status=concierge_status,
        concierge_ticket_id=concierge.get("ticket_id"),
        business_profile_status=profile_status,
        launch_stage=_launch_stage(profile_status, concierge_status, required_actions, health_score),
    )


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


class TenantPlanOverrideRequest(BaseModel):
    plan_type: Literal["free", "pro", "premium", "enterprise"]
    note: str
    expires_at: datetime | None = None


class TenantPlanOverrideResponse(BaseModel):
    tenant_id: str
    old_plan: str
    new_plan: str
    expires_at: str | None
    status: str


class TenantForcePlanRequest(BaseModel):
    plan_type: Literal["free", "pro", "premium", "enterprise"]


class TenantForcePlanResponse(BaseModel):
    tenant_id: str
    new_plan: str
    status: str


class ToolAdminPatch(BaseModel):
    key: str | None = None
    slug: str | None = None
    name: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    tags: list[str] | None = None
    required_plan: str | None = None
    status: str | None = None
    is_public: bool | None = None
    coming_soon: bool | None = None
    is_premium: bool | None = None
    input_schema_json: dict | None = None
    output_schema_json: dict | None = None
    required_integrations_json: list[str] | None = None
    n8n_workflow_id: str | None = None


class ToolAdminUpdate(BaseModel):
    key: str
    slug: str
    name: str
    status: str
    coming_soon: bool
    is_public: bool
    required_plan: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_premium: bool = False
    input_schema_json: dict = Field(default_factory=dict)
    output_schema_json: dict = Field(default_factory=dict)
    required_integrations_json: list[str] = Field(default_factory=list)
    n8n_workflow_id: str | None = None


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
            detail="Admin privileges required"
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


def _serialize_tool(tool: Tool) -> ToolAdminOut:
    return ToolAdminOut(
        id=str(tool.id),
        key=tool.key,
        slug=tool.slug,
        name=tool.name,
        description=tool.description,
        category=tool.category,
        icon=tool.icon,
        tags=list(tool.tags or []),
        required_plan=tool.required_plan,
        status=tool.status,
        is_public=bool(tool.is_public),
        coming_soon=bool(tool.coming_soon),
        is_premium=bool(tool.is_premium),
        required_integrations_json=list(tool.required_integrations_json or []),
        n8n_workflow_id=tool.n8n_workflow_id,
        input_schema_json=dict(tool.input_schema_json or {}),
        output_schema_json=dict(tool.output_schema_json or {}),
        created_at=tool.created_at,
        updated_at=tool.updated_at,
    )


def _get_tool_by_id(db: Session, tool_id: UUID) -> Tool | None:
    try:
        tool = db.get(Tool, tool_id)
        if tool:
            return tool
    except SQLAlchemyError:
        db.rollback()

    tool_id_str = str(tool_id)
    tool = db.query(Tool).filter(cast(Tool.id, String) == tool_id_str).first()
    if tool:
        return tool
    return db.query(Tool).filter(Tool.id == tool_id_str).first()


# Routes
@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get admin dashboard statistics."""
    now = utc_now_naive()
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


@router.get("/launch-board", response_model=LaunchBoardResponse)
async def get_launch_board(
    search: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Customer launch board for concierge onboarding operations."""
    _ = admin
    query = db.query(Tenant, User).join(User, Tenant.owner_id == User.id)
    if search:
        query = query.filter(Tenant.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))

    rows = query.order_by(Tenant.created_at.desc()).limit(limit).all()
    items: list[LaunchBoardItem] = []
    counters = {"pending_concierge": 0, "ready_to_launch": 0, "blocked_by_user": 0}

    for tenant, owner in rows:
        settings = dict(tenant.settings or {})
        setup_mode = str(settings.get("setup_mode") or "concierge")
        profile = dict(settings.get("business_profile") or {})
        concierge = dict(settings.get("concierge_enrichment") or {})
        health_rows = db.query(IntegrationHealthCheck).filter(IntegrationHealthCheck.tenant_id == tenant.id).all()
        health_score = int(round(sum(row.health_score for row in health_rows) / max(1, len(health_rows)))) if health_rows else 0
        required_actions = _required_user_actions_from_health(health_rows)
        profile_status = str(profile.get("status") or "unknown")
        concierge_status = str(concierge.get("status") or "not_started")
        launch_stage = _launch_stage(profile_status, concierge_status, required_actions, health_score)
        if stage and launch_stage != stage:
            continue

        if launch_stage == "ready_to_launch":
            counters["ready_to_launch"] += 1
        if launch_stage == "blocked_by_user":
            counters["blocked_by_user"] += 1
        if concierge_status in {"pending", "in_progress"}:
            counters["pending_concierge"] += 1

        subscription = db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant.id).first()
        plan_name = None
        if subscription:
            plan = db.get(Plan, subscription.plan_id)
            plan_name = plan.display_name if plan else None
        whatsapp_connected = db.query(WhatsAppAccount.id).filter(
            WhatsAppAccount.tenant_id == tenant.id,
            WhatsAppAccount.is_active == True,
        ).first()
        latest_run = db.query(SetupRun).filter(SetupRun.tenant_id == tenant.id).order_by(SetupRun.created_at.desc()).first()
        bot_count = int(db.query(func.count(Bot.id)).filter(Bot.tenant_id == tenant.id).scalar() or 0)
        open_tickets = int(db.query(func.count(Ticket.id)).filter(Ticket.tenant_id == str(tenant.id), Ticket.status.in_(["open", "pending"])).scalar() or 0)
        open_incidents = int(db.query(func.count(Incident.id)).filter(Incident.tenant_id == str(tenant.id), Incident.status != "resolved").scalar() or 0)

        items.append(LaunchBoardItem(
            tenant_id=str(tenant.id),
            tenant_name=tenant.name,
            owner_name=owner.full_name,
            owner_email=owner.email,
            plan_name=plan_name,
            setup_mode=setup_mode,
            launch_stage=launch_stage,
            health_score=health_score,
            concierge_status=concierge_status,
            concierge_ticket_id=concierge.get("ticket_id"),
            business_profile_status=profile_status,
            whatsapp_status="connected" if whatsapp_connected else "missing",
            required_user_actions=required_actions,
            bot_count=bot_count,
            open_tickets=open_tickets,
            open_incidents=open_incidents,
            latest_setup_run_status=latest_run.status if latest_run else None,
            created_at=tenant.created_at,
        ))

    return LaunchBoardResponse(
        items=items,
        total=len(items),
        pending_concierge=counters["pending_concierge"],
        ready_to_launch=counters["ready_to_launch"],
        blocked_by_user=counters["blocked_by_user"],
    )


@router.patch("/launch-board/{tenant_id}/concierge", response_model=ConciergeActionResponse)
async def update_launch_board_concierge(
    tenant_id: UUID,
    request_body: ConciergeUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    settings_json = _tenant_settings(tenant)
    profile = dict(settings_json.get("business_profile") or {})
    concierge = dict(settings_json.get("concierge_enrichment") or {})
    if request_body.create_ticket or not concierge.get("ticket_id"):
        concierge["ticket_id"] = _ensure_concierge_ticket(db, tenant, admin, request_body.note)
    concierge.update({
        "status": request_body.status,
        "updated_by": str(admin.id),
        "updated_at": utc_now_naive().isoformat(),
    })
    if request_body.note:
        concierge["last_note"] = request_body.note
        if concierge.get("ticket_id"):
            db.add(
                TicketMessage(
                    ticket_id=str(concierge["ticket_id"]),
                    sender_id=str(admin.id),
                    sender_type="admin",
                    body=request_body.note,
                )
            )
    if request_body.status == "ready_for_review" and profile.get("status") == "admin_enriched":
        profile["status"] = "ready"
        profile["updated_at"] = utc_now_naive().isoformat()

    settings_json["concierge_enrichment"] = concierge
    settings_json["business_profile"] = profile
    tenant.settings = settings_json
    db.commit()
    db.refresh(tenant)

    AuditLogService(db).log(
        action="admin.concierge.update",
        tenant_id=str(tenant.id),
        user_id=str(admin.id),
        resource_type="tenant",
        resource_id=str(tenant.id),
        payload={"status": request_body.status, "note": request_body.note},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
    )
    SystemEventService(db).log(
        tenant_id=str(tenant.id),
        source="admin",
        level="info",
        code="CONCIERGE_STATUS_UPDATED",
        message="Concierge status updated",
        meta_json={"status": request_body.status, "ticket_id": concierge.get("ticket_id")},
    )

    health_rows = db.query(IntegrationHealthCheck).filter(IntegrationHealthCheck.tenant_id == tenant.id).all()
    return _admin_operation_result(tenant, health_rows)


@router.patch("/tenants/{tenant_id}/business-profile", response_model=ConciergeActionResponse)
async def update_tenant_business_profile(
    tenant_id: UUID,
    request_body: BusinessProfileAdminUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    settings_json = _tenant_settings(tenant)
    existing_profile = dict(settings_json.get("business_profile") or {})
    profile = {
        **existing_profile,
        "status": request_body.status,
        "source": "admin_concierge",
        "business_name": tenant.name,
        "industry": request_body.industry,
        "tone": request_body.tone,
        "summary": request_body.summary,
        "services": request_body.services,
        "faq": request_body.faq,
        "updated_by": str(admin.id),
        "updated_at": utc_now_naive().isoformat(),
    }
    concierge = dict(settings_json.get("concierge_enrichment") or {})
    concierge.update({
        "status": "ready_for_review" if request_body.status == "ready" else concierge.get("status") or "in_progress",
        "updated_by": str(admin.id),
        "updated_at": profile["updated_at"],
    })
    if not concierge.get("ticket_id"):
        concierge["ticket_id"] = _ensure_concierge_ticket(db, tenant, admin, "Admin bilgi formasyonu düzenlendi.")

    settings_json["setup_mode"] = settings_json.get("setup_mode") or "concierge"
    settings_json["business_profile"] = profile
    settings_json["concierge_enrichment"] = concierge
    tenant.settings = settings_json
    _sync_profile_to_bot(db, tenant, profile)
    db.commit()
    db.refresh(tenant)

    AuditLogService(db).log(
        action="admin.business_profile.update",
        tenant_id=str(tenant.id),
        user_id=str(admin.id),
        resource_type="tenant",
        resource_id=str(tenant.id),
        payload={"status": request_body.status, "industry": request_body.industry},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
    )
    SystemEventService(db).log(
        tenant_id=str(tenant.id),
        source="admin",
        level="info",
        code="BUSINESS_PROFILE_UPDATED",
        message="Business profile updated by admin",
        meta_json={"status": request_body.status, "industry": request_body.industry},
    )

    health_rows = db.query(IntegrationHealthCheck).filter(IntegrationHealthCheck.tenant_id == tenant.id).all()
    return _admin_operation_result(tenant, health_rows)


@router.post("/tenants/{tenant_id}/autopilot/run", response_model=AdminAutopilotRunResponse)
async def run_admin_tenant_autopilot(
    tenant_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    status_payload = AutopilotService(db).run(tenant, admin)
    AuditLogService(db).log(
        action="admin.autopilot.run",
        tenant_id=str(tenant.id),
        user_id=str(admin.id),
        resource_type="tenant",
        resource_id=str(tenant.id),
        payload={"health_score": status_payload.get("health_score")},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
    )
    return AdminAutopilotRunResponse(
        tenant_id=str(tenant.id),
        status=str(status_payload.get("status")),
        health_score=int(status_payload.get("health_score") or 0),
        required_user_actions=status_payload.get("required_user_actions") or [],
    )


@router.post("/tenants/{tenant_id}/verification/run", response_model=AdminVerificationResponse)
async def run_admin_tenant_verification(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    payload = SystemVerificationService(db).run(tenant, admin)
    return AdminVerificationResponse(tenant_id=str(tenant.id), **payload)


@router.post("/tenants/{tenant_id}/launch", response_model=ConciergeActionResponse)
async def launch_tenant_from_admin(
    tenant_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    verification = SystemVerificationService(db).run(tenant, admin)
    if not verification["ready_for_launch"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Kritik sistem kontrolleri tamamlanmadan müşteri yayına alınamaz.",
                "failed_critical": verification["failed_critical"],
                "score": verification["score"],
            },
        )

    settings_json = _tenant_settings(tenant)
    profile = dict(settings_json.get("business_profile") or {})
    concierge = dict(settings_json.get("concierge_enrichment") or {})
    profile["status"] = "ready"
    profile["updated_at"] = utc_now_naive().isoformat()
    concierge.update({
        "status": "launched",
        "launched_by": str(admin.id),
        "launched_at": utc_now_naive().isoformat(),
        "updated_by": str(admin.id),
        "updated_at": utc_now_naive().isoformat(),
    })
    if not concierge.get("ticket_id"):
        concierge["ticket_id"] = _ensure_concierge_ticket(db, tenant, admin, "Müşteri yayına alındı.")
    settings_json["business_profile"] = profile
    settings_json["concierge_enrichment"] = concierge
    settings_json["production_verification"] = {
        "status": "ready",
        "score": verification["score"],
        "run_id": verification["run_id"],
        "verified_by": str(admin.id),
        "verified_at": utc_now_naive().isoformat(),
    }
    tenant.settings = settings_json
    _sync_profile_to_bot(db, tenant, profile)
    db.commit()
    db.refresh(tenant)

    AuditLogService(db).log(
        action="admin.tenant.launch",
        tenant_id=str(tenant.id),
        user_id=str(admin.id),
        resource_type="tenant",
        resource_id=str(tenant.id),
        payload={"concierge_status": "launched"},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
    )
    SystemEventService(db).log(
        tenant_id=str(tenant.id),
        source="admin",
        level="info",
        code="TENANT_LAUNCHED",
        message="Tenant launched by admin",
        meta_json={"ticket_id": concierge.get("ticket_id")},
    )

    health_rows = db.query(IntegrationHealthCheck).filter(IntegrationHealthCheck.tenant_id == tenant.id).all()
    return _admin_operation_result(tenant, health_rows)


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


@router.post("/tenants/{tenant_id}/preview", response_model=TenantResponse)
async def start_tenant_preview(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None,
):
    """Validate and audit a super-admin customer-panel preview session."""
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    log_admin_action(
        db,
        admin,
        "admin.tenant.preview.start",
        "tenant",
        str(tenant.id),
        {"tenant_name": tenant.name},
        request=request,
    )
    db.commit()
    return TenantResponse.model_validate(tenant)


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


@router.put("/tenants/{tenant_id}/plan", response_model=TenantPlanOverrideResponse)
async def override_tenant_plan(
    tenant_id: UUID,
    payload: TenantPlanOverrideRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None,
):
    if (
        settings.ENVIRONMENT == "prod"
        and settings.BILLING_MODE != "manual"
        and not settings.ALLOW_ADMIN_PLAN_OVERRIDE
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLAN_OVERRIDE_DISABLED",
                "message": "Admin plan override production ortamında devre dışı."
            },
        )

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    normalized_plan = normalize_plan_code(payload.plan_type)
    plan = db.query(Plan).filter(
        func.lower(Plan.name) == normalized_plan,
        Plan.is_active.is_(True)
    ).first()

    if not plan:
        SubscriptionService(db).get_or_create_free_plan()
        plan = db.query(Plan).filter(
            func.lower(Plan.name) == normalized_plan,
            Plan.is_active.is_(True)
        ).first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {normalized_plan}"
        )

    subscription_service = SubscriptionService(db)
    subscription = subscription_service.get_subscription(tenant.id)
    if subscription is None:
        subscription = subscription_service.create_subscription(tenant.id, "free")

    old_plan = normalize_plan_code(subscription.plan.plan_type or subscription.plan.name)
    subscription.plan_id = plan.id

    extra_data = dict(subscription.extra_data or {})
    extra_data["admin_plan_override"] = {
        "old_plan": old_plan,
        "new_plan": normalized_plan,
        "note": payload.note,
        "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
        "updated_by": str(admin.id),
        "updated_at": utc_now_naive().isoformat(),
    }
    subscription.extra_data = extra_data

    log_admin_action(
        db,
        admin,
        "admin.tenant.plan_override",
        "tenant",
        str(tenant.id),
        {
            "old_plan": old_plan,
            "new_plan": normalized_plan,
            "note": payload.note,
            "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
        },
        request=request,
    )

    db.commit()

    return TenantPlanOverrideResponse(
        tenant_id=str(tenant.id),
        old_plan=old_plan,
        new_plan=normalized_plan,
        expires_at=payload.expires_at.isoformat() if payload.expires_at else None,
        status="ok",
    )


@router.put("/tenants/{tenant_id}/force-plan", response_model=TenantForcePlanResponse)
async def force_tenant_plan(
    tenant_id: UUID,
    payload: TenantForcePlanRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None,
):
    if (
        settings.ENVIRONMENT == "prod"
        and settings.BILLING_MODE != "manual"
        and not settings.ALLOW_ADMIN_PLAN_OVERRIDE
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLAN_OVERRIDE_DISABLED",
                "message": "Admin force-plan production ortamında devre dışı."
            },
        )

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    normalized_plan = normalize_plan_code(payload.plan_type)
    subscription_service = SubscriptionService(db)
    try:
        subscription = subscription_service.upgrade_plan(
            tenant_id=tenant.id,
            new_plan_name=normalized_plan,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_admin_action(
        db,
        admin,
        "admin.tenant.force_plan",
        "tenant",
        str(tenant.id),
        {"new_plan": normalized_plan},
        request=request,
    )
    db.commit()

    return TenantForcePlanResponse(
        tenant_id=str(tenant.id),
        new_plan=normalize_plan_code(subscription.plan.plan_type or subscription.plan.name),
        status="ok",
    )


@router.get("/sales-inquiries", response_model=SalesInquiryListResponse)
async def list_sales_inquiries(
    inquiry_status: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SalesInquiryListResponse:
    query = db.query(SalesInquiry)
    if inquiry_status:
        query = query.filter(SalesInquiry.status == inquiry_status)
    if search and search.strip():
        pattern = f"%{search.strip().lower()}%"
        query = query.filter(
            func.lower(SalesInquiry.name).like(pattern)
            | func.lower(SalesInquiry.email).like(pattern)
            | func.lower(func.coalesce(SalesInquiry.company, "")).like(pattern)
        )
    total = query.count()
    rows = query.order_by(SalesInquiry.created_at.desc()).limit(limit).all()
    return SalesInquiryListResponse(
        items=[
            SalesInquiryAdminItem(
                id=str(row.id),
                name=row.name,
                email=row.email,
                company=row.company,
                phone=row.phone,
                plan=row.plan,
                interval=row.interval,
                message=row.message,
                status=row.status,
                email_delivered=row.email_delivered,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ],
        total=total,
    )


@router.patch("/sales-inquiries/{inquiry_id}", response_model=SalesInquiryAdminItem)
async def update_sales_inquiry(
    inquiry_id: str,
    payload: SalesInquiryStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SalesInquiryAdminItem:
    inquiry = db.get(SalesInquiry, inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Satış talebi bulunamadı")
    old_status = inquiry.status
    inquiry.status = payload.status
    db.commit()
    db.refresh(inquiry)
    log_admin_action(
        db,
        admin,
        "admin.sales_inquiry.update",
        "sales_inquiry",
        str(inquiry.id),
        {"old_status": old_status, "new_status": payload.status},
        request=request,
    )
    return SalesInquiryAdminItem(
        id=str(inquiry.id),
        name=inquiry.name,
        email=inquiry.email,
        company=inquiry.company,
        phone=inquiry.phone,
        plan=inquiry.plan,
        interval=inquiry.interval,
        message=inquiry.message,
        status=inquiry.status,
        email_delivered=inquiry.email_delivered,
        created_at=inquiry.created_at,
        updated_at=inquiry.updated_at,
    )


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
        items=[_serialize_tool(tool) for tool in tools],
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


@router.get("/tools/{tool_id}", response_model=ToolAdminOut)
async def get_tool_admin(
    tool_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    tool = _get_tool_by_id(db, tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    return _serialize_tool(tool)


@router.patch("/tools/{tool_id}", response_model=ToolAdminOut)
async def update_tool_admin(
    tool_id: UUID,
    payload: ToolAdminPatch,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    tool = _get_tool_by_id(db, tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    if payload.key and payload.key != tool.key:
        existing = db.query(Tool).filter(Tool.key == payload.key).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool key already exists")

    update_data = payload.model_dump(exclude_unset=True)
    if "key" in update_data and isinstance(update_data["key"], str):
        update_data["key"] = update_data["key"].strip()
        if not update_data["key"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tool key is required")

    if "slug" in update_data and update_data["slug"]:
        normalized_slug = update_data["slug"].strip()
        if not normalized_slug:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tool slug is required")
        update_data["slug"] = normalized_slug
        existing_slug = db.query(Tool).filter(
            Tool.slug == normalized_slug,
            cast(Tool.id, String) != str(tool.id)
        ).first()
        if existing_slug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool slug already exists")

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
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tool validation failed: {getattr(exc, 'orig', exc)}"
        ) from exc
    db.refresh(tool)
    return _serialize_tool(tool)


@router.put("/tools/{tool_id}", response_model=ToolAdminOut)
async def replace_tool_admin(
    tool_id: UUID,
    payload: ToolAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    tool = _get_tool_by_id(db, tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    if payload.key != tool.key:
        existing = db.query(Tool).filter(Tool.key == payload.key).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool key already exists")

    if payload.slug != tool.slug:
        existing_slug = db.query(Tool).filter(
            Tool.slug == payload.slug,
            cast(Tool.id, String) != str(tool.id)
        ).first()
        if existing_slug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool slug already exists")

    update_data = payload.model_dump()
    update_data["key"] = update_data["key"].strip()
    update_data["slug"] = update_data["slug"].strip()
    update_data["name"] = update_data["name"].strip()
    if not update_data["key"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tool key is required")
    if not update_data["slug"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tool slug is required")
    if not update_data["name"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tool name is required")

    for key, value in update_data.items():
        setattr(tool, key, value)

    log_admin_action(
        db,
        admin,
        "admin.tool.replace",
        "tool",
        str(tool.id),
        update_data,
        request=request
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tool validation failed: {getattr(exc, 'orig', exc)}"
        ) from exc
    db.refresh(tool)
    return _serialize_tool(tool)


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool_admin(
    tool_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    tool = _get_tool_by_id(db, tool_id)
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


_MONEY_QUANT = Decimal("0.01")
_PROFORMA_NOTICE = "Bu belge bilgilendirme amaçlı proformadır; e-Fatura veya e-Arşiv fatura yerine geçmez."


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _invoice_response(row: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=row.id,
        invoice_number=row.invoice_number,
        tenant_id=row.tenant_id,
        document_type=row.document_type,
        status=row.status,
        issue_date=row.issue_date,
        due_date=row.due_date,
        currency=row.currency,
        seller_name=row.seller_name,
        seller_email=row.seller_email,
        seller_phone=row.seller_phone,
        seller_address=row.seller_address,
        seller_tax_office=row.seller_tax_office,
        seller_tax_number=row.seller_tax_number,
        customer_name=row.customer_name,
        customer_email=row.customer_email,
        customer_phone=row.customer_phone,
        customer_address=row.customer_address,
        customer_tax_office=row.customer_tax_office,
        customer_tax_number=row.customer_tax_number,
        items=list(row.items_json or []),
        subtotal=row.subtotal,
        tax_total=row.tax_total,
        total=row.total,
        notes=row.notes,
        legal_notice=_PROFORMA_NOTICE,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    search: str | None = Query(default=None, max_length=180),
    invoice_status: Literal["draft", "sent", "paid", "cancelled"] | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> InvoiceListResponse:
    _ = admin
    query = db.query(Invoice)
    if invoice_status:
        query = query.filter(Invoice.status == invoice_status)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(
            Invoice.invoice_number.ilike(pattern),
            Invoice.customer_name.ilike(pattern),
            Invoice.customer_email.ilike(pattern),
        ))
    total = query.count()
    rows = query.order_by(Invoice.created_at.desc()).limit(limit).all()
    return InvoiceListResponse(items=[_invoice_response(row) for row in rows], total=total)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> InvoiceResponse:
    _ = admin
    row = db.get(Invoice, invoice_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proforma bulunamadı")
    return _invoice_response(row)


@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> InvoiceResponse:
    if payload.due_date < payload.issue_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Son ödeme tarihi düzenleme tarihinden önce olamaz")

    if payload.tenant_id is not None and db.get(Tenant, payload.tenant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant bulunamadı")

    items: list[dict] = []
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for line in payload.items:
        line_subtotal = _money(line.quantity * line.unit_price)
        line_tax = _money(line_subtotal * line.tax_rate / Decimal("100"))
        line_total = _money(line_subtotal + line_tax)
        subtotal += line_subtotal
        tax_total += line_tax
        items.append({
            "description": line.description.strip(),
            "quantity": str(line.quantity.normalize()),
            "unit": line.unit.strip(),
            "unit_price": str(_money(line.unit_price)),
            "tax_rate": str(line.tax_rate.normalize()),
            "subtotal": str(line_subtotal),
            "tax": str(line_tax),
            "total": str(line_total),
        })

    subtotal = _money(subtotal)
    tax_total = _money(tax_total)
    total = _money(subtotal + tax_total)
    invoice_number = f"SV-{payload.issue_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
    row = Invoice(
        invoice_number=invoice_number,
        tenant_id=payload.tenant_id,
        created_by_user_id=admin.id,
        document_type="proforma",
        status="draft",
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        currency=payload.currency.upper(),
        seller_name=payload.seller_name.strip(),
        seller_email=str(payload.seller_email) if payload.seller_email else None,
        seller_phone=_optional_text(payload.seller_phone),
        seller_address=_optional_text(payload.seller_address),
        seller_tax_office=_optional_text(payload.seller_tax_office),
        seller_tax_number=_optional_text(payload.seller_tax_number),
        customer_name=payload.customer_name.strip(),
        customer_email=str(payload.customer_email) if payload.customer_email else None,
        customer_phone=_optional_text(payload.customer_phone),
        customer_address=_optional_text(payload.customer_address),
        customer_tax_office=_optional_text(payload.customer_tax_office),
        customer_tax_number=_optional_text(payload.customer_tax_number),
        items_json=items,
        subtotal=subtotal,
        tax_total=tax_total,
        total=total,
        notes=_optional_text(payload.notes),
    )
    db.add(row)
    db.flush()
    log_admin_action(
        db,
        admin,
        "admin.invoice.create",
        "invoice",
        str(row.id),
        {"invoice_number": row.invoice_number, "customer_name": row.customer_name, "total": str(row.total)},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _invoice_response(row)


@router.patch("/invoices/{invoice_id}/status", response_model=InvoiceResponse)
async def update_invoice_status(
    invoice_id: UUID,
    payload: InvoiceStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> InvoiceResponse:
    row = db.get(Invoice, invoice_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proforma bulunamadı")
    previous_status = row.status
    row.status = payload.status
    log_admin_action(
        db,
        admin,
        "admin.invoice.status_update",
        "invoice",
        str(row.id),
        {"previous_status": previous_status, "status": row.status},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _invoice_response(row)
