"""
Message model for conversation messages.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageSender(str, Enum):
    """Message sender types."""
    USER = "user"
    BOT = "bot"
    SYSTEM = "system"


class Message(Base):
    """Message model representing a single chat message."""
    
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False
    )
    sender: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    raw_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages"
    )
    
    def __repr__(self) -> str:
        return f"<Message {self.id} from {self.sender}>"
