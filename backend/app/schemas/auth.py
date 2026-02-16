"""
Pydantic schemas for authentication.
"""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Schema for login request."""
    email: EmailStr
    password: str
    two_factor_code: str | None = None


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""
    refresh_token: str


class AccessTokenResponse(BaseModel):
    """Schema for access token response only."""
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Schema for authenticated password change."""
    current_password: str
    new_password: str


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
