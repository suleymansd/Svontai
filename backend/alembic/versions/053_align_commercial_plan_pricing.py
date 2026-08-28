"""Align commercial plan pricing and usage limits.

Revision ID: 053
Revises: 052
Create Date: 2026-08-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "053"
down_revision: Union[str, None] = "052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _update_plan(
    bind,
    *,
    name: str,
    display_name: str,
    description: str,
    price_monthly: int,
    price_yearly: int,
    message_limit: int,
) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE plans
            SET display_name = :display_name,
                description = :description,
                price_monthly = :price_monthly,
                price_yearly = :price_yearly,
                message_limit = :message_limit,
                updated_at = CURRENT_TIMESTAMP
            WHERE name = :name
            """
        ),
        {
            "name": name,
            "display_name": display_name,
            "description": description,
            "price_monthly": price_monthly,
            "price_yearly": price_yearly,
            "message_limit": message_limit,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    _update_plan(
        bind,
        name="pro",
        display_name="Başlangıç",
        description="Küçük işletmeler için satışa hazır WhatsApp AI",
        price_monthly=999,
        price_yearly=9990,
        message_limit=1000,
    )
    _update_plan(
        bind,
        name="premium",
        display_name="Profesyonel",
        description="Büyüyen işletmeler için gelişmiş otomasyon",
        price_monthly=4999,
        price_yearly=49990,
        message_limit=10000,
    )
    _update_plan(
        bind,
        name="enterprise",
        display_name="Kurumsal",
        description="Kurumsal ölçek ve özel SLA ihtiyaçları için",
        price_monthly=14999,
        price_yearly=149990,
        message_limit=50000,
    )


def downgrade() -> None:
    bind = op.get_bind()
    _update_plan(
        bind,
        name="pro",
        display_name="Pro",
        description="Küçük ve büyüyen ekipler için",
        price_monthly=299,
        price_yearly=2990,
        message_limit=1000,
    )
    _update_plan(
        bind,
        name="premium",
        display_name="Premium",
        description="İleri düzey otomasyon kullanan ekipler için",
        price_monthly=599,
        price_yearly=5990,
        message_limit=5000,
    )
    _update_plan(
        bind,
        name="enterprise",
        display_name="Kurumsal",
        description="Kurumsal ölçek ve özel SLA ihtiyaçları için",
        price_monthly=1299,
        price_yearly=12990,
        message_limit=20000,
    )
