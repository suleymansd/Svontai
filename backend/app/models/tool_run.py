"""Execution log for tool runs."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ToolRun(Base):
    __tablename__ = "tool_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_id", name="uq_tool_runs_tenant_request"),
        Index("ix_tool_runs_tenant_tool_created", "tenant_id", "tool_slug", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

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
    tool_slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)
    n8n_execution_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    tool_input_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    usage_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    artifacts_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
