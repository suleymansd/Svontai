"""Add primary assistant identity to bots.

Revision ID: 043
Revises: 042
Create Date: 2026-07-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bots") as batch_op:
        batch_op.add_column(
            sa.Column("assistant_type", sa.String(length=20), nullable=False, server_default="specialist")
        )
        batch_op.add_column(sa.Column("specialist_key", sa.String(length=80), nullable=True))

    op.execute(
        """
        UPDATE bots
        SET assistant_type = 'primary', specialist_key = NULL
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY tenant_id ORDER BY created_at ASC, id ASC) AS row_num
                FROM bots
            ) ranked
            WHERE row_num = 1
        )
        """
    )
    op.execute(
        "UPDATE bots SET specialist_key = 'legacy_custom' WHERE assistant_type = 'specialist' AND specialist_key IS NULL"
    )
    op.create_index("ix_bots_assistant_type", "bots", ["assistant_type"], unique=False)
    op.create_index("ix_bots_specialist_key", "bots", ["specialist_key"], unique=False)
    op.create_index(
        "uq_bots_primary_per_tenant",
        "bots",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("assistant_type = 'primary'"),
        sqlite_where=sa.text("assistant_type = 'primary'"),
    )


def downgrade() -> None:
    op.drop_index("uq_bots_primary_per_tenant", table_name="bots")
    op.drop_index("ix_bots_specialist_key", table_name="bots")
    op.drop_index("ix_bots_assistant_type", table_name="bots")
    with op.batch_alter_table("bots") as batch_op:
        batch_op.drop_column("specialist_key")
        batch_op.drop_column("assistant_type")
