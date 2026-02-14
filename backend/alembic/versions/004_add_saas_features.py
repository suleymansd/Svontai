"""Add SaaS features - Plans, Subscriptions, Analytics, Bot Settings, Onboarding

Revision ID: 004
Revises: 003_add_whatsapp_onboarding_tables
Create Date: 2024-01-15 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite
import uuid
from datetime import datetime, timedelta

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create plans table
    op.create_table(
        'plans',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(50), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('plan_type', sa.String(20), nullable=False, server_default='free'),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='TRY'),
        sa.Column('message_limit', sa.Integer, nullable=False, server_default='100'),
        sa.Column('bot_limit', sa.Integer, nullable=False, server_default='1'),
        sa.Column('knowledge_items_limit', sa.Integer, nullable=False, server_default='50'),
        sa.Column('feature_flags', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('trial_days', sa.Integer, nullable=False, server_default='14'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('is_public', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # Create tenant_subscriptions table
    op.create_table(
        'tenant_subscriptions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('plan_id', sa.UUID(), sa.ForeignKey('plans.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='trial'),
        sa.Column('started_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('trial_ends_at', sa.DateTime, nullable=True),
        sa.Column('current_period_start', sa.DateTime, nullable=True),
        sa.Column('current_period_end', sa.DateTime, nullable=True),
        sa.Column('cancelled_at', sa.DateTime, nullable=True),
        sa.Column('ends_at', sa.DateTime, nullable=True),
        sa.Column('messages_used_this_month', sa.Integer, nullable=False, server_default='0'),
        sa.Column('usage_reset_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('payment_provider', sa.String(50), nullable=True),
        sa.Column('external_subscription_id', sa.String(255), nullable=True),
        sa.Column('external_customer_id', sa.String(255), nullable=True),
        sa.Column('extra_data', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # Create usage_logs table
    op.create_table(
        'usage_logs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('bot_id', sa.UUID(), sa.ForeignKey('bots.id', ondelete='SET NULL'), nullable=True),
        sa.Column('usage_type', sa.String(50), nullable=False),
        sa.Column('count', sa.Integer, nullable=False, server_default='1'),
        sa.Column('extra_data', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_usage_logs_tenant_id', 'usage_logs', ['tenant_id'])
    op.create_index('ix_usage_logs_usage_type', 'usage_logs', ['usage_type'])
    op.create_index('ix_usage_logs_created_at', 'usage_logs', ['created_at'])
    
    # Create daily_stats table
    op.create_table(
        'daily_stats',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date, nullable=False),
        sa.Column('messages_sent', sa.Integer, nullable=False, server_default='0'),
        sa.Column('messages_received', sa.Integer, nullable=False, server_default='0'),
        sa.Column('ai_responses', sa.Integer, nullable=False, server_default='0'),
        sa.Column('conversations_started', sa.Integer, nullable=False, server_default='0'),
        sa.Column('conversations_total', sa.Integer, nullable=False, server_default='0'),
        sa.Column('leads_captured', sa.Integer, nullable=False, server_default='0'),
        sa.Column('whatsapp_messages', sa.Integer, nullable=False, server_default='0'),
        sa.Column('widget_messages', sa.Integer, nullable=False, server_default='0'),
        sa.Column('operator_takeovers', sa.Integer, nullable=False, server_default='0'),
        sa.Column('extra_data', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_daily_stats_tenant_id', 'daily_stats', ['tenant_id'])
    op.create_index('ix_daily_stats_date', 'daily_stats', ['date'])
    
    # Create bot_settings table
    op.create_table(
        'bot_settings',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('bot_id', sa.UUID(), sa.ForeignKey('bots.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('response_tone', sa.String(20), nullable=False, server_default='friendly'),
        sa.Column('emoji_usage', sa.String(10), nullable=False, server_default='light'),
        sa.Column('max_response_length', sa.Integer, nullable=False, server_default='500'),
        sa.Column('memory_window', sa.Integer, nullable=False, server_default='10'),
        sa.Column('enable_guardrails', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('fallback_message', sa.Text, nullable=False, server_default='Üzgünüm, bu konuda size yardımcı olamıyorum.'),
        sa.Column('uncertainty_threshold', sa.Float, nullable=False, server_default='0.7'),
        sa.Column('human_handoff_enabled', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('human_handoff_message', sa.Text, nullable=False, server_default='Sizi bir müşteri temsilcimize bağlıyorum.'),
        sa.Column('rate_limit_per_minute', sa.Integer, nullable=False, server_default='20'),
        sa.Column('rate_limit_per_hour', sa.Integer, nullable=False, server_default='100'),
        sa.Column('system_prompt_override', sa.Text, nullable=True),
        sa.Column('prohibited_topics', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('extra_settings', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # Create tenant_onboarding table
    op.create_table(
        'tenant_onboarding',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('is_completed', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('steps', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('current_step', sa.String(50), nullable=False, server_default='create_tenant'),
        sa.Column('dismissed', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('dismissed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # Add new columns to conversations table
    op.add_column('conversations', sa.Column('status', sa.String(20), nullable=True, server_default='ai_active'))
    op.add_column('conversations', sa.Column('is_ai_paused', sa.Boolean, nullable=True, server_default='0'))
    op.add_column('conversations', sa.Column('operator_id', sa.UUID(), nullable=True))
    op.add_column('conversations', sa.Column('takeover_at', sa.DateTime, nullable=True))
    op.add_column('conversations', sa.Column('has_lead', sa.Boolean, nullable=True, server_default='0'))
    op.add_column('conversations', sa.Column('lead_score', sa.Integer, nullable=True, server_default='0'))
    op.add_column('conversations', sa.Column('summary', sa.Text, nullable=True))
    op.add_column('conversations', sa.Column('tags', sa.JSON, nullable=True, server_default='[]'))
    
    # Add new columns to leads table
    op.add_column('leads', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('leads', sa.Column('company', sa.String(255), nullable=True))
    op.add_column('leads', sa.Column('score', sa.Integer, nullable=True, server_default='0'))
    op.add_column('leads', sa.Column('is_auto_detected', sa.Boolean, nullable=True, server_default='0'))
    op.add_column('leads', sa.Column('detection_confidence', sa.Float, nullable=True, server_default='0.0'))
    op.add_column('leads', sa.Column('detected_fields', sa.JSON, nullable=True, server_default='{}'))
    op.add_column('leads', sa.Column('tags', sa.JSON, nullable=True, server_default='[]'))
    op.add_column('leads', sa.Column('extra_data', sa.JSON, nullable=True, server_default='{}'))
    op.add_column('leads', sa.Column('is_deleted', sa.Boolean, nullable=True, server_default='0'))
    op.add_column('leads', sa.Column('deleted_at', sa.DateTime, nullable=True))
    op.add_column('leads', sa.Column('updated_at', sa.DateTime, nullable=True, server_default=sa.func.now()))
    
    # Insert default plans
    op.execute("""
        INSERT INTO plans (id, name, display_name, description, plan_type, price_monthly, price_yearly, message_limit, bot_limit, knowledge_items_limit, feature_flags, trial_days, sort_order)
        VALUES 
        ('%(free_id)s', 'free', 'Ücretsiz', 'Başlamak için ideal', 'free', 0, 0, 100, 1, 20, '{"whatsapp_integration": false, "analytics": false, "custom_branding": false, "priority_support": false, "api_access": false, "export_data": false, "operator_takeover": false, "lead_automation": false}', 0, 0),
        ('%(starter_id)s', 'starter', 'Başlangıç', 'Küçük işletmeler için', 'starter', 299, 2990, 1000, 2, 100, '{"whatsapp_integration": true, "analytics": true, "custom_branding": false, "priority_support": false, "api_access": false, "export_data": true, "operator_takeover": false, "lead_automation": true}', 14, 1),
        ('%(pro_id)s', 'pro', 'Profesyonel', 'Büyüyen işletmeler için', 'pro', 599, 5990, 5000, 5, 500, '{"whatsapp_integration": true, "analytics": true, "custom_branding": true, "priority_support": true, "api_access": true, "export_data": true, "operator_takeover": true, "lead_automation": true}', 14, 2),
        ('%(business_id)s', 'business', 'İşletme', 'Büyük ekipler için', 'business', 1299, 12990, 20000, 20, 2000, '{"whatsapp_integration": true, "analytics": true, "custom_branding": true, "priority_support": true, "api_access": true, "export_data": true, "operator_takeover": true, "lead_automation": true, "white_label": true, "dedicated_support": true}', 14, 3)
    """ % {
        'free_id': str(uuid.uuid4()),
        'starter_id': str(uuid.uuid4()),
        'pro_id': str(uuid.uuid4()),
        'business_id': str(uuid.uuid4())
    })


def downgrade() -> None:
    # Drop new columns from leads
    op.drop_column('leads', 'updated_at')
    op.drop_column('leads', 'deleted_at')
    op.drop_column('leads', 'is_deleted')
    op.drop_column('leads', 'extra_data')
    op.drop_column('leads', 'tags')
    op.drop_column('leads', 'detected_fields')
    op.drop_column('leads', 'detection_confidence')
    op.drop_column('leads', 'is_auto_detected')
    op.drop_column('leads', 'score')
    op.drop_column('leads', 'company')
    op.drop_column('leads', 'tenant_id')
    
    # Drop new columns from conversations
    op.drop_column('conversations', 'tags')
    op.drop_column('conversations', 'summary')
    op.drop_column('conversations', 'lead_score')
    op.drop_column('conversations', 'has_lead')
    op.drop_column('conversations', 'takeover_at')
    op.drop_column('conversations', 'operator_id')
    op.drop_column('conversations', 'is_ai_paused')
    op.drop_column('conversations', 'status')
    
    # Drop tables
    op.drop_table('tenant_onboarding')
    op.drop_table('bot_settings')
    op.drop_index('ix_daily_stats_date', 'daily_stats')
    op.drop_index('ix_daily_stats_tenant_id', 'daily_stats')
    op.drop_table('daily_stats')
    op.drop_index('ix_usage_logs_created_at', 'usage_logs')
    op.drop_index('ix_usage_logs_usage_type', 'usage_logs')
    op.drop_index('ix_usage_logs_tenant_id', 'usage_logs')
    op.drop_table('usage_logs')
    op.drop_table('tenant_subscriptions')
    op.drop_table('plans')
