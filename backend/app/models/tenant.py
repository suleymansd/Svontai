"""
Tenant model for multi-tenant SaaS architecture.
"""

import uuid
import re
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from name."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    return slug[:100]


class Tenant(Base):
    """Tenant model representing a business/organization."""
    
    __tablename__ = "tenants"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    settings: Mapped[dict] = mapped_column(
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
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="tenants"
    )
    bots: Mapped[list["Bot"]] = relationship(
        "Bot",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    whatsapp_integrations: Mapped[list["WhatsAppIntegration"]] = relationship(
        "WhatsAppIntegration",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    whatsapp_accounts: Mapped[list["WhatsAppAccount"]] = relationship(
        "WhatsAppAccount",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    subscription: Mapped["TenantSubscription | None"] = relationship(
        "TenantSubscription",
        back_populates="tenant",
        uselist=False
    )
    onboarding: Mapped["TenantOnboarding | None"] = relationship(
        "TenantOnboarding",
        back_populates="tenant",
        uselist=False
    )
    
    def __repr__(self) -> str:
        return f"<Tenant {self.name}>"

