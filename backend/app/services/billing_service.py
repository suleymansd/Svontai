"""Billing service for plan, limits, and usage summaries."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.plans import (
    PLAN_DEFAULT_TOOL_RATE_LIMITS,
    PLAN_MONTHLY_TOOL_RUN_LIMITS,
    normalize_plan_code,
)
from app.models.subscription import TenantSubscription
from app.models.tenant_membership import TenantMembership
from app.models.tenant_tool import TenantTool
from app.models.tool import Tool
from app.models.tool_run import ToolRun
from app.services.subscription_service import SubscriptionService


class BillingService:
    def __init__(self, db: Session):
        self.db = db
        self._subscription_service = SubscriptionService(db)

    @staticmethod
    def month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
        current = now or datetime.now(UTC)
        month_start = datetime(current.year, current.month, 1, tzinfo=UTC).replace(tzinfo=None)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        return month_start, next_month

    def get_subscription_or_create(self, tenant_id: uuid.UUID) -> TenantSubscription:
        subscription = self._subscription_service.get_subscription(tenant_id)
        if subscription is None:
            subscription = self._subscription_service.create_subscription(tenant_id, "free")
        return subscription

    def resolve_plan_code(self, tenant_id: uuid.UUID) -> str:
        subscription = self.get_subscription_or_create(tenant_id)
        return normalize_plan_code(subscription.plan.plan_type or subscription.plan.name)

    def monthly_runs_limit(self, tenant_id: uuid.UUID) -> int:
        plan_code = self.resolve_plan_code(tenant_id)
        return PLAN_MONTHLY_TOOL_RUN_LIMITS.get(plan_code, PLAN_MONTHLY_TOOL_RUN_LIMITS["free"])

    def monthly_runs_used(self, tenant_id: uuid.UUID) -> int:
        month_start, month_end = self.month_window()
        return (
            self.db.query(func.count(ToolRun.id))
            .filter(
                ToolRun.tenant_id == tenant_id,
                ToolRun.created_at >= month_start,
                ToolRun.created_at < month_end,
            )
            .scalar()
            or 0
        )

    def by_tool_monthly_usage(self, tenant_id: uuid.UUID) -> dict[str, int]:
        month_start, month_end = self.month_window()
        rows = (
            self.db.query(ToolRun.tool_slug, func.count(ToolRun.id))
            .filter(
                ToolRun.tenant_id == tenant_id,
                ToolRun.created_at >= month_start,
                ToolRun.created_at < month_end,
            )
            .group_by(ToolRun.tool_slug)
            .all()
        )
        return {slug: int(count) for slug, count in rows}

    def last_30_days_chart(self, tenant_id: uuid.UUID) -> list[dict[str, int | str]]:
        utc_today = datetime.now(UTC).date()
        start_date = utc_today - timedelta(days=29)
        start_dt = datetime.combine(start_date, datetime.min.time())

        rows = (
            self.db.query(func.date(ToolRun.created_at), func.count(ToolRun.id))
            .filter(
                ToolRun.tenant_id == tenant_id,
                ToolRun.created_at >= start_dt,
            )
            .group_by(func.date(ToolRun.created_at))
            .all()
        )
        by_day = defaultdict(int)
        for raw_day, count in rows:
            by_day[str(raw_day)] = int(count)

        points: list[dict[str, int | str]] = []
        for offset in range(30):
            day = start_date + timedelta(days=offset)
            day_key = day.isoformat()
            points.append({"day": day_key, "runs": int(by_day.get(day_key, 0))})
        return points

    def per_tool_rate_limits(self, tenant_id: uuid.UUID) -> dict[str, int]:
        plan_code = self.resolve_plan_code(tenant_id)
        default_limit = PLAN_DEFAULT_TOOL_RATE_LIMITS.get(plan_code, PLAN_DEFAULT_TOOL_RATE_LIMITS["free"])

        tools = self.db.query(Tool).all()
        tenant_rows = self.db.query(TenantTool).filter(TenantTool.tenant_id == tenant_id).all()
        tenant_map = {row.tool_slug: row for row in tenant_rows}

        result: dict[str, int] = {}
        for tool in tools:
            slug = tool.slug or tool.key
            tenant_tool = tenant_map.get(slug)
            if tenant_tool and tenant_tool.rate_limit_per_minute is not None:
                result[slug] = int(tenant_tool.rate_limit_per_minute)
            else:
                result[slug] = int(default_limit)
        return result

    def get_plan_payload(self, tenant_id: uuid.UUID) -> dict:
        subscription = self.get_subscription_or_create(tenant_id)
        active_seats = (
            self.db.query(func.count(TenantMembership.id))
            .filter(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.status == "active",
            )
            .scalar()
            or 0
        )
        return {
            "plan": normalize_plan_code(subscription.plan.plan_type or subscription.plan.name),
            "renew_at": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "status": subscription.status,
            "seats": int(active_seats),
            "notes": subscription.extra_data.get("notes") if isinstance(subscription.extra_data, dict) else None,
        }

    def get_limits_payload(self, tenant_id: uuid.UUID) -> dict:
        plan_code = self.resolve_plan_code(tenant_id)
        monthly_limit = self.monthly_runs_limit(tenant_id)
        used = self.monthly_runs_used(tenant_id)
        by_tool = self.by_tool_monthly_usage(tenant_id)
        return {
            "plan": plan_code,
            "limits": {
                "monthly_runs": monthly_limit,
                "rate_limits": self.per_tool_rate_limits(tenant_id),
            },
            "usage": {
                "monthly_runs_used": used,
                "monthly_runs_remaining": max(0, monthly_limit - used),
                "by_tool": by_tool,
                "chart_30d": self.last_30_days_chart(tenant_id),
            },
        }

    def check_monthly_limit(self, tenant_id: uuid.UUID) -> tuple[bool, int, int]:
        monthly_limit = self.monthly_runs_limit(tenant_id)
        used = self.monthly_runs_used(tenant_id)
        if monthly_limit > 0 and used >= monthly_limit:
            return False, used, monthly_limit
        return True, used, monthly_limit
