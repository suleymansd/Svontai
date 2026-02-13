"""Pydantic schemas for SystemEvent."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SystemEventBase(BaseModel):
    tenant_id: str | None = None
    source: str
    level: str
    code: str
    message: str
    meta_json: dict | None = None
    correlation_id: str | None = None


class SystemEventCreate(SystemEventBase):
    pass


class SystemEventResponse(SystemEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
