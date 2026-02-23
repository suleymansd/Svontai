"""Persisted tool output artifacts."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        Index("ix_artifacts_tenant_request", "tenant_id", "request_id"),
        Index("ix_artifacts_tenant_tool_created", "tenant_id", "tool_slug", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tool_slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(40), nullable=False, default="external")
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
