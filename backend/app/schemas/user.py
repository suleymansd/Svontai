"""
Pydantic schemas for User model.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    """Base schema for User."""
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    full_name: str | None = None
    email: EmailStr | None = None


class UserAdminUpdate(BaseModel):
    """Schema for admin updating a user."""
    full_name: str | None = None
    email: EmailStr | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    """Schema for user response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    is_admin: bool = False
    is_active: bool = True
    email_verified: bool = True
    last_login: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserWithTenants(UserResponse):
    """Schema for user response with tenants."""
    tenants: list["TenantResponse"] = []


# Avoid circular import
from app.schemas.tenant import TenantResponse
UserWithTenants.model_rebuild()
