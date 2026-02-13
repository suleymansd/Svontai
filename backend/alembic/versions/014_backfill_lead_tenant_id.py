"""Backfill lead tenant_id from bots

Revision ID: 014
Revises: 013
Create Date: 2026-02-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(
            sa.Column(
                "tenant_id",
                sa.String(36),
                nullable=True
            )
        )
        batch_op.create_foreign_key(
            "fk_leads_tenant_id",
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE"
        )
        batch_op.create_index("ix_leads_tenant_id", ["tenant_id"])

    op.execute(
        """
        UPDATE leads
        SET tenant_id = bots.tenant_id
        FROM bots
        WHERE leads.bot_id = bots.id
          AND leads.tenant_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE leads
        SET tenant_id = NULL
        WHERE tenant_id IS NOT NULL
        """
    )

    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_constraint("fk_leads_tenant_id", type_="foreignkey")
        batch_op.drop_index("ix_leads_tenant_id")
        batch_op.drop_column("tenant_id")
