"""Add autopilot diagnostics and agency client tables

Revision ID: 034
Revises: 033
Create Date: 2026-06-17
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "setup_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("triggered_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("actions_json", sa.JSON(), nullable=False),
        sa.Column("required_actions_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_setup_runs_tenant_id"), "setup_runs", ["tenant_id"], unique=False)

    op.create_table(
        "integration_health_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False),
        sa.Column("repairable", sa.Boolean(), nullable=False),
        sa.Column("requires_user_action", sa.Boolean(), nullable=False),
        sa.Column("action_url", sa.String(length=255), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider", name="uq_integration_health_tenant_provider"),
    )
    op.create_index(op.f("ix_integration_health_checks_tenant_id"), "integration_health_checks", ["tenant_id"], unique=False)

    op.create_table(
        "agency_clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agency_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("client_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agency_tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_tenant_id", "client_tenant_id", name="uq_agency_client_pair"),
    )
    op.create_index(op.f("ix_agency_clients_agency_tenant_id"), "agency_clients", ["agency_tenant_id"], unique=False)
    op.create_index(op.f("ix_agency_clients_client_tenant_id"), "agency_clients", ["client_tenant_id"], unique=False)

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lock_owner", sa.String(length=128), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_scheduled_jobs_name"), "scheduled_jobs", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_scheduled_jobs_name"), table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")
    op.drop_index(op.f("ix_agency_clients_client_tenant_id"), table_name="agency_clients")
    op.drop_index(op.f("ix_agency_clients_agency_tenant_id"), table_name="agency_clients")
    op.drop_table("agency_clients")
    op.drop_index(op.f("ix_integration_health_checks_tenant_id"), table_name="integration_health_checks")
    op.drop_table("integration_health_checks")
    op.drop_index(op.f("ix_setup_runs_tenant_id"), table_name="setup_runs")
    op.drop_table("setup_runs")
