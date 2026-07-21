"""Admin-created proforma invoices for manual billing."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_status_issue_date", "status", "issue_date"),
        Index("ix_invoices_customer_created", "customer_name", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(20), nullable=False, default="proforma")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")

    seller_name: Mapped[str] = mapped_column(String(180), nullable=False)
    seller_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seller_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    seller_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_tax_office: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seller_tax_number: Mapped[str | None] = mapped_column(String(40), nullable=True)

    customer_name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_tax_office: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_tax_number: Mapped[str | None] = mapped_column(String(40), nullable=True)

    items_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )
