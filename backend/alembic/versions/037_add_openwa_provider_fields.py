"""Add provider-neutral WhatsApp account fields.

Revision ID: 037
Revises: 036
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("whatsapp_accounts") as batch_op:
        batch_op.add_column(
            sa.Column("provider", sa.String(length=30), nullable=False, server_default="meta_cloud")
        )
        batch_op.add_column(sa.Column("provider_session_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("provider_webhook_id", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("provider_metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch_op.add_column(sa.Column("last_error", sa.Text(), nullable=True))
        batch_op.create_index(
            "ix_whatsapp_accounts_provider_session_id",
            ["provider_session_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("whatsapp_accounts") as batch_op:
        batch_op.drop_index("ix_whatsapp_accounts_provider_session_id")
        batch_op.drop_column("last_error")
        batch_op.drop_column("provider_metadata_json")
        batch_op.drop_column("provider_webhook_id")
        batch_op.drop_column("provider_session_id")
        batch_op.drop_column("provider")
