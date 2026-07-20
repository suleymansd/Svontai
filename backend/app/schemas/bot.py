"""
Pydantic schemas for Bot model.
"""

from datetime import datetime
from uuid import UUID
from enum import Enum
from typing import Any, Literal
import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WidgetPosition(str, Enum):
    """Widget position options."""
    LEFT = "left"
    RIGHT = "right"


class BotBase(BaseModel):
    """Base schema for Bot."""
    name: str
    description: str | None = None
    welcome_message: str = "Merhaba! Size nasıl yardımcı olabilirim?"
    language: str = "tr"
    primary_color: str = Field(default="#3C82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    widget_position: WidgetPosition = WidgetPosition.RIGHT


class BotCreate(BotBase):
    """Schema for creating a new bot."""
    pass


class BotUpdate(BaseModel):
    """Schema for updating a bot."""
    name: str | None = None
    description: str | None = None
    welcome_message: str | None = None
    language: str | None = None
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    widget_position: WidgetPosition | None = None
    is_active: bool | None = None


class BotResponse(BotBase):
    """Schema for bot response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    tenant_id: UUID
    public_key: str
    is_active: bool
    assistant_type: Literal["primary", "specialist"]
    specialist_key: str | None = None
    created_at: datetime
    updated_at: datetime


class BotPublicInfo(BaseModel):
    """Public bot information for widget."""
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    welcome_message: str
    primary_color: str
    widget_position: str


AssistantGoal = Literal["support", "sales", "appointments", "mixed"]
ResponseLength = Literal["concise", "balanced", "detailed"]
PricePolicy = Literal["known_only", "confirm_before_sending", "never_share"]
HandoffMode = Literal["automatic", "suggest", "manual"]
CapabilityKey = Literal[
    "knowledge_support",
    "lead_qualification",
    "appointment_management",
    "human_handoff",
    "media_catalog",
]


class AssistantTraining(BaseModel):
    goal: AssistantGoal = "mixed"
    tone: Literal["formal", "friendly", "professional", "casual"] = "professional"
    response_length: ResponseLength = "balanced"
    price_policy: PricePolicy = "known_only"
    handoff_mode: HandoffMode = "automatic"
    business_summary: str = Field(default="", max_length=3000)


class AssistantTrainingUpdate(AssistantTraining):
    pass


class AssistantCapabilityUpdate(BaseModel):
    enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def validate_config_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False)) > 50_000:
            raise ValueError("Capability configuration is too large")
        return value


class AssistantCapabilityResponse(BaseModel):
    key: CapabilityKey
    name: str
    description: str
    enabled: bool
    ready: bool
    status: Literal["active", "needs_setup", "disabled"]
    missing_requirements: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    locked: bool = False


class AssistantProfileResponse(BaseModel):
    assistant: BotResponse
    training: AssistantTraining
    capabilities: list[AssistantCapabilityResponse]
    completion_percent: int
