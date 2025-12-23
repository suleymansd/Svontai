"""
UsageLog model for tracking detailed usage metrics.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Integer, JSON, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UsageType(str, Enum):
    """Types of usage to track."""
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    BOT_CREATED = "bot_created"
    BOT_DELETED = "bot_deleted"
    KNOWLEDGE_ADDED = "knowledge_added"
    LEAD_CAPTURED = "lead_captured"
    CONVERSATION_STARTED = "conversation_started"
    WHATSAPP_MESSAGE = "whatsapp_message"
    WIDGET_MESSAGE = "widget_message"
    AI_RESPONSE = "ai_response"
    OPERATOR_TAKEOVER = "operator_takeover"


class UsageLog(Base):
    """UsageLog model for detailed usage tracking."""
    
    __tablename__ = "usage_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    bot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bots.id", ondelete="SET NULL"),
        nullable=True
    )
    usage_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    count: Mapped[int] = mapped_column(
        Integer,
        default=1,
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
        nullable=False,
        index=True
    )
    
    def __repr__(self) -> str:
        return f"<UsageLog {self.usage_type} - {self.count}>"


class DailyStats(Base):
    """Aggregated daily statistics per tenant."""
    
    __tablename__ = "daily_stats"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True
    )
    # Message counts
    messages_sent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    messages_received: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    ai_responses: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    # Conversation counts
    conversations_started: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    conversations_total: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    # Lead counts
    leads_captured: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    # Source breakdown
    whatsapp_messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    widget_messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    # Operator stats
    operator_takeovers: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    # Extra data
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
    
    def __repr__(self) -> str:
        return f"<DailyStats {self.tenant_id} - {self.date}>"

