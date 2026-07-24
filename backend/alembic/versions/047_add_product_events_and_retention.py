"""Add privacy-safe product analytics and tenant retention policies.

Revision ID: 047
Revises: 046
Create Date: 2026-07-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False, server_default="action"),
        sa.Column("path", sa.String(length=300), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("properties_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_events_tenant_id", "product_events", ["tenant_id"])
    op.create_index("ix_product_events_user_id", "product_events", ["user_id"])
    op.create_index("ix_product_events_name", "product_events", ["name"])
    op.create_index("ix_product_events_session_id", "product_events", ["session_id"])
    op.create_index(
        "ix_product_events_tenant_occurred",
        "product_events",
        ["tenant_id", "occurred_at"],
    )
    op.create_index(
        "ix_product_events_tenant_name_occurred",
        "product_events",
        ["tenant_id", "name", "occurred_at"],
    )
    op.create_index(
        "ix_product_events_session_occurred",
        "product_events",
        ["session_id", "occurred_at"],
    )

    op.create_table(
        "data_retention_policies",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("message_content_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("raw_payload_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("product_analytics_days", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("usage_log_days", sa.Integer(), nullable=False, server_default="730"),
        sa.Column("system_event_days", sa.Integer(), nullable=False, server_default="730"),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("data_retention_policies")
    op.drop_table("product_events")
