"""
System event model for observability and error tracking.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SystemEvent(Base):
    """High-volume system events for observability."""

    __tablename__ = "system_events"
    __table_args__ = (
        Index("ix_system_events_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    message: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    meta_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    tenant = relationship("Tenant")
