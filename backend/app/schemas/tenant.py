"""
Pydantic schemas for Tenant model.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantBase(BaseModel):
    """Base schema for Tenant."""
    name: str


class TenantCreate(TenantBase):
    """Schema for creating a new tenant."""
    pass


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""
    name: str | None = None
    settings: dict | None = None


class TenantResponse(TenantBase):
    """Schema for tenant response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    slug: str | None = None
    created_at: datetime
    updated_at: datetime

