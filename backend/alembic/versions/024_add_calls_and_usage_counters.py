"""Add calls and tenant_usage_counters tables

Revision ID: 024
Revises: 023
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calls",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_call_id", sa.String(255), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False, server_default="inbound"),
        sa.Column("status", sa.String(30), nullable=False, server_default="started"),
        sa.Column("from_number", sa.String(60), nullable=False),
        sa.Column("to_number", sa.String(60), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(12, 4), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_calls_tenant_id", "calls", ["tenant_id"])
    op.create_index("ix_calls_lead_id", "calls", ["lead_id"])
    op.create_index("ix_calls_tenant_started", "calls", ["tenant_id", "started_at"])
    op.create_index("ix_calls_tenant_provider", "calls", ["tenant_id", "provider", "provider_call_id"])
    op.create_index(
        "ix_calls_tenant_provider_unique",
        "calls",
        ["tenant_id", "provider", "provider_call_id"],
        unique=True,
    )

    op.create_table(
        "call_transcripts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_id", sa.UUID(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("speaker", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("ts_iso", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_call_transcripts_tenant_id", "call_transcripts", ["tenant_id"])
    op.create_index("ix_call_transcripts_call_id", "call_transcripts", ["call_id"])
    op.create_index("ix_call_transcripts_call_segment", "call_transcripts", ["call_id", "segment_index"])

    op.create_table(
        "call_summaries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_id", sa.UUID(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("intent", sa.String(80), nullable=True),
        sa.Column("labels_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("action_items_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_call_summaries_tenant_id", "call_summaries", ["tenant_id"])
    op.create_index("ix_call_summaries_call_id", "call_summaries", ["call_id"], unique=True)

    op.create_table(
        "tenant_usage_counters",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_key", sa.String(7), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voice_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("workflow_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outbound_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extra_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_usage_counters_tenant_id", "tenant_usage_counters", ["tenant_id"])
    op.create_index("ix_tenant_usage_counters_tenant_period", "tenant_usage_counters", ["tenant_id", "period_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenant_usage_counters_tenant_period", table_name="tenant_usage_counters")
    op.drop_index("ix_tenant_usage_counters_tenant_id", table_name="tenant_usage_counters")
    op.drop_table("tenant_usage_counters")

    op.drop_index("ix_call_summaries_call_id", table_name="call_summaries")
    op.drop_index("ix_call_summaries_tenant_id", table_name="call_summaries")
    op.drop_table("call_summaries")

    op.drop_index("ix_call_transcripts_call_segment", table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_call_id", table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_tenant_id", table_name="call_transcripts")
    op.drop_table("call_transcripts")

    op.drop_index("ix_calls_tenant_provider_unique", table_name="calls")
    op.drop_index("ix_calls_tenant_provider", table_name="calls")
    op.drop_index("ix_calls_tenant_started", table_name="calls")
    op.drop_index("ix_calls_lead_id", table_name="calls")
    op.drop_index("ix_calls_tenant_id", table_name="calls")
    op.drop_table("calls")

