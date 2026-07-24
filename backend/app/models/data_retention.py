"""Tenant data retention policy."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class DataRetentionPolicy(Base):
    """Configurable deletion windows with a legal-hold safety switch."""

    __tablename__ = "data_retention_policies"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message_content_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    raw_payload_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    product_analytics_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    usage_log_days: Mapped[int] = mapped_column(Integer, nullable=False, default=730)
    system_event_days: Mapped[int] = mapped_column(Integer, nullable=False, default=730)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )
