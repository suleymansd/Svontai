"""Privacy-safe product usage events."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class ProductEvent(Base):
    """A tenant-scoped interaction event without message or form content."""

    __tablename__ = "product_events"
    __table_args__ = (
        Index("ix_product_events_tenant_occurred", "tenant_id", "occurred_at"),
        Index("ix_product_events_tenant_name_occurred", "tenant_id", "name", "occurred_at"),
        Index("ix_product_events_session_occurred", "session_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="action")
    path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    properties_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
