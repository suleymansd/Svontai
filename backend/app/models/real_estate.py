"""
Real Estate Pack models for industry-specific automation.
"""

import uuid
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RealEstatePackSettings(Base):
    __tablename__ = "real_estate_pack_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    persona: Mapped[str] = mapped_column(String(20), default="pro", nullable=False)

    lead_limit_monthly: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    pdf_limit_monthly: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    followup_limit_monthly: Mapped[int] = mapped_column(Integer, default=600, nullable=False)

    followup_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    followup_attempts: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    question_flow_buyer: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    question_flow_seller: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    listings_source: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    manual_availability: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    google_calendar_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    google_calendar_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    report_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    report_brand_color: Mapped[str] = mapped_column(String(20), default="#6D28D9", nullable=False)
    report_footer: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RealEstateGoogleCalendarIntegration(Base):
    __tablename__ = "real_estate_google_calendar_integrations"
    __table_args__ = (
        Index("ix_re_gc_tenant_agent", "tenant_id", "agent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    calendar_id: Mapped[str] = mapped_column(String(255), default="primary", nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="inactive", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RealEstateListing(Base):
    __tablename__ = "real_estate_listings"
    __table_args__ = (
        Index("ix_re_listings_tenant_active", "tenant_id", "is_active"),
        Index("ix_re_listings_tenant_sale_rent", "tenant_id", "sale_rent"),
        Index("ix_re_listings_tenant_location", "tenant_id", "location_text"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sale_rent: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    property_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    location_text: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lat: Mapped[float | None] = mapped_column(nullable=True)
    lng: Mapped[float | None] = mapped_column(nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(6), default="TRY", nullable=False)
    m2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rooms: Mapped[str | None] = mapped_column(String(20), nullable=True)
    features: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    media: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RealEstateConversationState(Base):
    __tablename__ = "real_estate_conversation_states"
    __table_args__ = (
        Index("ix_re_conv_state_tenant_state", "tenant_id", "current_state"),
        Index("ix_re_conv_state_window", "window_open_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_state: Mapped[str] = mapped_column(String(40), default="welcome", nullable=False, index=True)
    intent: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False, index=True)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[float] = mapped_column(default=0.0, nullable=False)
    collected_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    pii_snapshot_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    window_open_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_customer_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_outbound_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RealEstateLeadListingEvent(Base):
    __tablename__ = "real_estate_lead_listing_events"
    __table_args__ = (
        Index("ix_re_lead_listing_event_tenant_lead", "tenant_id", "lead_id"),
        Index("ix_re_lead_listing_event_event", "event"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("real_estate_listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class RealEstateAppointment(Base):
    __tablename__ = "real_estate_appointments"
    __table_args__ = (
        Index("ix_re_appointments_tenant_start", "tenant_id", "start_at"),
        Index("ix_re_appointments_agent_start", "agent_id", "start_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("real_estate_listings.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False, index=True)
    calendar_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    calendar_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meeting_mode: Mapped[str] = mapped_column(String(20), default="in_person", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RealEstateFollowUpJob(Base):
    __tablename__ = "real_estate_followup_jobs"
    __table_args__ = (
        Index("ix_re_followup_tenant_schedule", "tenant_id", "scheduled_at"),
        Index("ix_re_followup_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RealEstateTemplateRegistry(Base):
    __tablename__ = "real_estate_template_registry"
    __table_args__ = (
        Index("ix_re_templates_tenant_name", "tenant_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="tr", nullable=False)
    meta_template_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    variables_schema: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    content_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RealEstateWeeklyReport(Base):
    __tablename__ = "real_estate_weekly_reports"
    __table_args__ = (
        Index("ix_re_reports_tenant_week", "tenant_id", "week_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
