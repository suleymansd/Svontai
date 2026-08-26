"""Extend tenant retention to media, voice, tickets and artifacts.

Revision ID: 050
Revises: 049
"""

from alembic import op
import sqlalchemy as sa


revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "data_retention_policies",
        sa.Column("media_days", sa.Integer(), nullable=False, server_default="365"),
    )
    op.add_column(
        "data_retention_policies",
        sa.Column("call_data_days", sa.Integer(), nullable=False, server_default="365"),
    )
    op.add_column(
        "data_retention_policies",
        sa.Column("ticket_days", sa.Integer(), nullable=False, server_default="730"),
    )
    op.add_column(
        "data_retention_policies",
        sa.Column("artifact_days", sa.Integer(), nullable=False, server_default="180"),
    )


def downgrade() -> None:
    op.drop_column("data_retention_policies", "artifact_days")
    op.drop_column("data_retention_policies", "ticket_days")
    op.drop_column("data_retention_policies", "call_data_days")
    op.drop_column("data_retention_policies", "media_days")
