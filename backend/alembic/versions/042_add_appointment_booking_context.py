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
    op.add_column("appointments", sa.Column("customer_phone", sa.String(length=40), nullable=True))
    op.add_column("appointments", sa.Column("conversation_id", sa.UUID(), nullable=True))
    op.add_column(
        "appointments",
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
    )
    op.add_column(
        "appointments",
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
    )
    op.create_foreign_key(
        "fk_appointments_conversation_id",
        "appointments",
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
    op.drop_constraint("fk_appointments_conversation_id", "appointments", type_="foreignkey")
    op.drop_column("appointments", "source")
    op.drop_column("appointments", "duration_minutes")
    op.drop_column("appointments", "conversation_id")
    op.drop_column("appointments", "customer_phone")
