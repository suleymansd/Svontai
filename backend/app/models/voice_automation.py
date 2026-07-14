"""Voice automation settings, intents, and outbound jobs."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class CallIntentStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SKIPPED = "skipped"
    COMPLETED = "completed"
    FAILED = "failed"


class OutboundCallJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TenantVoiceSettings(Base):
    """Tenant-level autonomous voice assistant controls."""

    __tablename__ = "tenant_voice_settings"
    __table_args__ = (
        Index("ix_tenant_voice_settings_tenant", "tenant_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="vapi")
    from_number: Mapped[str | None] = mapped_column(String(60), nullable=True)

    allow_appointment_booking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_explicit_call_request: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    business_hours_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    allowed_triggers_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    handoff_rules_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    max_attempts_per_lead: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=240)
    daily_call_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


class CallIntent(Base):
    """A decision to call a WhatsApp/customer contact."""

    __tablename__ = "call_intents"
    __table_args__ = (
        Index("ix_call_intents_tenant_status", "tenant_id", "status"),
        Index("ix_call_intents_conversation", "conversation_id"),
        Index("ix_call_intents_external_message", "external_message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bots.id", ondelete="SET NULL"), nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)

    customer_phone: Mapped[str] = mapped_column(String(60), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trigger: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=CallIntentStatus.PENDING.value)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


class OutboundCallJob(Base):
    """Worker-executable outbound call job."""

    __tablename__ = "outbound_call_jobs"
    __table_args__ = (
        Index("ix_outbound_call_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_outbound_call_jobs_next_attempt", "next_attempt_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_intent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("call_intents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calls.id", ondelete="SET NULL"), nullable=True)

    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="vapi")
    from_number: Mapped[str] = mapped_column(String(60), nullable=False)
    to_number: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=OutboundCallJobStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    response_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
