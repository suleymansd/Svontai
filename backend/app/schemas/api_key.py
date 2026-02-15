"""
Pydantic schemas for tenant API key management.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    last4: str
    revoked_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyResponse]


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    current_password: str = Field(min_length=1, max_length=200)


class ApiKeyCreateResponse(ApiKeyResponse):
    secret: str


class ApiKeyRevokeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
