"""
Pydantic schemas for Message model.
"""

from datetime import datetime
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, ConfigDict


class MessageSender(str, Enum):
    """Message sender types."""
    USER = "user"
    BOT = "bot"
    SYSTEM = "system"


class MessageBase(BaseModel):
    """Base schema for Message."""
    content: str
    sender: MessageSender


class MessageCreate(MessageBase):
    """Schema for creating a new message."""
    conversation_id: UUID
    raw_payload: dict | None = None


class MessageResponse(MessageBase):
    """Schema for message response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    conversation_id: UUID
    created_at: datetime

