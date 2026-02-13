"""Add performance indexes

Revision ID: 013
Revises: 012
Create Date: 2026-02-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_automation_runs_tenant_created",
        "automation_runs",
        ["tenant_id", "created_at"]
    )
    op.create_index(
        "ix_system_events_tenant_created",
        "system_events",
        ["tenant_id", "created_at"]
    )
    op.create_index(
        "ix_tickets_tenant_last_activity",
        "tickets",
        ["tenant_id", "last_activity_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_tenant_last_activity", table_name="tickets")
    op.drop_index("ix_system_events_tenant_created", table_name="system_events")
    op.drop_index("ix_automation_runs_tenant_created", table_name="automation_runs")
