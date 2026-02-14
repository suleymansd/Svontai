"""Add system_events and incidents tables

Revision ID: 008
Revises: 007
Create Date: 2026-01-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'system_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('message', sa.String(500), nullable=False),
        sa.Column('meta_json', sa.JSON(), nullable=True),
        sa.Column('correlation_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_system_events_tenant_id', 'system_events', ['tenant_id'])
    op.create_index('ix_system_events_source', 'system_events', ['source'])
    op.create_index('ix_system_events_level', 'system_events', ['level'])
    op.create_index('ix_system_events_code', 'system_events', ['code'])
    op.create_index('ix_system_events_correlation_id', 'system_events', ['correlation_id'])
    op.create_index('ix_system_events_created_at', 'system_events', ['created_at'])

    op.create_table(
        'incidents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('assigned_to', sa.String(36), nullable=True),
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_incidents_tenant_id', 'incidents', ['tenant_id'])
    op.create_index('ix_incidents_severity', 'incidents', ['severity'])
    op.create_index('ix_incidents_status', 'incidents', ['status'])
    op.create_index('ix_incidents_assigned_to', 'incidents', ['assigned_to'])
    op.create_index('ix_incidents_created_at', 'incidents', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_incidents_created_at', table_name='incidents')
    op.drop_index('ix_incidents_assigned_to', table_name='incidents')
    op.drop_index('ix_incidents_status', table_name='incidents')
    op.drop_index('ix_incidents_severity', table_name='incidents')
    op.drop_index('ix_incidents_tenant_id', table_name='incidents')
    op.drop_table('incidents')

    op.drop_index('ix_system_events_created_at', table_name='system_events')
    op.drop_index('ix_system_events_correlation_id', table_name='system_events')
    op.drop_index('ix_system_events_code', table_name='system_events')
    op.drop_index('ix_system_events_level', table_name='system_events')
    op.drop_index('ix_system_events_source', table_name='system_events')
    op.drop_index('ix_system_events_tenant_id', table_name='system_events')
    op.drop_table('system_events')
