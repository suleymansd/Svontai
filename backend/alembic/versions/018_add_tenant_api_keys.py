"""Add tenant API keys

Revision ID: 018
Revises: 017
Create Date: 2026-02-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_api_keys",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("last4", sa.String(4), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key_hash", name="uq_tenant_api_keys_key_hash"),
    )

    op.create_index("ix_tenant_api_keys_tenant_id", "tenant_api_keys", ["tenant_id"])
    op.create_index("ix_tenant_api_keys_created_by", "tenant_api_keys", ["created_by"])
    op.create_index("ix_tenant_api_keys_revoked_at", "tenant_api_keys", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_tenant_api_keys_revoked_at", table_name="tenant_api_keys")
    op.drop_index("ix_tenant_api_keys_created_by", table_name="tenant_api_keys")
    op.drop_index("ix_tenant_api_keys_tenant_id", table_name="tenant_api_keys")
    op.drop_table("tenant_api_keys")

