"""
Monthly usage counters for billing-aware metering.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenantUsageCounter(Base):
    __tablename__ = "tenant_usage_counters"
    __table_args__ = (
        Index("ix_tenant_usage_counters_tenant_period", "tenant_id", "period_key", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # YYYY-MM in UTC
    period_key: Mapped[str] = mapped_column(String(7), nullable=False)

    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    voice_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    workflow_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outbound_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    extra_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

