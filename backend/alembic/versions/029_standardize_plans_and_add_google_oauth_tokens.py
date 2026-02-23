"""Standardize plan names and add google_oauth_tokens table

Revision ID: 029
Revises: 028
Create Date: 2026-02-22
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _plan_id(bind, name: str):
    return bind.execute(sa.text("SELECT id FROM plans WHERE name = :name LIMIT 1"), {"name": name}).scalar()


def _remap_subscription_plan(bind, from_plan_id, to_plan_id) -> None:
    if not from_plan_id or not to_plan_id:
        return
    bind.execute(
        sa.text("UPDATE tenant_subscriptions SET plan_id = :to_plan WHERE plan_id = :from_plan"),
        {"to_plan": to_plan_id, "from_plan": from_plan_id},
    )


def _ensure_plan(
    bind,
    *,
    name: str,
    display_name: str,
    description: str,
    plan_type: str,
    sort_order: int,
    price_monthly: int,
    price_yearly: int,
    message_limit: int,
    bot_limit: int,
    knowledge_items_limit: int,
    feature_flags: dict,
) -> None:
    if _plan_id(bind, name):
        return

    bind.execute(
        sa.text(
            """
            INSERT INTO plans (
                id, name, display_name, description, plan_type, price_monthly, price_yearly, currency,
                message_limit, bot_limit, knowledge_items_limit, feature_flags, trial_days,
                is_active, is_public, sort_order, created_at, updated_at
            ) VALUES (
                :id, :name, :display_name, :description, :plan_type, :price_monthly, :price_yearly, 'TRY',
                :message_limit, :bot_limit, :knowledge_items_limit, :feature_flags, 14,
                true, true, :sort_order, NOW(), NOW()
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "display_name": display_name,
            "description": description,
            "plan_type": plan_type,
            "price_monthly": price_monthly,
            "price_yearly": price_yearly,
            "message_limit": message_limit,
            "bot_limit": bot_limit,
            "knowledge_items_limit": knowledge_items_limit,
            "feature_flags": feature_flags,
            "sort_order": sort_order,
        },
    )


