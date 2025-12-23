"""
Pydantic schemas for Lead model.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class LeadBase(BaseModel):
    """Base schema for Lead."""
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    notes: str | None = None
    source: str | None = None
    status: str | None = None


class LeadCreate(LeadBase):
    """Schema for creating a new lead."""
    bot_id: UUID
    conversation_id: UUID | None = None


class LeadPublicCreate(LeadBase):
    """Schema for public lead creation."""
    bot_public_key: str
    conversation_id: UUID | None = None


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    notes: str | None = None


class LeadResponse(LeadBase):
    """Schema for lead response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    bot_id: UUID | None
    conversation_id: UUID | None
    created_at: datetime


class LeadWithBotName(LeadResponse):
    """Schema for lead response with bot name."""
    bot_name: str

