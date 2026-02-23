"""Add tool engine tables and marketplace fields

Revision ID: 027
Revises: 026
Create Date: 2026-02-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tools", sa.Column("slug", sa.String(length=120), nullable=True))
    op.add_column("tools", sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tools", sa.Column("input_schema_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("tools", sa.Column("output_schema_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("tools", sa.Column("required_integrations_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("tools", sa.Column("n8n_workflow_id", sa.String(length=255), nullable=True))

    op.execute('UPDATE tools SET slug = "key" WHERE slug IS NULL')
    op.create_index("ix_tools_slug", "tools", ["slug"], unique=True)

    op.create_table(
        "tenant_tools",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_slug", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_tools_tenant_id", "tenant_tools", ["tenant_id"])
    op.create_index("ix_tenant_tools_tool_slug", "tenant_tools", ["tool_slug"])
    op.create_index(
        "ix_tenant_tools_tenant_tool_slug_unique",
        "tenant_tools",
        ["tenant_id", "tool_slug"],
        unique=True,
    )

    op.create_table(
        "tool_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("n8n_execution_id", sa.String(length=120), nullable=True),
        sa.Column("tool_input_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("output_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column("usage_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("artifacts_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("context_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tool_runs_request_id", "tool_runs", ["request_id"], unique=False)
    op.create_index("ix_tool_runs_correlation_id", "tool_runs", ["correlation_id"])
    op.create_index("ix_tool_runs_tenant_id", "tool_runs", ["tenant_id"])
    op.create_index("ix_tool_runs_user_id", "tool_runs", ["user_id"])
    op.create_index("ix_tool_runs_tool_slug", "tool_runs", ["tool_slug"])
    op.create_index("ix_tool_runs_status", "tool_runs", ["status"])
    op.create_index("ix_tool_runs_n8n_execution_id", "tool_runs", ["n8n_execution_id"])
    op.create_index(
        "ix_tool_runs_tenant_tool_created",
        "tool_runs",
        ["tenant_id", "tool_slug", "created_at"],
    )
    op.create_index(
        "ix_tool_runs_tenant_request_id_unique",
        "tool_runs",
        ["tenant_id", "request_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_tool_runs_tenant_request_id_unique", table_name="tool_runs")
    op.drop_index("ix_tool_runs_tenant_tool_created", table_name="tool_runs")
    op.drop_index("ix_tool_runs_n8n_execution_id", table_name="tool_runs")
    op.drop_index("ix_tool_runs_status", table_name="tool_runs")
    op.drop_index("ix_tool_runs_tool_slug", table_name="tool_runs")
    op.drop_index("ix_tool_runs_user_id", table_name="tool_runs")
    op.drop_index("ix_tool_runs_tenant_id", table_name="tool_runs")
    op.drop_index("ix_tool_runs_correlation_id", table_name="tool_runs")
    op.drop_index("ix_tool_runs_request_id", table_name="tool_runs")
    op.drop_table("tool_runs")

    op.drop_index("ix_tenant_tools_tenant_tool_slug_unique", table_name="tenant_tools")
    op.drop_index("ix_tenant_tools_tool_slug", table_name="tenant_tools")
    op.drop_index("ix_tenant_tools_tenant_id", table_name="tenant_tools")
    op.drop_table("tenant_tools")

    op.drop_index("ix_tools_slug", table_name="tools")
    op.drop_column("tools", "n8n_workflow_id")
    op.drop_column("tools", "required_integrations_json")
    op.drop_column("tools", "output_schema_json")
    op.drop_column("tools", "input_schema_json")
    op.drop_column("tools", "is_premium")
    op.drop_column("tools", "slug")
