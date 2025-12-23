"""
Pydantic schemas for Bot model.
"""

from datetime import datetime
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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
    created_at: datetime
    updated_at: datetime


class BotPublicInfo(BaseModel):
    """Public bot information for widget."""
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    welcome_message: str
    primary_color: str
    widget_position: str

