"""
WhatsApp Account model for storing Meta WhatsApp Business API credentials.
"""

import uuid
from datetime import datetime
from app.core.time import utc_now_naive
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TokenStatus(str, Enum):
    """Token status enum."""
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class WebhookStatus(str, Enum):
    """Webhook status enum."""
    NOT_CONFIGURED = "not_configured"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    FAILED = "failed"


class WhatsAppAccount(Base):
    """WhatsApp provider credentials and tenant session configuration."""
    
    __tablename__ = "whatsapp_accounts"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    provider: Mapped[str] = mapped_column(
        String(30),
        default="meta_cloud",
        nullable=False,
        comment="WhatsApp transport provider: meta_cloud or openwa",
    )
    provider_session_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="External provider session identifier",
    )
    provider_webhook_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="External provider webhook identifier",
    )
    provider_metadata_json: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="Non-sensitive provider state",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Meta WhatsApp Business API identifiers
    waba_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="WhatsApp Business Account ID"
    )
    phone_number_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Phone Number ID from Meta"
    )
    display_phone_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Display phone number (e.g., +90 555 123 4567)"
    )
    business_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Meta Business ID"
    )
    app_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Meta App ID"
    )
    
    # Encrypted access token
    access_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Encrypted long-lived access token"
    )
    token_status: Mapped[str] = mapped_column(
        String(20),
        default=TokenStatus.PENDING.value,
        nullable=False
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # Webhook configuration
    webhook_verify_token: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Unique verify token for webhook"
    )
    webhook_status: Mapped[str] = mapped_column(
        String(30),
        default=WebhookStatus.NOT_CONFIGURED.value,
        nullable=False
    )
    webhook_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Status flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False
    )
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="whatsapp_accounts"
    )
    
    def __repr__(self) -> str:
        return f"<WhatsAppAccount {self.provider}:{self.display_phone_number or self.id}>"
