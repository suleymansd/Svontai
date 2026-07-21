"""Add admin-created proforma invoices.

Revision ID: 046
Revises: 045
Create Date: 2026-07-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("document_type", sa.String(length=20), nullable=False, server_default="proforma"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="TRY"),
        sa.Column("seller_name", sa.String(length=180), nullable=False),
        sa.Column("seller_email", sa.String(length=255), nullable=True),
        sa.Column("seller_phone", sa.String(length=40), nullable=True),
        sa.Column("seller_address", sa.Text(), nullable=True),
        sa.Column("seller_tax_office", sa.String(length=120), nullable=True),
        sa.Column("seller_tax_number", sa.String(length=40), nullable=True),
        sa.Column("customer_name", sa.String(length=180), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=40), nullable=True),
        sa.Column("customer_address", sa.Text(), nullable=True),
        sa.Column("customer_tax_office", sa.String(length=120), nullable=True),
        sa.Column("customer_tax_number", sa.String(length=40), nullable=True),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("tax_total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"], unique=False)
    op.create_index("ix_invoices_created_by_user_id", "invoices", ["created_by_user_id"], unique=False)
    op.create_index("ix_invoices_status", "invoices", ["status"], unique=False)
    op.create_index("ix_invoices_status_issue_date", "invoices", ["status", "issue_date"], unique=False)
    op.create_index("ix_invoices_customer_name", "invoices", ["customer_name"], unique=False)
    op.create_index("ix_invoices_customer_created", "invoices", ["customer_name", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("invoices")