def upgrade() -> None:
    op.create_table(
        "google_oauth_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="google"),
        sa.Column("scopes_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider", name="uq_google_oauth_tokens_tenant_provider"),
    )
    op.create_index("ix_google_oauth_tokens_tenant_id", "google_oauth_tokens", ["tenant_id"])
    op.create_index("ix_google_oauth_tokens_provider", "google_oauth_tokens", ["provider"])
    op.create_index("ix_google_oauth_tokens_tenant_provider", "google_oauth_tokens", ["tenant_id", "provider"])
    op.create_index("ix_google_oauth_tokens_expires_at", "google_oauth_tokens", ["expires_at"])

    bind = op.get_bind()

    calendar_scope = ["https://www.googleapis.com/auth/calendar.events"]
    if bind.dialect.name == "sqlite":
        raw_rows = bind.execute(
            sa.text(
                """
                SELECT
                    tenant_id,
                    access_token_encrypted,
                    refresh_token_encrypted,
                    updated_at
                FROM real_estate_google_calendar_integrations
                WHERE status = 'active'
                  AND (access_token_encrypted IS NOT NULL OR refresh_token_encrypted IS NOT NULL)
                ORDER BY tenant_id ASC, updated_at DESC
                """
            )
        ).mappings().all()
        deduped: dict[str, dict] = {}
        for row in raw_rows:
            tenant_key = str(row["tenant_id"])
            if tenant_key not in deduped:
                deduped[tenant_key] = row
        rows = list(deduped.values())
    else:
        rows = bind.execute(
            sa.text(
                """
                SELECT DISTINCT ON (tenant_id)
                    tenant_id,
                    access_token_encrypted,
                    refresh_token_encrypted,
                    updated_at
                FROM real_estate_google_calendar_integrations
                WHERE status = 'active'
                  AND (access_token_encrypted IS NOT NULL OR refresh_token_encrypted IS NOT NULL)
                ORDER BY tenant_id, updated_at DESC
                """
            )
        ).mappings().all()

    for row in rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO google_oauth_tokens (
                    id, tenant_id, provider, scopes_json, access_token_encrypted, refresh_token_encrypted, expires_at, created_at, updated_at
                ) VALUES (
                    :id, :tenant_id, 'google', :scopes_json, :access_token_encrypted, :refresh_token_encrypted, NULL, NOW(), NOW()
                )
                ON CONFLICT (tenant_id, provider) DO UPDATE SET
                    access_token_encrypted = EXCLUDED.access_token_encrypted,
                    refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                    scopes_json = EXCLUDED.scopes_json,
                    updated_at = NOW()
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": row["tenant_id"],
                "scopes_json": calendar_scope,
                "access_token_encrypted": row["access_token_encrypted"],
                "refresh_token_encrypted": row["refresh_token_encrypted"],
            },
        )

    if _plan_id(bind, "pro") and not _plan_id(bind, "premium"):
        bind.execute(sa.text("UPDATE plans SET name = 'premium', plan_type = 'premium', display_name = 'Premium' WHERE name = 'pro'"))
    if _plan_id(bind, "starter") and not _plan_id(bind, "pro"):
        bind.execute(sa.text("UPDATE plans SET name = 'pro', plan_type = 'pro', display_name = 'Pro' WHERE name = 'starter'"))
    if _plan_id(bind, "business") and not _plan_id(bind, "enterprise"):
        bind.execute(sa.text("UPDATE plans SET name = 'enterprise', plan_type = 'enterprise', display_name = 'Kurumsal' WHERE name = 'business'"))

    pro_id = _plan_id(bind, "pro")
    starter_id = _plan_id(bind, "starter")
    if pro_id and starter_id:
        _remap_subscription_plan(bind, starter_id, pro_id)
        bind.execute(sa.text("DELETE FROM plans WHERE id = :id"), {"id": starter_id})

    enterprise_id = _plan_id(bind, "enterprise")
    business_id = _plan_id(bind, "business")
    if enterprise_id and business_id:
        _remap_subscription_plan(bind, business_id, enterprise_id)
        bind.execute(sa.text("DELETE FROM plans WHERE id = :id"), {"id": business_id})

    _ensure_plan(
        bind,
        name="pro",
        display_name="Pro",
        description="Küçük ve büyüyen ekipler için",
        plan_type="pro",
        sort_order=1,
        price_monthly=299,
        price_yearly=2990,
        message_limit=1000,
        bot_limit=2,
        knowledge_items_limit=100,
        feature_flags={
            "whatsapp_integration": True,
            "analytics": True,
            "custom_branding": False,
            "priority_support": False,
            "api_access": False,
            "export_data": True,
            "operator_takeover": False,
            "lead_automation": True,
            "tickets": True,
            "error_center": True,
            "usage": True,
            "tools_catalog": True,
            "tool_guides": True,
        },
    )
    _ensure_plan(
        bind,
        name="premium",
        display_name="Premium",
        description="İleri düzey otomasyon kullanan ekipler için",
        plan_type="premium",
        sort_order=2,
        price_monthly=599,
        price_yearly=5990,
        message_limit=5000,
        bot_limit=5,
        knowledge_items_limit=500,
        feature_flags={
            "whatsapp_integration": True,
            "analytics": True,
            "custom_branding": True,
            "priority_support": True,
            "api_access": True,
            "export_data": True,
            "operator_takeover": True,
            "lead_automation": True,
            "tickets": True,
            "error_center": True,
            "usage": True,
            "tools_catalog": True,
            "tool_guides": True,
            "premium_tools": True,
        },
    )
    _ensure_plan(
        bind,
        name="enterprise",
        display_name="Kurumsal",
        description="Kurumsal ölçek ve özel SLA ihtiyaçları için",
        plan_type="enterprise",
        sort_order=3,
        price_monthly=1299,
        price_yearly=12990,
        message_limit=20000,
        bot_limit=20,
        knowledge_items_limit=2000,
        feature_flags={
            "whatsapp_integration": True,
            "analytics": True,
            "custom_branding": True,
            "priority_support": True,
            "api_access": True,
            "export_data": True,
            "operator_takeover": True,
            "lead_automation": True,
            "white_label": True,
            "dedicated_support": True,
            "tickets": True,
            "error_center": True,
            "usage": True,
            "tools_catalog": True,
            "tool_guides": True,
            "premium_tools": True,
        },
    )

    bind.execute(sa.text("UPDATE plans SET plan_type = 'pro', display_name = 'Pro' WHERE name = 'pro'"))
    bind.execute(sa.text("UPDATE plans SET plan_type = 'premium', display_name = 'Premium' WHERE name = 'premium'"))
    bind.execute(sa.text("UPDATE plans SET plan_type = 'enterprise', display_name = 'Kurumsal' WHERE name = 'enterprise'"))
    bind.execute(sa.text("UPDATE plans SET plan_type = 'free', display_name = COALESCE(display_name, 'Ücretsiz') WHERE name = 'free'"))
    bind.execute(sa.text("UPDATE plans SET sort_order = 0 WHERE name = 'free'"))
    bind.execute(sa.text("UPDATE plans SET sort_order = 1 WHERE name = 'pro'"))
    bind.execute(sa.text("UPDATE plans SET sort_order = 2 WHERE name = 'premium'"))
    bind.execute(sa.text("UPDATE plans SET sort_order = 3 WHERE name = 'enterprise'"))

    bind.execute(sa.text("UPDATE tools SET required_plan = 'pro' WHERE lower(required_plan) = 'starter'"))
    bind.execute(sa.text("UPDATE tools SET required_plan = 'premium' WHERE lower(required_plan) IN ('growth', 'business')"))


def downgrade() -> None:
    bind = op.get_bind()
    if _plan_id(bind, "starter") is None and _plan_id(bind, "pro") is not None:
        bind.execute(sa.text("UPDATE plans SET name = 'starter', plan_type = 'starter', display_name = 'Başlangıç' WHERE name = 'pro'"))
    if _plan_id(bind, "pro") is None and _plan_id(bind, "premium") is not None:
        bind.execute(sa.text("UPDATE plans SET name = 'pro', plan_type = 'pro', display_name = 'Profesyonel' WHERE name = 'premium'"))
    if _plan_id(bind, "business") is None and _plan_id(bind, "enterprise") is not None:
        bind.execute(sa.text("UPDATE plans SET name = 'business', plan_type = 'business', display_name = 'İşletme' WHERE name = 'enterprise'"))

    op.drop_index("ix_google_oauth_tokens_expires_at", table_name="google_oauth_tokens")
    op.drop_index("ix_google_oauth_tokens_tenant_provider", table_name="google_oauth_tokens")
    op.drop_index("ix_google_oauth_tokens_provider", table_name="google_oauth_tokens")
    op.drop_index("ix_google_oauth_tokens_tenant_id", table_name="google_oauth_tokens")
    op.drop_table("google_oauth_tokens")
