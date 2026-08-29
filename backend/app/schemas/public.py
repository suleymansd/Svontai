"""
Pydantic schemas for public chat endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.bot import BotPublicInfo


class ChatInitRequest(BaseModel):
    """Schema for chat initialization request."""
    bot_public_key: str = Field(min_length=16, max_length=255)


class ChatInitResponse(BaseModel):
    """Schema for chat initialization response."""
    conversation_id: UUID
    external_user_id: str
    session_token: str
    bot: BotPublicInfo
    welcome_message: str
    conversation_status: str
    is_ai_paused: bool


class ChatSendRequest(BaseModel):
    """Schema for sending a chat message."""
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=4000)
    session_token: str = Field(min_length=32, max_length=2048)


class ChatSendResponse(BaseModel):
    """Schema for chat send response."""
    user_message_id: UUID
    reply_message_id: UUID | None = None
    reply: str | None = None
    user_created_at: datetime
    reply_created_at: datetime | None = None
    conversation_status: str
    is_ai_paused: bool


class ChatMessage(BaseModel):
    """Schema for public chat messages."""
    id: UUID
    sender: str
    content: str
    created_at: datetime


class ChatMessagesResponse(BaseModel):
    """Schema for public chat messages response."""
    messages: list[ChatMessage]
    conversation_status: str
    is_ai_paused: bool
