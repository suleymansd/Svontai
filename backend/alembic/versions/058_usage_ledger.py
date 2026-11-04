"""Idempotency ledger for usage counter increments (audit A09).

Revision ID: 058
Revises: 057
"""

from alembic import op
import sqlalchemy as sa

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("period_key", sa.String(7), nullable=False),
        sa.Column("amounts_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_usage_ledger_idempotency_key", "usage_ledger", ["idempotency_key"], unique=True)
    op.create_index("ix_usage_ledger_tenant_period", "usage_ledger", ["tenant_id", "period_key"])
    op.create_index("ix_usage_ledger_created_at", "usage_ledger", ["created_at"])


def downgrade():
    op.drop_index("ix_usage_ledger_created_at", table_name="usage_ledger")
    op.drop_index("ix_usage_ledger_tenant_period", table_name="usage_ledger")
    op.drop_index("ix_usage_ledger_idempotency_key", table_name="usage_ledger")
    op.drop_table("usage_ledger")
