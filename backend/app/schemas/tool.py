"""
Pydantic schemas for Tool model.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ToolBase(BaseModel):
    key: str
    name: str
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    tags: list[str] | None = None
    required_plan: str | None = None
    status: str
    is_public: bool
    coming_soon: bool


class ToolCreate(ToolBase):
    pass


class ToolUpdate(BaseModel):
    key: str | None = None
    name: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    tags: list[str] | None = None
    required_plan: str | None = None
    status: str | None = None
    is_public: bool | None = None
    coming_soon: bool | None = None


class ToolResponse(ToolBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
