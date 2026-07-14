"""
Pydantic schemas for Tool model.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolBase(BaseModel):
    key: str
    slug: str | None = None
    name: str
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    tags: list[str] | None = None
    required_plan: str | None = None
    status: str
    is_public: bool
    coming_soon: bool
    is_premium: bool = False
    input_schema_json: dict = Field(default_factory=dict)
    output_schema_json: dict = Field(default_factory=dict)
    required_integrations_json: list[str] = Field(default_factory=list)
    n8n_workflow_id: str | None = None


class ToolCreate(ToolBase):
    pass


class ToolUpdate(BaseModel):
    key: str | None = None
    slug: str | None = None
    name: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    tags: list[str] | None = None
    required_plan: str | None = None
    status: str | None = None
    is_public: bool | None = None
    coming_soon: bool | None = None
    is_premium: bool | None = None
    input_schema_json: dict | None = None
    output_schema_json: dict | None = None
    required_integrations_json: list[str] | None = None
    n8n_workflow_id: str | None = None


class ToolResponse(ToolBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
