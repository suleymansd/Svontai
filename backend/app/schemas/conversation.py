"""
Pydantic schemas for Conversation model.
"""

from datetime import datetime
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, ConfigDict


class ConversationSource(str, Enum):
    """Source of the conversation."""
    WHATSAPP = "whatsapp"
    WEB_WIDGET = "web_widget"


class ConversationBase(BaseModel):
    """Base schema for Conversation."""
    external_user_id: str
    source: ConversationSource = ConversationSource.WEB_WIDGET


class ConversationCreate(ConversationBase):
    """Schema for creating a new conversation."""
    bot_id: UUID
    extra_data: dict = {}


class ConversationResponse(ConversationBase):
    """Schema for conversation response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    bot_id: UUID
    extra_data: dict
    created_at: datetime
    updated_at: datetime


class ConversationWithMessages(ConversationResponse):
    """Schema for conversation with messages."""
    messages: list["MessageResponse"] = []


# Avoid circular import
from app.schemas.message import MessageResponse
ConversationWithMessages.model_rebuild()

