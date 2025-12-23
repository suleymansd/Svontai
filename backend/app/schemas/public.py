"""
Pydantic schemas for public chat endpoints.
"""

from uuid import UUID

from pydantic import BaseModel

from app.schemas.bot import BotPublicInfo


class ChatInitRequest(BaseModel):
    """Schema for chat initialization request."""
    bot_public_key: str
    external_user_id: str | None = None


class ChatInitResponse(BaseModel):
    """Schema for chat initialization response."""
    conversation_id: UUID
    external_user_id: str
    bot: BotPublicInfo
    welcome_message: str


class ChatSendRequest(BaseModel):
    """Schema for sending a chat message."""
    conversation_id: UUID
    message: str


class ChatSendResponse(BaseModel):
    """Schema for chat send response."""
    message_id: UUID
    reply: str

