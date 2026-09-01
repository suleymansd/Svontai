"""Add contact AI policy and outbound reply idempotency.

Revision ID: 055
Revises: 054
Create Date: 2026-09-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "ai_reply_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="Whether automated AI and workflow replies may be sent to this contact",
        ),
    )
    op.add_column(
        "messages",
        sa.Column(
            "automation_run_id",
            sa.String(length=36),
            nullable=True,
            comment="n8n automation run that produced this outbound message",
        ),
    )
    op.add_column(
        "messages",
        sa.Column(
            "automation_delivery_key",
            sa.String(length=80),
            nullable=True,
            comment="Unique run and delivery-kind key for exactly-once automated sends",
        ),
    )
    op.add_column(
        "messages",
        sa.Column(
            "reply_to_external_id",
            sa.String(length=255),
            nullable=True,
            comment="Inbound provider message ID answered by this outbound message",
        ),
    )
    op.create_index(
        "ix_messages_automation_run_id",
        "messages",
        ["automation_run_id"],
        unique=False,
    )
    op.create_index(
        "uq_messages_automation_delivery_key",
        "messages",
        ["automation_delivery_key"],
        unique=True,
    )
    op.create_index(
        "uq_messages_conversation_reply_to_external_id",
        "messages",
        ["conversation_id", "reply_to_external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_messages_conversation_reply_to_external_id", table_name="messages")
    op.drop_index("uq_messages_automation_delivery_key", table_name="messages")
    op.drop_index("ix_messages_automation_run_id", table_name="messages")
    op.drop_column("messages", "reply_to_external_id")
    op.drop_column("messages", "automation_delivery_key")
    op.drop_column("messages", "automation_run_id")
    op.drop_column("conversations", "ai_reply_enabled")
