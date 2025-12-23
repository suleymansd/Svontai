"""
Lead management router.
"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, EmailStr

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.lead import Lead
from app.schemas.lead import LeadResponse, LeadWithBotName

router = APIRouter(prefix="/leads", tags=["Leads"])


class LeadCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = "manual"


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
    db: Session = Depends(get_db)
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
    
    # Query leads that belong to tenant's bots OR have no bot
    query = db.query(Lead).filter(
        or_(
            Lead.bot_id.in_(tenant_bot_ids),
            Lead.bot_id.is_(None)
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
    db: Session = Depends(get_db)
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
    # Get first bot of tenant (or create without bot_id)
    bot = db.query(Bot).filter(Bot.tenant_id == current_tenant.id).first()
    
    lead = Lead(
        bot_id=bot.id if bot else None,
        name=lead_data.name,
        email=lead_data.email,
        phone=lead_data.phone,
        notes=lead_data.notes,
        source=lead_data.source or "manual",
        status="new"
    )
    
    db.add(lead)
    db.commit()
    db.refresh(lead)
    
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: UUID,
    lead_data: LeadUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
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
    
    # Find lead that belongs to tenant's bots OR has no bot
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        or_(
            Lead.bot_id.in_(tenant_bot_ids),
            Lead.bot_id.is_(None)
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
    
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
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
    
    # Find lead that belongs to tenant's bots OR has no bot
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        or_(
            Lead.bot_id.in_(tenant_bot_ids),
            Lead.bot_id.is_(None)
        )
    ).first()
    
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead bulunamadı"
        )
    
    db.delete(lead)
    db.commit()
    
    return None


@router.get("/bots/{bot_id}", response_model=list[LeadResponse])
async def list_bot_leads(
    bot_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
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

