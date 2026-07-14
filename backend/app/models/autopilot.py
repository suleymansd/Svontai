"""Autopilot setup, integration health, and agency client models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class SetupRun(Base):
    """Records tenant-safe setup and repair runs."""

    __tablename__ = "setup_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    actions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    required_actions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationHealthCheck(Base):
    """Latest and historical provider diagnostics for a tenant."""

    __tablename__ = "integration_health_checks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_integration_health_tenant_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    health_score: Mapped[int] = mapped_column(default=0, nullable=False)
    message: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    checks_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    repairable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_user_action: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    action_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AgencyClient(Base):
    """Parent agency tenant to managed client tenant relationship."""

    __tablename__ = "agency_clients"
    __table_args__ = (
        UniqueConstraint("agency_tenant_id", "client_tenant_id", name="uq_agency_client_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agency_tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    client_tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ScheduledJob(Base):
    """Persistent worker job lock and retry state."""

    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="idle", nullable=False)
    lock_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
