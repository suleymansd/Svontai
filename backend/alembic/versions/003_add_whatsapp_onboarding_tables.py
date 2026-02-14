"""Add WhatsApp onboarding tables

Revision ID: 003
Revises: 002
Create Date: 2024-12-17

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create whatsapp_accounts table
    op.create_table(
        'whatsapp_accounts',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('waba_id', sa.String(50), nullable=True),
        sa.Column('phone_number_id', sa.String(50), nullable=True),
        sa.Column('display_phone_number', sa.String(20), nullable=True),
        sa.Column('business_id', sa.String(50), nullable=True),
        sa.Column('app_id', sa.String(50), nullable=True),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_status', sa.String(20), nullable=False, default='pending'),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('webhook_verify_token', sa.String(100), nullable=True),
        sa.Column('webhook_status', sa.String(30), nullable=False, default='not_configured'),
        sa.Column('webhook_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    
    # Create onboarding_steps table
    op.create_table(
        'onboarding_steps',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider', sa.String(30), nullable=False),
        sa.Column('step_key', sa.String(50), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False, default=0),
        sa.Column('step_name', sa.String(100), nullable=False),
        sa.Column('step_description', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('onboarding_steps')
    op.drop_table('whatsapp_accounts')
