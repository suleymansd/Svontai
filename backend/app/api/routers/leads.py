"""
Lead management router.
"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.lead import Lead
from app.schemas.lead import LeadResponse, LeadWithBotName
from app.services.audit_log_service import AuditLogService
from app.services.subscription_service import SubscriptionService
from app.models.user import User

router = APIRouter(prefix="/leads", tags=["Leads"])


class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=5000)
    source: Optional[str] = Field(default="manual", max_length=50)

    @field_validator("email", "phone", "notes", "source", mode="before")
    @classmethod
    def _empty_string_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


@router.get("", response_model=list[LeadResponse])
async def list_leads(
    search: str | None = None,
    bot_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[Lead]:
    """
    List all leads for the tenant.
    
    Args:
        search: Optional search term for name, email, or phone.
        bot_id: Optional filter by bot ID.
        skip: Number of records to skip.
        limit: Maximum number of records to return.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        List of leads.
    """
    # Get all bot IDs for this tenant
    tenant_bot_ids = db.query(Bot.id).filter(Bot.tenant_id == current_tenant.id).all()
    tenant_bot_ids = [b[0] for b in tenant_bot_ids]
    
    # Query leads that belong to tenant's bots OR tenant itself
    query = db.query(Lead).filter(
        or_(
            Lead.bot_id.in_(tenant_bot_ids),
            Lead.tenant_id == current_tenant.id
        )
    )
    
    if bot_id:
        query = query.filter(Lead.bot_id == bot_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Lead.name.ilike(search_term),
                Lead.email.ilike(search_term),
                Lead.phone.ilike(search_term)
            )
        )
    
    leads = query.order_by(
        Lead.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return leads


@router.post("", response_model=LeadResponse)
async def create_lead(
    lead_data: LeadCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> Lead:
    """
    Create a new lead manually.
    
    Args:
        lead_data: The lead data.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The created lead.
    """
    # Plan gate: automated lead sources require lead automation feature.
    source_value = (lead_data.source or "manual").strip().lower() if isinstance(lead_data.source, str) else "manual"
    if source_value != "manual":
        if not SubscriptionService(db).check_feature(current_tenant.id, "lead_automation"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu kaynak için lead otomasyonu planınızda aktif değil (Lead Automation)."
            )

    # Get first bot of tenant (or create without bot_id)
    bot = db.query(Bot).filter(Bot.tenant_id == current_tenant.id).first()

    normalized_email = lead_data.email.strip() if isinstance(lead_data.email, str) else None
    normalized_phone = lead_data.phone.strip() if isinstance(lead_data.phone, str) else None
    normalized_notes = lead_data.notes.strip() if isinstance(lead_data.notes, str) else None
    normalized_source = source_value or "manual"

    lead = Lead(
        tenant_id=current_tenant.id,
        bot_id=bot.id if bot else None,
        name=lead_data.name.strip(),
        email=normalized_email or None,
        phone=normalized_phone or None,
        notes=normalized_notes or None,
        source=normalized_source or "manual",
        status="new"
    )
    
    db.add(lead)
    try:
        db.commit()
        db.refresh(lead)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead kaydedilemedi. Lütfen e-posta/telefon formatını kontrol edin ve tekrar deneyin."
        )

    AuditLogService(db).log(
        action="lead.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="lead",
        resource_id=str(lead.id),
        payload={"name": lead.name, "source": lead.source},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: UUID,
    lead_data: LeadUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> Lead:
    """
    Update a lead.
    
    Args:
        lead_id: The lead ID.
        lead_data: The lead data to update.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The updated lead.
    """
    # Get all bot IDs for this tenant
    tenant_bot_ids = db.query(Bot.id).filter(Bot.tenant_id == current_tenant.id).all()
    tenant_bot_ids = [b[0] for b in tenant_bot_ids]
    
    # Find lead that belongs to tenant's bots OR tenant itself
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        or_(
            Lead.bot_id.in_(tenant_bot_ids),
            Lead.tenant_id == current_tenant.id
        )
    ).first()
    
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead bulunamadı"
        )
    
    update_data = lead_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)
    
    db.commit()
    db.refresh(lead)

    AuditLogService(db).log(
        action="lead.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="lead",
        resource_id=str(lead.id),
        payload=update_data,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    """
    Delete a lead.
    
    Args:
        lead_id: The lead ID.
        current_tenant: The user's tenant.
        db: Database session.
    """
    # Get all bot IDs for this tenant
    tenant_bot_ids = db.query(Bot.id).filter(Bot.tenant_id == current_tenant.id).all()
    tenant_bot_ids = [b[0] for b in tenant_bot_ids]
    
    # Find lead that belongs to tenant's bots OR tenant itself
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        or_(
            Lead.bot_id.in_(tenant_bot_ids),
            Lead.tenant_id == current_tenant.id
        )
    ).first()
    
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead bulunamadı"
        )
    
    db.delete(lead)
    db.commit()

    AuditLogService(db).log(
        action="lead.delete",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="lead",
        resource_id=str(lead.id),
        payload={"name": lead.name},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    
    return None


@router.get("/bots/{bot_id}", response_model=list[LeadResponse])
async def list_bot_leads(
    bot_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[Lead]:
    """
    List leads for a specific bot.
    
    Args:
        bot_id: The bot ID.
        skip: Number of records to skip.
        limit: Maximum number of records to return.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        List of leads.
    """
    # Verify bot belongs to tenant
    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        Bot.tenant_id == current_tenant.id
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot bulunamadı"
        )
    
    leads = db.query(Lead).filter(
        Lead.bot_id == bot_id
    ).order_by(
        Lead.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return leads
