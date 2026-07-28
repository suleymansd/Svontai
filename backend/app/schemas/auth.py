"""
Pydantic schemas for authentication.
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.password_policy import validate_password_strength


class LoginRequest(BaseModel):
    """Schema for login request."""
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    two_factor_code: str | None = None
    portal: Literal["tenant", "super_admin"] = "tenant"
    admin_session_note: str | None = None


class AccessTokenResponse(BaseModel):
    """Access token response; refresh credentials stay in an HttpOnly cookie."""
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Schema for authenticated password change."""
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)


class TwoFactorSetupRequest(BaseModel):
    """Schema for 2FA setup start."""
    current_password: str


class TwoFactorEnableRequest(BaseModel):
    """Schema for enabling 2FA."""
    code: str


class TwoFactorDisableRequest(BaseModel):
    """Schema for disabling 2FA."""
    current_password: str
    code: str


class TwoFactorStatusResponse(BaseModel):
    """Schema for 2FA status."""
    enabled: bool


class TwoFactorSetupResponse(BaseModel):
    """Schema for 2FA setup response."""
    secret: str
    otpauth_uri: str


class AdminTwoFactorEnableRequest(BaseModel):
    """Enable mandatory super-admin 2FA with a short-lived enrollment token."""
    setup_token: str
    code: str
