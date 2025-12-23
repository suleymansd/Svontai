"""
Bot model for AI-powered chat assistants.
"""

import uuid
import secrets
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WidgetPosition(str, Enum):
    """Widget position options."""
    LEFT = "left"
    RIGHT = "right"


def generate_public_key() -> str:
    """Generate a unique public key for widget authentication."""
    return f"bot_{secrets.token_urlsafe(24)}"


class Bot(Base):
    """Bot model representing an AI assistant."""
    
    __tablename__ = "bots"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    welcome_message: Mapped[str] = mapped_column(
        Text,
        default="Merhaba! Size nasıl yardımcı olabilirim?",
        nullable=False
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default="tr",
        nullable=False
    )
    primary_color: Mapped[str] = mapped_column(
        String(7),
        default="#3C82F6",
        nullable=False
    )
    widget_position: Mapped[str] = mapped_column(
        String(10),
        default=WidgetPosition.RIGHT.value,
        nullable=False
    )
    public_key: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        default=generate_public_key,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
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
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="bots"
    )
    knowledge_items: Mapped[list["BotKnowledgeItem"]] = relationship(
        "BotKnowledgeItem",
        back_populates="bot",
        cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="bot",
        cascade="all, delete-orphan"
    )
    leads: Mapped[list["Lead"]] = relationship(
        "Lead",
        back_populates="bot",
        cascade="all, delete-orphan"
    )
    whatsapp_integration: Mapped["WhatsAppIntegration | None"] = relationship(
        "WhatsAppIntegration",
        back_populates="bot",
        uselist=False
    )
    settings: Mapped["BotSettings | None"] = relationship(
        "BotSettings",
        back_populates="bot",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Bot {self.name}>"

