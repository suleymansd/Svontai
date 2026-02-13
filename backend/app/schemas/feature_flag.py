"""
Pydantic schemas for feature flags.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FeatureFlagUpsert(BaseModel):
    """Upsert schema for feature flags."""
    enabled: bool = True
    payload_json: dict | None = None


class FeatureFlagResponse(BaseModel):
    """Feature flag response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    key: str
    enabled: bool
    payload_json: dict | None = None
    created_at: datetime
    updated_at: datetime
