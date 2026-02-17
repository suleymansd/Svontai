"""
Call models for Voice AI Agent.

This is the system-of-record for phone calls (inbound/outbound) regardless of provider.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CallDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CANCELLED = "cancelled"


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_tenant_started", "tenant_id", "started_at"),
        Index("ix_calls_tenant_provider", "tenant_id", "provider", "provider_call_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_call_id: Mapped[str] = mapped_column(String(255), nullable=False)

    direction: Mapped[str] = mapped_column(String(20), nullable=False, default=CallDirection.INBOUND.value)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=CallStatus.STARTED.value)

    from_number: Mapped[str] = mapped_column(String(60), nullable=False)
    to_number: Mapped[str] = mapped_column(String(60), nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    lead: Mapped["Lead | None"] = relationship("Lead")
    transcripts: Mapped[list["CallTranscript"]] = relationship(
        "CallTranscript",
        back_populates="call",
        cascade="all, delete-orphan",
        order_by="CallTranscript.segment_index",
    )
    summary: Mapped["CallSummary | None"] = relationship(
        "CallSummary",
        back_populates="call",
        uselist=False,
        cascade="all, delete-orphan",
    )


class CallTranscript(Base):
    __tablename__ = "call_transcripts"
    __table_args__ = (
        Index("ix_call_transcripts_call_segment", "call_id", "segment_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    segment_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    speaker: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")  # user|agent|system
    text: Mapped[str] = mapped_column(Text, nullable=False)
    ts_iso: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    call: Mapped["Call"] = relationship("Call", back_populates="transcripts")


class CallSummary(Base):
    __tablename__ = "call_summaries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    intent: Mapped[str | None] = mapped_column(String(80), nullable=True)
    labels_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    action_items_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    call: Mapped["Call"] = relationship("Call", back_populates="summary")

