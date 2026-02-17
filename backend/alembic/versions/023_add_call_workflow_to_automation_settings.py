"""Add call_workflow_id to tenant_automation_settings

Revision ID: 023
Revises: 022
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column.get("name") == column_name for column in columns)


def upgrade() -> None:
    if not _has_column("tenant_automation_settings", "call_workflow_id"):
        op.add_column("tenant_automation_settings", sa.Column("call_workflow_id", sa.String(255), nullable=True))


def downgrade() -> None:
    # Safe downgrade
    if _has_column("tenant_automation_settings", "call_workflow_id"):
        op.drop_column("tenant_automation_settings", "call_workflow_id")

