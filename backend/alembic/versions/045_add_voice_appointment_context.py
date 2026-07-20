"""Link AI-created appointments to their source voice call.

Revision ID: 045
Revises: 044
Create Date: 2026-07-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("appointments") as batch_op:
        batch_op.add_column(sa.Column("call_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_appointments_call_id",
            "calls",
            ["call_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_appointments_call_id", "appointments", ["call_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_appointments_call_id", table_name="appointments")
    with op.batch_alter_table("appointments") as batch_op:
        batch_op.drop_constraint("fk_appointments_call_id", type_="foreignkey")
        batch_op.drop_column("call_id")
