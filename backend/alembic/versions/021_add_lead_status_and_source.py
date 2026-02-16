"""Add status and source columns to leads

Revision ID: 021
Revises: 020
Create Date: 2026-02-16 16:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column.get("name") == column_name for column in columns)


def upgrade() -> None:
    if not _has_column("leads", "status"):
        op.add_column(
            "leads",
            sa.Column("status", sa.String(length=50), nullable=False, server_default="new"),
        )

    if not _has_column("leads", "source"):
        op.add_column(
            "leads",
            sa.Column("source", sa.String(length=50), nullable=False, server_default="web"),
        )


def downgrade() -> None:
    if _has_column("leads", "source"):
        op.drop_column("leads", "source")

    if _has_column("leads", "status"):
        op.drop_column("leads", "status")

