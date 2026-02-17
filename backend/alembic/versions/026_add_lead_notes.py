"""Add lead notes table

Revision ID: 026
Revises: 025
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_notes",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("call_id", sa.UUID(), sa.ForeignKey("calls.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(30), nullable=False, server_default="panel"),
        sa.Column("note_type", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("title", sa.String(140), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_lead_notes_tenant_id", "lead_notes", ["tenant_id"])
    op.create_index("ix_lead_notes_lead_id", "lead_notes", ["lead_id"])
    op.create_index("ix_lead_notes_call_id", "lead_notes", ["call_id"])
    op.create_index("ix_lead_notes_conversation_id", "lead_notes", ["conversation_id"])
    op.create_index("ix_lead_notes_created_by", "lead_notes", ["created_by"])
    op.create_index("ix_lead_notes_tenant_created", "lead_notes", ["tenant_id", "created_at"])
    op.create_index("ix_lead_notes_tenant_lead", "lead_notes", ["tenant_id", "lead_id"])
    op.create_index("ix_lead_notes_tenant_call", "lead_notes", ["tenant_id", "call_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_notes_tenant_call", table_name="lead_notes")
    op.drop_index("ix_lead_notes_tenant_lead", table_name="lead_notes")
    op.drop_index("ix_lead_notes_tenant_created", table_name="lead_notes")
    op.drop_index("ix_lead_notes_created_by", table_name="lead_notes")
    op.drop_index("ix_lead_notes_conversation_id", table_name="lead_notes")
    op.drop_index("ix_lead_notes_call_id", table_name="lead_notes")
    op.drop_index("ix_lead_notes_lead_id", table_name="lead_notes")
    op.drop_index("ix_lead_notes_tenant_id", table_name="lead_notes")
    op.drop_table("lead_notes")

