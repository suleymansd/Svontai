"""Add appointment duration and conversation context.

Revision ID: 042
Revises: 041
Create Date: 2026-07-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("appointments") as batch_op:
        batch_op.add_column(sa.Column("customer_phone", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("conversation_id", sa.UUID(), nullable=True))
        batch_op.add_column(
            sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60")
        )
        batch_op.add_column(
            sa.Column("source", sa.String(length=30), nullable=False, server_default="manual")
        )
        batch_op.create_foreign_key(
            "fk_appointments_conversation_id",
            "conversations",
            ["conversation_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_appointments_customer_phone", "appointments", ["customer_phone"], unique=False)
    op.create_index("ix_appointments_conversation_id", "appointments", ["conversation_id"], unique=False)
    op.create_index("ix_appointments_source", "appointments", ["source"], unique=False)
    op.execute(
        """
        UPDATE bots
        SET welcome_message = 'Nasıl yardımcı olabilirim?'
        WHERE welcome_message LIKE 'Merhaba,%ile iletişime geçtiğiniz için teşekkür ederiz.%'
           OR welcome_message LIKE 'Merhaba,%ekibi adına size yardımcı olabilirim.%'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_source", table_name="appointments")
    op.drop_index("ix_appointments_conversation_id", table_name="appointments")
    op.drop_index("ix_appointments_customer_phone", table_name="appointments")
    with op.batch_alter_table("appointments") as batch_op:
        batch_op.drop_constraint("fk_appointments_conversation_id", type_="foreignkey")
        batch_op.drop_column("source")
        batch_op.drop_column("duration_minutes")
        batch_op.drop_column("conversation_id")
        batch_op.drop_column("customer_phone")
