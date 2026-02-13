"""
Lead model for customer contact information.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Text, Boolean, JSON, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LeadStatus(str, Enum):
    """Lead status options."""
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"


class LeadSource(str, Enum):
    """Lead source options."""
    WEB_WIDGET = "web"
    WHATSAPP = "whatsapp"
    MANUAL = "manual"
    IMPORT = "import"


class Lead(Base):
    """Lead model for storing customer contact information."""
    
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_bot_created", "bot_id", "created_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    bot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True
    )
    # Contact info
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    # Status & scoring
    status: Mapped[str] = mapped_column(
        String(50),
        default=LeadStatus.NEW.value,
        nullable=False
    )
    score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    # Source tracking
    source: Mapped[str] = mapped_column(
        String(50),
        default=LeadSource.WEB_WIDGET.value,
        nullable=False
    )
    # Auto-detection flags
    is_auto_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    detection_confidence: Mapped[float] = mapped_column(
        default=0.0,
        nullable=False
    )
    detected_fields: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )
    # Notes & metadata
    notes: Mapped[str | None] = mapped_column(
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
    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
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
        back_populates="leads"
    )
    conversation: Mapped["Conversation | None"] = relationship(
        "Conversation",
        back_populates="lead"
    )
    
    def __repr__(self) -> str:
        return f"<Lead {self.name or self.email or self.phone}>"
