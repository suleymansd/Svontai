"""Add artifacts table for tool output storage

Revision ID: 028
Revises: 027
Create Date: 2026-02-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("tool_slug", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("storage_provider", sa.String(length=40), nullable=False, server_default="external"),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_artifacts_tenant_id", "artifacts", ["tenant_id"])
    op.create_index("ix_artifacts_request_id", "artifacts", ["request_id"])
    op.create_index("ix_artifacts_tool_slug", "artifacts", ["tool_slug"])
    op.create_index("ix_artifacts_tenant_request", "artifacts", ["tenant_id", "request_id"])
    op.create_index(
        "ix_artifacts_tenant_tool_created",
        "artifacts",
        ["tenant_id", "tool_slug", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifacts_tenant_tool_created", table_name="artifacts")
    op.drop_index("ix_artifacts_tenant_request", table_name="artifacts")
    op.drop_index("ix_artifacts_tool_slug", table_name="artifacts")
    op.drop_index("ix_artifacts_request_id", table_name="artifacts")
    op.drop_index("ix_artifacts_tenant_id", table_name="artifacts")
    op.drop_table("artifacts")
