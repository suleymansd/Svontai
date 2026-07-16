"""Allow tenant-scoped leads without a bot.

Revision ID: 039
Revises: 038
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "leads",
        "bot_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE leads AS lead
        SET bot_id = (
            SELECT bot.id
            FROM bots AS bot
            WHERE bot.tenant_id = lead.tenant_id
            ORDER BY bot.created_at ASC
            LIMIT 1
        )
        WHERE lead.bot_id IS NULL
        """
    )
    op.alter_column(
        "leads",
        "bot_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
