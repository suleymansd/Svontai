"""Add correlation_id to automation_runs

Revision ID: 009
Revises: 008
Create Date: 2026-01-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('automation_runs', sa.Column('correlation_id', sa.String(100), nullable=True))
    op.create_index('ix_automation_runs_correlation_id', 'automation_runs', ['correlation_id'])


def downgrade() -> None:
    op.drop_index('ix_automation_runs_correlation_id', table_name='automation_runs')
    op.drop_column('automation_runs', 'correlation_id')
