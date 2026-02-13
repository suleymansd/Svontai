"""Add conversation/message/lead indexes

Revision ID: 015
Revises: 014
Create Date: 2026-02-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_conversations_bot_updated",
        "conversations",
        ["bot_id", "updated_at"]
    )
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at"]
    )
    op.create_index(
        "ix_leads_bot_created",
        "leads",
        ["bot_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_leads_bot_created", table_name="leads")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_index("ix_conversations_bot_updated", table_name="conversations")
