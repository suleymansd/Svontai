"""Add durable webhook inbox and message idempotency.

Revision ID: 049
Revises: 048
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the oldest copy before enforcing provider retry idempotency.
    op.execute(
        """
        DELETE FROM messages
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY conversation_id, external_id
                        ORDER BY created_at ASC, id ASC
                    ) AS duplicate_number
                FROM messages
                WHERE external_id IS NOT NULL
            ) AS duplicate_messages
            WHERE duplicate_number > 1
        )
        """
    )
    op.create_index(
        "uq_messages_conversation_external_id",
        "messages",
        ["conversation_id", "external_id"],
        unique=True,
    )

    op.create_table(
        "webhook_inbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("deduplication_key", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_owner", sa.String(length=128), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "deduplication_key", name="uq_webhook_inbox_provider_dedup"),
    )
    op.create_index("ix_webhook_inbox_events_tenant_id", "webhook_inbox_events", ["tenant_id"])
    op.create_index(
        "ix_webhook_inbox_claim",
        "webhook_inbox_events",
        ["status", "available_at", "locked_until"],
    )


def downgrade() -> None:
    op.drop_table("webhook_inbox_events")
    op.drop_index("uq_messages_conversation_external_id", table_name="messages")
