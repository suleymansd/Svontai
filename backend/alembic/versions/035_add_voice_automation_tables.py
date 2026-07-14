"""add voice automation tables

Revision ID: 035_add_voice_automation_tables
Revises: 034
Create Date: 2026-06-18 02:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "035_add_voice_automation_tables"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_voice_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="vapi"),
        sa.Column("from_number", sa.String(length=60), nullable=True),
        sa.Column("allow_appointment_booking", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_explicit_call_request", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("business_hours_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("allowed_triggers_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("handoff_rules_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("max_attempts_per_lead", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="240"),
        sa.Column("daily_call_limit", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_voice_settings_tenant", "tenant_voice_settings", ["tenant_id"], unique=True)

    op.create_table(
        "call_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("customer_phone", sa.String(length=60), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("trigger", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_intents_tenant_status", "call_intents", ["tenant_id", "status"], unique=False)
    op.create_index("ix_call_intents_conversation", "call_intents", ["conversation_id"], unique=False)
    op.create_index("ix_call_intents_external_message", "call_intents", ["external_message_id"], unique=False)

    op.create_table(
        "outbound_call_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("call_intent_id", sa.Uuid(), nullable=True),
        sa.Column("call_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="vapi"),
        sa.Column("from_number", sa.String(length=60), nullable=False),
        sa.Column("to_number", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider_call_id", sa.String(length=255), nullable=True),
        sa.Column("request_payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("response_payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["call_intent_id"], ["call_intents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbound_call_jobs_tenant_status", "outbound_call_jobs", ["tenant_id", "status"], unique=False)
    op.create_index("ix_outbound_call_jobs_next_attempt", "outbound_call_jobs", ["next_attempt_at"], unique=False)
    op.create_index("ix_outbound_call_jobs_call_intent_id", "outbound_call_jobs", ["call_intent_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_outbound_call_jobs_call_intent_id", table_name="outbound_call_jobs")
    op.drop_index("ix_outbound_call_jobs_next_attempt", table_name="outbound_call_jobs")
    op.drop_index("ix_outbound_call_jobs_tenant_status", table_name="outbound_call_jobs")
    op.drop_table("outbound_call_jobs")

    op.drop_index("ix_call_intents_external_message", table_name="call_intents")
    op.drop_index("ix_call_intents_conversation", table_name="call_intents")
    op.drop_index("ix_call_intents_tenant_status", table_name="call_intents")
    op.drop_table("call_intents")

    op.drop_index("ix_tenant_voice_settings_tenant", table_name="tenant_voice_settings")
    op.drop_table("tenant_voice_settings")
