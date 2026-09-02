"""
Pydantic schemas for authentication.
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.password_policy import validate_password_strength


class LoginRequest(BaseModel):
    """Schema for login request."""
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    two_factor_code: str | None = None
    portal: Literal["tenant", "super_admin"] = "tenant"
    admin_session_note: str | None = None
    client: Literal["web", "mobile"] = "web"
    device_id: str | None = Field(default=None, min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    device_name: str | None = Field(default=None, max_length=120)
    platform: Literal["ios", "android"] | None = None
    app_version: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_mobile_client(self):
        if self.client != "mobile":
            return self
        if self.portal != "tenant":
            raise ValueError("Mobil uygulama yalnızca işletme paneli girişini destekler")
        if not self.device_id or not self.platform:
            raise ValueError("Mobil giriş için cihaz kimliği ve platform zorunludur")
        return self


class AccessTokenResponse(BaseModel):
    """Access token response; refresh credentials stay in an HttpOnly cookie."""
    access_token: str
    token_type: str = "bearer"


class MobileAccessTokenResponse(AccessTokenResponse):
    """Native clients receive a rotating refresh token for secure device storage."""

    refresh_token: str
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Refresh payload used only by native clients."""

    refresh_token: str | None = Field(default=None, min_length=32, max_length=4096)
    device_id: str | None = Field(default=None, min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


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
