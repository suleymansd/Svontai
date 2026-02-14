"""Add n8n automation tables

Revision ID: 005
Revises: 004
Create Date: 2024-01-20 10:00:00.000000

This migration adds tables for n8n workflow engine integration:
- automation_runs: Tracks individual automation executions
- tenant_automation_settings: Per-tenant automation configuration
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create automation_runs table
    op.create_table(
        'automation_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False, server_default='whatsapp'),
        sa.Column('from_number', sa.String(50), nullable=False),
        sa.Column('to_number', sa.String(50), nullable=True),
        sa.Column('message_id', sa.String(255), nullable=True),
        sa.Column('message_content', sa.Text, nullable=True),
        sa.Column('n8n_workflow_id', sa.String(255), nullable=True),
        sa.Column('n8n_execution_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='received'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('request_payload', sa.JSON, nullable=True),
        sa.Column('response_payload', sa.JSON, nullable=True),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('extra_data', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # Create indexes for automation_runs
    op.create_index('ix_automation_runs_tenant_id', 'automation_runs', ['tenant_id'])
    op.create_index('ix_automation_runs_message_id', 'automation_runs', ['message_id'])
    op.create_index('ix_automation_runs_n8n_execution_id', 'automation_runs', ['n8n_execution_id'])
    op.create_index('ix_automation_runs_status', 'automation_runs', ['status'])
    op.create_index('ix_automation_runs_created_at', 'automation_runs', ['created_at'])
    
    # Create tenant_automation_settings table
    op.create_table(
        'tenant_automation_settings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False, unique=True),
        sa.Column('use_n8n', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('default_workflow_id', sa.String(255), nullable=True),
        sa.Column('whatsapp_workflow_id', sa.String(255), nullable=True),
        sa.Column('widget_workflow_id', sa.String(255), nullable=True),
        sa.Column('custom_n8n_url', sa.String(500), nullable=True),
        sa.Column('custom_shared_secret', sa.String(255), nullable=True),
        sa.Column('enable_auto_retry', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('max_retries', sa.Integer, nullable=False, server_default='2'),
        sa.Column('timeout_seconds', sa.Integer, nullable=False, server_default='10'),
        sa.Column('extra_settings', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # Create index for tenant_automation_settings
    op.create_index('ix_tenant_automation_settings_tenant_id', 'tenant_automation_settings', ['tenant_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_tenant_automation_settings_tenant_id', 'tenant_automation_settings')
    op.drop_index('ix_automation_runs_created_at', 'automation_runs')
    op.drop_index('ix_automation_runs_status', 'automation_runs')
    op.drop_index('ix_automation_runs_n8n_execution_id', 'automation_runs')
    op.drop_index('ix_automation_runs_message_id', 'automation_runs')
    op.drop_index('ix_automation_runs_tenant_id', 'automation_runs')
    
    # Drop tables
    op.drop_table('tenant_automation_settings')
    op.drop_table('automation_runs')
