"""
WhatsApp integration model for Cloud API configuration.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WhatsAppIntegration(Base):
    """WhatsApp Cloud API integration configuration."""
    
    __tablename__ = "whatsapp_integrations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    bot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bots.id", ondelete="SET NULL"),
        nullable=True
    )
    whatsapp_phone_number_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    whatsapp_business_account_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    access_token: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    webhook_verify_token: Mapped[str] = mapped_column(
        String(100),
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
        back_populates="whatsapp_integrations"
    )
    bot: Mapped["Bot | None"] = relationship(
        "Bot",
        back_populates="whatsapp_integration"
    )
    
    def __repr__(self) -> str:
        return f"<WhatsAppIntegration {self.whatsapp_phone_number_id}>"

