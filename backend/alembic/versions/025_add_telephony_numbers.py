"""Add telephony_numbers table

Revision ID: 025
Revises: 024
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telephony_numbers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default="twilio"),
        sa.Column("phone_number", sa.String(60), nullable=False),
        sa.Column("label", sa.String(140), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_telephony_numbers_tenant_id", "telephony_numbers", ["tenant_id"])
    op.create_index("ix_telephony_numbers_phone", "telephony_numbers", ["phone_number"])
    op.create_index("ix_telephony_numbers_tenant_phone", "telephony_numbers", ["tenant_id", "phone_number"], unique=True)
    op.create_index("ix_telephony_numbers_phone_active", "telephony_numbers", ["phone_number", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_telephony_numbers_phone_active", table_name="telephony_numbers")
    op.drop_index("ix_telephony_numbers_tenant_phone", table_name="telephony_numbers")
    op.drop_index("ix_telephony_numbers_phone", table_name="telephony_numbers")
    op.drop_index("ix_telephony_numbers_tenant_id", table_name="telephony_numbers")
    op.drop_table("telephony_numbers")

