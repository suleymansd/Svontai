"""
Pydantic schemas for User model.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, model_validator

from app.core.legal import KVKK_NOTICE_VERSION, PRIVACY_NOTICE_VERSION, TERMS_VERSION
from app.core.password_policy import validate_password_strength


class UserBase(BaseModel):
    """Base schema for User."""
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str
    terms_accepted: bool
    privacy_notice_acknowledged: bool
    terms_version: str
    privacy_version: str
    kvkk_notice_version: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode="after")
    def validate_legal_acknowledgements(self):
        if not self.terms_accepted:
            raise ValueError("Kullanım koşulları ve hizmet sözleşmesi kabul edilmelidir")
        if not self.privacy_notice_acknowledged:
            raise ValueError("KVKK aydınlatma metni ve gizlilik politikası okunmalıdır")
        if self.terms_version != TERMS_VERSION:
            raise ValueError("Kullanım koşulları sürümü güncel değil")
        if self.privacy_version != PRIVACY_NOTICE_VERSION:
            raise ValueError("Gizlilik politikası sürümü güncel değil")
        if self.kvkk_notice_version != KVKK_NOTICE_VERSION:
            raise ValueError("KVKK aydınlatma metni sürümü güncel değil")
        return self


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
    two_factor_enabled: bool = False
    last_login: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserWithTenants(UserResponse):
    """Schema for user response with tenants."""
    tenants: list["TenantResponse"] = []


# Avoid circular import
from app.schemas.tenant import TenantResponse
UserWithTenants.model_rebuild()
