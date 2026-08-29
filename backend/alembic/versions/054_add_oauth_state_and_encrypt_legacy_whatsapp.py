"""Add single-use OAuth state and encrypt legacy WhatsApp credentials.

Revision ID: 054
Revises: 053
Create Date: 2026-08-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_oauth_states_provider", "oauth_states", ["provider"])
    op.create_index("ix_oauth_states_state_hash", "oauth_states", ["state_hash"], unique=True)
    op.create_index("ix_oauth_states_tenant_id", "oauth_states", ["tenant_id"])
    op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"])
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])

    op.alter_column(
        "whatsapp_integrations",
        "webhook_verify_token",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=False,
    )

    # The legacy columns are retained for backward-compatible schema rollout,
    # but values are converted to Fernet ciphertext before the new code reads them.
    bind = op.get_bind()
    rows = list(bind.execute(
        sa.text("SELECT id, access_token, webhook_verify_token FROM whatsapp_integrations")
    ).mappings())
    from app.core.encryption import encrypt_token

    for row in rows:
        access_token = str(row["access_token"] or "")
        verify_token = str(row["webhook_verify_token"] or "")
        encrypted_access = access_token if access_token.startswith("gAAAAA") else encrypt_token(access_token)
        encrypted_verify = verify_token if verify_token.startswith("gAAAAA") else encrypt_token(verify_token)
        bind.execute(
            sa.text(
                """
                UPDATE whatsapp_integrations
                SET access_token = :access_token,
                    webhook_verify_token = :verify_token
                WHERE id = :id
                """
            ),
            {"id": row["id"], "access_token": encrypted_access, "verify_token": encrypted_verify},
        )


def downgrade() -> None:
    # Credentials deliberately remain encrypted during downgrade.
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_index("ix_oauth_states_user_id", table_name="oauth_states")
    op.drop_index("ix_oauth_states_tenant_id", table_name="oauth_states")
    op.drop_index("ix_oauth_states_state_hash", table_name="oauth_states")
    op.drop_index("ix_oauth_states_provider", table_name="oauth_states")
    op.drop_table("oauth_states")
