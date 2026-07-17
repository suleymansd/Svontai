"""Public sales and concierge inquiries."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class SalesInquiry(Base):
    __tablename__ = "sales_inquiries"
    __table_args__ = (
        Index("ix_sales_inquiries_status_created", "status", "created_at"),
        Index("ix_sales_inquiries_email_created", "email", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    plan: Mapped[str | None] = mapped_column(String(30), nullable=True)
    interval: Mapped[str | None] = mapped_column(String(20), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="contact_page")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new", index=True)
    email_delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )
