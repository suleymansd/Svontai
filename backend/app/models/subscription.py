"""
TenantSubscription model for tracking tenant subscriptions.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Integer, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SubscriptionStatus(str, Enum):
    """Subscription status options."""
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TenantSubscription(Base):
    """TenantSubscription model for tracking tenant subscription status."""
    
    __tablename__ = "tenant_subscriptions"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True  # One subscription per tenant
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=SubscriptionStatus.TRIAL.value,
        nullable=False
    )
    # Dates
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    # Usage tracking
    messages_used_this_month: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    usage_reset_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    # Payment provider info (for future integration)
    payment_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    external_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    external_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
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
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="subscription"
    )
    plan: Mapped["Plan"] = relationship(
        "Plan",
        back_populates="subscriptions"
    )
    
    def __repr__(self) -> str:
        return f"<TenantSubscription {self.tenant_id} - {self.status}>"
    
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        if self.status in [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value]:
            if self.status == SubscriptionStatus.TRIAL.value and self.trial_ends_at:
                return datetime.utcnow() < self.trial_ends_at
            if self.ends_at:
                return datetime.utcnow() < self.ends_at
            return True
        return False
    
    def can_send_message(self) -> bool:
        """Check if tenant can send more messages this month."""
        if not self.is_active():
            return False
        return self.messages_used_this_month < self.plan.message_limit
    
    def increment_message_count(self):
        """Increment the message count for this month."""
        self.messages_used_this_month += 1
    
    def reset_monthly_usage(self):
        """Reset monthly usage counters."""
        self.messages_used_this_month = 0
        self.usage_reset_at = datetime.utcnow()

