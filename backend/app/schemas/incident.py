"""Pydantic schemas for Incident."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class IncidentBase(BaseModel):
    tenant_id: str | None = None
    title: str
    severity: str
    status: str
    assigned_to: str | None = None
    root_cause: str | None = None
    resolution: str | None = None


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    title: str | None = None
    severity: str | None = None
    status: str | None = None
    assigned_to: str | None = None
    root_cause: str | None = None
    resolution: str | None = None


class IncidentResponse(IncidentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
