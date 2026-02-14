"""Add tickets tables

Revision ID: 012
Revises: 011
Create Date: 2026-01-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tickets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('requester_id', sa.String(36), nullable=True),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('priority', sa.String(20), nullable=False, server_default='normal'),
        sa.Column('assigned_to', sa.String(36), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_tickets_tenant_id', 'tickets', ['tenant_id'])
    op.create_index('ix_tickets_requester_id', 'tickets', ['requester_id'])
    op.create_index('ix_tickets_assigned_to', 'tickets', ['assigned_to'])
    op.create_index('ix_tickets_status', 'tickets', ['status'])
    op.create_index('ix_tickets_priority', 'tickets', ['priority'])
    op.create_index('ix_tickets_last_activity_at', 'tickets', ['last_activity_at'])
    op.create_index('ix_tickets_created_at', 'tickets', ['created_at'])

    op.create_table(
        'ticket_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', sa.String(36), nullable=True),
        sa.Column('sender_type', sa.String(20), nullable=False, server_default='user'),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ticket_messages_ticket_id', 'ticket_messages', ['ticket_id'])
    op.create_index('ix_ticket_messages_sender_id', 'ticket_messages', ['sender_id'])
    op.create_index('ix_ticket_messages_created_at', 'ticket_messages', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_ticket_messages_created_at', table_name='ticket_messages')
    op.drop_index('ix_ticket_messages_sender_id', table_name='ticket_messages')
    op.drop_index('ix_ticket_messages_ticket_id', table_name='ticket_messages')
    op.drop_table('ticket_messages')

    op.drop_index('ix_tickets_created_at', table_name='tickets')
    op.drop_index('ix_tickets_last_activity_at', table_name='tickets')
    op.drop_index('ix_tickets_priority', table_name='tickets')
    op.drop_index('ix_tickets_status', table_name='tickets')
    op.drop_index('ix_tickets_assigned_to', table_name='tickets')
    op.drop_index('ix_tickets_requester_id', table_name='tickets')
    op.drop_index('ix_tickets_tenant_id', table_name='tickets')
    op.drop_table('tickets')
