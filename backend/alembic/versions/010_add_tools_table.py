"""Add tools table

Revision ID: 010
Revises: 009
Create Date: 2026-01-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tools',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('key', sa.String(100), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('icon', sa.String(100), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('required_plan', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('coming_soon', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_tools_key', 'tools', ['key'])
    op.create_index('ix_tools_category', 'tools', ['category'])
    op.create_index('ix_tools_status', 'tools', ['status'])


def downgrade() -> None:
    op.drop_index('ix_tools_status', table_name='tools')
    op.drop_index('ix_tools_category', table_name='tools')
    op.drop_index('ix_tools_key', table_name='tools')
    op.drop_table('tools')
