"""
Pydantic schemas for RBAC.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RoleResponse(BaseModel):
    """Role response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None


class PermissionResponse(BaseModel):
    """Permission response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    description: str | None = None


class MembershipResponse(BaseModel):
    """Tenant membership response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    status: str
    role: RoleResponse
    created_at: datetime
