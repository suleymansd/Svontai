"""Add Google Calendar sync state to appointments.

Revision ID: 040
Revises: 039
Create Date: 2026-07-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("calendar_provider", sa.String(length=30), nullable=True))
    op.add_column("appointments", sa.Column("calendar_event_id", sa.String(length=255), nullable=True))
    op.add_column(
        "appointments",
        sa.Column("calendar_sync_status", sa.String(length=30), nullable=False, server_default="pending"),
    )
    op.add_column("appointments", sa.Column("calendar_last_error", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("calendar_synced_at", sa.DateTime(), nullable=True))
    op.create_index("ix_appointments_calendar_event_id", "appointments", ["calendar_event_id"], unique=False)
    op.create_index("ix_appointments_calendar_sync_status", "appointments", ["calendar_sync_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_appointments_calendar_sync_status", table_name="appointments")
    op.drop_index("ix_appointments_calendar_event_id", table_name="appointments")
    op.drop_column("appointments", "calendar_synced_at")
    op.drop_column("appointments", "calendar_last_error")
    op.drop_column("appointments", "calendar_sync_status")
    op.drop_column("appointments", "calendar_event_id")
    op.drop_column("appointments", "calendar_provider")
