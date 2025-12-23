"""
Plan model for subscription tiers.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Integer, Boolean, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PlanType(str, Enum):
    """Plan tier types."""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class Plan(Base):
    """Plan model representing subscription tiers."""
    
    __tablename__ = "plans"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
    plan_type: Mapped[str] = mapped_column(
        String(20),
        default=PlanType.FREE.value,
        nullable=False
    )
    # Pricing
    price_monthly: Mapped[float] = mapped_column(
        Numeric(10, 2),
        default=0.0,
        nullable=False
    )
    price_yearly: Mapped[float] = mapped_column(
        Numeric(10, 2),
        default=0.0,
        nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="TRY",
        nullable=False
    )
    # Limits
    message_limit: Mapped[int] = mapped_column(
        Integer,
        default=100,  # Messages per month
        nullable=False
    )
    bot_limit: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )
    knowledge_items_limit: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False
    )
    # Feature flags as JSON
    feature_flags: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )
    # Trial settings
    trial_days: Mapped[int] = mapped_column(
        Integer,
        default=14,
        nullable=False
    )
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
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
    subscriptions: Mapped[list["TenantSubscription"]] = relationship(
        "TenantSubscription",
        back_populates="plan",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Plan {self.name}>"


# Default plans configuration
DEFAULT_PLANS = [
    {
        "name": "free",
        "display_name": "Ücretsiz",
        "description": "Başlamak için ideal",
        "plan_type": PlanType.FREE.value,
        "price_monthly": 0,
        "price_yearly": 0,
        "message_limit": 100,
        "bot_limit": 1,
        "knowledge_items_limit": 20,
        "trial_days": 0,
        "sort_order": 0,
        "feature_flags": {
            "whatsapp_integration": False,
            "analytics": False,
            "custom_branding": False,
            "priority_support": False,
            "api_access": False,
            "export_data": False,
            "operator_takeover": False,
            "lead_automation": False
        }
    },
    {
        "name": "starter",
        "display_name": "Başlangıç",
        "description": "Küçük işletmeler için",
        "plan_type": PlanType.STARTER.value,
        "price_monthly": 299,
        "price_yearly": 2990,
        "message_limit": 1000,
        "bot_limit": 2,
        "knowledge_items_limit": 100,
        "trial_days": 14,
        "sort_order": 1,
        "feature_flags": {
            "whatsapp_integration": True,
            "analytics": True,
            "custom_branding": False,
            "priority_support": False,
            "api_access": False,
            "export_data": True,
            "operator_takeover": False,
            "lead_automation": True
        }
    },
    {
        "name": "pro",
        "display_name": "Profesyonel",
        "description": "Büyüyen işletmeler için",
        "plan_type": PlanType.PRO.value,
        "price_monthly": 599,
        "price_yearly": 5990,
        "message_limit": 5000,
        "bot_limit": 5,
        "knowledge_items_limit": 500,
        "trial_days": 14,
        "sort_order": 2,
        "feature_flags": {
            "whatsapp_integration": True,
            "analytics": True,
            "custom_branding": True,
            "priority_support": True,
            "api_access": True,
            "export_data": True,
            "operator_takeover": True,
            "lead_automation": True
        }
    },
    {
        "name": "business",
        "display_name": "İşletme",
        "description": "Büyük ekipler için",
        "plan_type": PlanType.BUSINESS.value,
        "price_monthly": 1299,
        "price_yearly": 12990,
        "message_limit": 20000,
        "bot_limit": 20,
        "knowledge_items_limit": 2000,
        "trial_days": 14,
        "sort_order": 3,
        "feature_flags": {
            "whatsapp_integration": True,
            "analytics": True,
            "custom_branding": True,
            "priority_support": True,
            "api_access": True,
            "export_data": True,
            "operator_takeover": True,
            "lead_automation": True,
            "white_label": True,
            "dedicated_support": True
        }
    }
]

