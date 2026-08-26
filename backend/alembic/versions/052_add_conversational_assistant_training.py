"""Add persistent conversational assistant training sessions.

Revision ID: 052
Revises: 051
"""

from alembic import op
import sqlalchemy as sa


revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_training_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("messages_json", sa.JSON(), nullable=False),
        sa.Column("proposal_json", sa.JSON(), nullable=True),
        sa.Column("specialist_bot_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["specialist_bot_id"], ["bots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_training_sessions_tenant_id", "assistant_training_sessions", ["tenant_id"])
    op.create_index("ix_assistant_training_sessions_user_id", "assistant_training_sessions", ["user_id"])
    op.create_index("ix_assistant_training_sessions_status", "assistant_training_sessions", ["status"])
    op.create_index(
        "ix_assistant_training_sessions_tenant_updated",
        "assistant_training_sessions",
        ["tenant_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_training_sessions_tenant_updated", table_name="assistant_training_sessions")
    op.drop_index("ix_assistant_training_sessions_status", table_name="assistant_training_sessions")
    op.drop_index("ix_assistant_training_sessions_user_id", table_name="assistant_training_sessions")
    op.drop_index("ix_assistant_training_sessions_tenant_id", table_name="assistant_training_sessions")
    op.drop_table("assistant_training_sessions")
