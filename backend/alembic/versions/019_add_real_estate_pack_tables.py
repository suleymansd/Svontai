"""Add Real Estate Pack tables

Revision ID: 019
Revises: 018
Create Date: 2026-02-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("external_id", sa.String(255), nullable=True))
    op.create_index("ix_messages_external_id", "messages", ["external_id"])

    op.create_table(
        "real_estate_pack_settings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("persona", sa.String(length=20), nullable=False, server_default="pro"),
        sa.Column("lead_limit_monthly", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("pdf_limit_monthly", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("followup_limit_monthly", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("followup_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("followup_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("question_flow_buyer", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("question_flow_seller", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("listings_source", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("manual_availability", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("google_calendar_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("google_calendar_email", sa.String(length=255), nullable=True),
        sa.Column("report_logo_url", sa.String(length=500), nullable=True),
        sa.Column("report_brand_color", sa.String(length=20), nullable=False, server_default="#6D28D9"),
        sa.Column("report_footer", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_real_estate_pack_settings_tenant_id", "real_estate_pack_settings", ["tenant_id"])

    op.create_table(
        "real_estate_google_calendar_integrations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=False, server_default="primary"),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="inactive"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_real_estate_google_calendar_integrations_tenant_id", "real_estate_google_calendar_integrations", ["tenant_id"])
    op.create_index("ix_real_estate_google_calendar_integrations_agent_id", "real_estate_google_calendar_integrations", ["agent_id"])
    op.create_index("ix_re_gc_tenant_agent", "real_estate_google_calendar_integrations", ["tenant_id", "agent_id"])

    op.create_table(
        "real_estate_listings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sale_rent", sa.String(length=20), nullable=False),
        sa.Column("property_type", sa.String(length=30), nullable=False),
        sa.Column("location_text", sa.String(length=255), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=6), nullable=False, server_default="TRY"),
        sa.Column("m2", sa.Integer(), nullable=True),
        sa.Column("rooms", sa.String(length=20), nullable=True),
        sa.Column("features", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("media", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_real_estate_listings_tenant_id", "real_estate_listings", ["tenant_id"])
    op.create_index("ix_real_estate_listings_created_by", "real_estate_listings", ["created_by"])
    op.create_index("ix_real_estate_listings_sale_rent", "real_estate_listings", ["sale_rent"])
    op.create_index("ix_real_estate_listings_property_type", "real_estate_listings", ["property_type"])
    op.create_index("ix_real_estate_listings_location_text", "real_estate_listings", ["location_text"])
    op.create_index("ix_real_estate_listings_price", "real_estate_listings", ["price"])
    op.create_index("ix_re_listings_tenant_active", "real_estate_listings", ["tenant_id", "is_active"])
    op.create_index("ix_re_listings_tenant_sale_rent", "real_estate_listings", ["tenant_id", "sale_rent"])
    op.create_index("ix_re_listings_tenant_location", "real_estate_listings", ["tenant_id", "location_text"])

    op.create_table(
        "real_estate_conversation_states",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("current_state", sa.String(length=40), nullable=False, server_default="welcome"),
        sa.Column("intent", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("opted_out", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("collected_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("pii_snapshot_encrypted", sa.Text(), nullable=True),
        sa.Column("window_open_until", sa.DateTime(), nullable=True),
        sa.Column("last_customer_message_at", sa.DateTime(), nullable=True),
        sa.Column("last_outbound_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_real_estate_conversation_states_tenant_id", "real_estate_conversation_states", ["tenant_id"])
    op.create_index("ix_real_estate_conversation_states_lead_id", "real_estate_conversation_states", ["lead_id"])
    op.create_index("ix_real_estate_conversation_states_current_state", "real_estate_conversation_states", ["current_state"])
    op.create_index("ix_real_estate_conversation_states_intent", "real_estate_conversation_states", ["intent"])
    op.create_index("ix_re_conv_state_tenant_state", "real_estate_conversation_states", ["tenant_id", "current_state"])
    op.create_index("ix_re_conv_state_window", "real_estate_conversation_states", ["window_open_until"])

    op.create_table(
        "real_estate_lead_listing_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_id", sa.UUID(), sa.ForeignKey("real_estate_listings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event", sa.String(length=30), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_real_estate_lead_listing_events_tenant_id", "real_estate_lead_listing_events", ["tenant_id"])
    op.create_index("ix_real_estate_lead_listing_events_lead_id", "real_estate_lead_listing_events", ["lead_id"])
    op.create_index("ix_real_estate_lead_listing_events_listing_id", "real_estate_lead_listing_events", ["listing_id"])
    op.create_index("ix_real_estate_lead_listing_events_event", "real_estate_lead_listing_events", ["event"])
    op.create_index("ix_real_estate_lead_listing_events_created_at", "real_estate_lead_listing_events", ["created_at"])
    op.create_index("ix_re_lead_listing_event_tenant_lead", "real_estate_lead_listing_events", ["tenant_id", "lead_id"])
    op.create_index("ix_re_lead_listing_event_event", "real_estate_lead_listing_events", ["event"])

    op.create_table(
        "real_estate_appointments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("listing_id", sa.UUID(), sa.ForeignKey("real_estate_listings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled"),
        sa.Column("calendar_provider", sa.String(length=30), nullable=True),
        sa.Column("calendar_event_id", sa.String(length=255), nullable=True),
        sa.Column("meeting_mode", sa.String(length=20), nullable=False, server_default="in_person"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reminder_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_real_estate_appointments_tenant_id", "real_estate_appointments", ["tenant_id"])
    op.create_index("ix_real_estate_appointments_lead_id", "real_estate_appointments", ["lead_id"])
    op.create_index("ix_real_estate_appointments_agent_id", "real_estate_appointments", ["agent_id"])
    op.create_index("ix_real_estate_appointments_start_at", "real_estate_appointments", ["start_at"])
    op.create_index("ix_real_estate_appointments_status", "real_estate_appointments", ["status"])
    op.create_index("ix_re_appointments_tenant_start", "real_estate_appointments", ["tenant_id", "start_at"])
    op.create_index("ix_re_appointments_agent_start", "real_estate_appointments", ["agent_id", "start_at"])

    op.create_table(
        "real_estate_followup_jobs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("template_name", sa.String(length=120), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_real_estate_followup_jobs_tenant_id", "real_estate_followup_jobs", ["tenant_id"])
    op.create_index("ix_real_estate_followup_jobs_lead_id", "real_estate_followup_jobs", ["lead_id"])
    op.create_index("ix_real_estate_followup_jobs_conversation_id", "real_estate_followup_jobs", ["conversation_id"])
    op.create_index("ix_real_estate_followup_jobs_scheduled_at", "real_estate_followup_jobs", ["scheduled_at"])
    op.create_index("ix_real_estate_followup_jobs_status", "real_estate_followup_jobs", ["status"])
    op.create_index("ix_re_followup_tenant_schedule", "real_estate_followup_jobs", ["tenant_id", "scheduled_at"])
    op.create_index("ix_re_followup_status", "real_estate_followup_jobs", ["status"])

    op.create_table(
        "real_estate_template_registry",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False, server_default="tr"),
        sa.Column("meta_template_id", sa.String(length=120), nullable=True),
        sa.Column("variables_schema", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("content_preview", sa.Text(), nullable=True),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_real_estate_template_registry_tenant_id", "real_estate_template_registry", ["tenant_id"])
    op.create_index("ix_re_templates_tenant_name", "real_estate_template_registry", ["tenant_id", "name"])

    op.create_table(
        "real_estate_weekly_reports",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("pdf_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_real_estate_weekly_reports_tenant_id", "real_estate_weekly_reports", ["tenant_id"])
    op.create_index("ix_real_estate_weekly_reports_week_start", "real_estate_weekly_reports", ["week_start"])
    op.create_index("ix_re_reports_tenant_week", "real_estate_weekly_reports", ["tenant_id", "week_start"])


def downgrade() -> None:
    op.drop_index("ix_re_reports_tenant_week", table_name="real_estate_weekly_reports")
    op.drop_index("ix_real_estate_weekly_reports_week_start", table_name="real_estate_weekly_reports")
    op.drop_index("ix_real_estate_weekly_reports_tenant_id", table_name="real_estate_weekly_reports")
    op.drop_table("real_estate_weekly_reports")

    op.drop_index("ix_re_templates_tenant_name", table_name="real_estate_template_registry")
    op.drop_index("ix_real_estate_template_registry_tenant_id", table_name="real_estate_template_registry")
    op.drop_table("real_estate_template_registry")

    op.drop_index("ix_re_followup_status", table_name="real_estate_followup_jobs")
    op.drop_index("ix_re_followup_tenant_schedule", table_name="real_estate_followup_jobs")
    op.drop_index("ix_real_estate_followup_jobs_status", table_name="real_estate_followup_jobs")
    op.drop_index("ix_real_estate_followup_jobs_scheduled_at", table_name="real_estate_followup_jobs")
    op.drop_index("ix_real_estate_followup_jobs_conversation_id", table_name="real_estate_followup_jobs")
    op.drop_index("ix_real_estate_followup_jobs_lead_id", table_name="real_estate_followup_jobs")
    op.drop_index("ix_real_estate_followup_jobs_tenant_id", table_name="real_estate_followup_jobs")
    op.drop_table("real_estate_followup_jobs")

    op.drop_index("ix_re_appointments_agent_start", table_name="real_estate_appointments")
    op.drop_index("ix_re_appointments_tenant_start", table_name="real_estate_appointments")
    op.drop_index("ix_real_estate_appointments_status", table_name="real_estate_appointments")
    op.drop_index("ix_real_estate_appointments_start_at", table_name="real_estate_appointments")
    op.drop_index("ix_real_estate_appointments_agent_id", table_name="real_estate_appointments")
    op.drop_index("ix_real_estate_appointments_lead_id", table_name="real_estate_appointments")
    op.drop_index("ix_real_estate_appointments_tenant_id", table_name="real_estate_appointments")
    op.drop_table("real_estate_appointments")

    op.drop_index("ix_re_lead_listing_event_event", table_name="real_estate_lead_listing_events")
    op.drop_index("ix_re_lead_listing_event_tenant_lead", table_name="real_estate_lead_listing_events")
    op.drop_index("ix_real_estate_lead_listing_events_created_at", table_name="real_estate_lead_listing_events")
    op.drop_index("ix_real_estate_lead_listing_events_event", table_name="real_estate_lead_listing_events")
    op.drop_index("ix_real_estate_lead_listing_events_listing_id", table_name="real_estate_lead_listing_events")
    op.drop_index("ix_real_estate_lead_listing_events_lead_id", table_name="real_estate_lead_listing_events")
    op.drop_index("ix_real_estate_lead_listing_events_tenant_id", table_name="real_estate_lead_listing_events")
    op.drop_table("real_estate_lead_listing_events")

    op.drop_index("ix_re_conv_state_window", table_name="real_estate_conversation_states")
    op.drop_index("ix_re_conv_state_tenant_state", table_name="real_estate_conversation_states")
    op.drop_index("ix_real_estate_conversation_states_intent", table_name="real_estate_conversation_states")
    op.drop_index("ix_real_estate_conversation_states_current_state", table_name="real_estate_conversation_states")
    op.drop_index("ix_real_estate_conversation_states_lead_id", table_name="real_estate_conversation_states")
    op.drop_index("ix_real_estate_conversation_states_tenant_id", table_name="real_estate_conversation_states")
    op.drop_table("real_estate_conversation_states")

    op.drop_index("ix_re_listings_tenant_location", table_name="real_estate_listings")
    op.drop_index("ix_re_listings_tenant_sale_rent", table_name="real_estate_listings")
    op.drop_index("ix_re_listings_tenant_active", table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listings_price", table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listings_location_text", table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listings_property_type", table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listings_sale_rent", table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listings_created_by", table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listings_tenant_id", table_name="real_estate_listings")
    op.drop_table("real_estate_listings")

    op.drop_index("ix_re_gc_tenant_agent", table_name="real_estate_google_calendar_integrations")
    op.drop_index("ix_real_estate_google_calendar_integrations_agent_id", table_name="real_estate_google_calendar_integrations")
    op.drop_index("ix_real_estate_google_calendar_integrations_tenant_id", table_name="real_estate_google_calendar_integrations")
    op.drop_table("real_estate_google_calendar_integrations")

    op.drop_index("ix_real_estate_pack_settings_tenant_id", table_name="real_estate_pack_settings")
    op.drop_table("real_estate_pack_settings")

    op.drop_index("ix_messages_external_id", table_name="messages")
    op.drop_column("messages", "external_id")
