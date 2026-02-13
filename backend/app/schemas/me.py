"""
Pydantic schema for /api/me response.
"""

from pydantic import BaseModel

from app.schemas.user import UserResponse
from app.schemas.tenant import TenantResponse
from app.schemas.rbac import RoleResponse


class MeResponse(BaseModel):
    """Aggregated context response."""
    user: UserResponse
    tenant: TenantResponse | None = None
    role: RoleResponse | None = None
    permissions: list[str]
    entitlements: dict
    feature_flags: dict
