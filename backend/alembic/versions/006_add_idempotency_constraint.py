"""Add idempotency constraint for automation_runs

Revision ID: 006
Revises: 005
Create Date: 2026-01-24

This migration adds a unique constraint on (tenant_id, message_id) in the
automation_runs table to prevent duplicate processing of the same WhatsApp message.

This ensures idempotency: if Meta sends the same webhook multiple times,
we only process it once.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add unique constraint for idempotency."""
    # Create a unique index on (tenant_id, message_id) for idempotency
    # Using index instead of constraint for partial uniqueness (message_id can be NULL)
    # We only enforce uniqueness when message_id is NOT NULL
    op.create_index(
        'ix_automation_runs_tenant_message_idempotency',
        'automation_runs',
        ['tenant_id', 'message_id'],
        unique=True,
        postgresql_where=sa.text('message_id IS NOT NULL'),
        sqlite_where=sa.text('message_id IS NOT NULL')
    )


def downgrade() -> None:
    """Remove unique constraint."""
    op.drop_index('ix_automation_runs_tenant_message_idempotency', table_name='automation_runs')
