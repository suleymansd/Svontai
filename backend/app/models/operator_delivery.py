"""Durable outbox for operator messages; ambiguous sends are never retried."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class OperatorDelivery(Base):
    __tablename__ = "operator_deliveries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_id", name="uq_operator_delivery_request"),
        Index("ix_operator_delivery_status_updated", "status", "updated_at"),
        Index("ix_operator_delivery_tenant", "tenant_id"),
    )
    message_id: Mapped[UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    request_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    attempt_token: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
