"""
Feature flag model for tenant overrides.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FeatureFlag(Base):
    """Feature flag per tenant or global."""

    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_feature_flags_tenant_key"),
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
    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    payload_json: Mapped[dict | None] = mapped_column(
        JSON,
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

    tenant: Mapped["Tenant | None"] = relationship("Tenant", back_populates="feature_flags")

    def __repr__(self) -> str:
        return f"<FeatureFlag {self.key} ({self.tenant_id})>"
