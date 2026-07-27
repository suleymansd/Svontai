"""Complete voice automation controls and consent ledger.

Revision ID: 048
Revises: 047
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant_voice_settings",
        sa.Column("transfer_number", sa.String(length=60), nullable=True),
    )
    op.create_table(
        "voice_contact_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("phone_number", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="allowed"),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="customer_message"),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("consent_at", sa.DateTime(), nullable=True),
        sa.Column("opted_out_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "phone_number",
            name="uq_voice_contact_policy_tenant_phone",
        ),
    )
    op.create_index(
        "ix_voice_contact_policies_tenant_id",
        "voice_contact_policies",
        ["tenant_id"],
    )
    op.create_index(
        "ix_voice_contact_policies_tenant_status",
        "voice_contact_policies",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("voice_contact_policies")
    op.drop_column("tenant_voice_settings", "transfer_number")
