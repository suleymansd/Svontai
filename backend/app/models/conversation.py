"""
Conversation model for chat sessions.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, JSON, Boolean, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConversationSource(str, Enum):
    """Source of the conversation."""
    WHATSAPP = "whatsapp"
    WEB_WIDGET = "web_widget"


class ConversationStatus(str, Enum):
    """Conversation status for operator takeover."""
    AI_ACTIVE = "ai_active"
    HUMAN_TAKEOVER = "human_takeover"
    CLOSED = "closed"
    WAITING = "waiting"


class Conversation(Base):
    """Conversation model representing a chat session."""
    
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_bot_updated", "bot_id", "updated_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    bot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False
    )
    external_user_id: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(20),
        default=ConversationSource.WEB_WIDGET.value,
        nullable=False
    )
    # Operator takeover fields
    status: Mapped[str] = mapped_column(
        String(20),
        default=ConversationStatus.AI_ACTIVE.value,
        nullable=False
    )
    is_ai_paused: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    takeover_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    # Lead detection
    has_lead: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    lead_score: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )
    # Summary & tags
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    tags: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False
    )
    extra_data: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    bot: Mapped["Bot"] = relationship(
        "Bot",
        back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )
    lead: Mapped["Lead | None"] = relationship(
        "Lead",
        back_populates="conversation",
        uselist=False
    )
    
    def __repr__(self) -> str:
        return f"<Conversation {self.id}>"
