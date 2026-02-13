"""
Appointment model for scheduling and reminder workflows.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Appointment(Base):
    """Customer appointments for a tenant."""

    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    customer_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    customer_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="scheduled",
        nullable=False,
        index=True
    )
    reminder_before_minutes: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False
    )
    reminder_before_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    reminder_after_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime,
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
