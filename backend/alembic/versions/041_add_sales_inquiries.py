"""Add persisted public sales inquiries.

Revision ID: 041
Revises: 040
Create Date: 2026-07-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_inquiries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=180), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("plan", sa.String(length=30), nullable=True),
        sa.Column("interval", sa.String(length=20), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="contact_page"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="new"),
        sa.Column("email_delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_inquiries_email", "sales_inquiries", ["email"], unique=False)
    op.create_index("ix_sales_inquiries_status", "sales_inquiries", ["status"], unique=False)
    op.create_index(
        "ix_sales_inquiries_status_created",
        "sales_inquiries",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_sales_inquiries_email_created",
        "sales_inquiries",
        ["email", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sales_inquiries_email_created", table_name="sales_inquiries")
    op.drop_index("ix_sales_inquiries_status_created", table_name="sales_inquiries")
    op.drop_index("ix_sales_inquiries_status", table_name="sales_inquiries")
    op.drop_index("ix_sales_inquiries_email", table_name="sales_inquiries")
    op.drop_table("sales_inquiries")
