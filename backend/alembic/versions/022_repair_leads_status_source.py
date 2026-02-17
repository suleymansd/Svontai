"""Repair leads.status and leads.source columns

Revision ID: 022
Revises: 021
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column.get("name") == column_name for column in columns)


def upgrade() -> None:
    # Some environments may have an inconsistent schema even if alembic_version is advanced.
    # This migration hardens leads table to match current ORM expectations.
    if not _has_column("leads", "status"):
        op.add_column(
            "leads",
            sa.Column("status", sa.String(length=50), nullable=True, server_default="new"),
        )
        op.execute("UPDATE leads SET status = 'new' WHERE status IS NULL")
        op.alter_column("leads", "status", nullable=False, server_default="new")
    else:
        op.execute("UPDATE leads SET status = 'new' WHERE status IS NULL")

    if not _has_column("leads", "source"):
        op.add_column(
            "leads",
            sa.Column("source", sa.String(length=50), nullable=True, server_default="web"),
        )
        op.execute("UPDATE leads SET source = 'web' WHERE source IS NULL")
        op.alter_column("leads", "source", nullable=False, server_default="web")
    else:
        op.execute("UPDATE leads SET source = 'web' WHERE source IS NULL")


def downgrade() -> None:
    # No-op downgrade (safety migration)
    pass

