"""Add tenant assistant media library.

Revision ID: 044
Revises: 043
Create Date: 2026-07-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id"),
    )
    op.create_index("ix_assistant_media_assets_tenant_id", "assistant_media_assets", ["tenant_id"])
    op.create_index("ix_assistant_media_assets_artifact_id", "assistant_media_assets", ["artifact_id"], unique=True)
    op.create_index("ix_assistant_media_assets_created_by", "assistant_media_assets", ["created_by"])
    op.create_index("ix_assistant_media_assets_is_active", "assistant_media_assets", ["is_active"])
    op.create_index("ix_assistant_media_tenant_active", "assistant_media_assets", ["tenant_id", "is_active"])
    op.create_index("ix_assistant_media_tenant_type", "assistant_media_assets", ["tenant_id", "media_type"])


def downgrade() -> None:
    op.drop_table("assistant_media_assets")
