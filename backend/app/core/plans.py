"""Centralized plan codes and helpers."""

from __future__ import annotations

from enum import Enum


class StandardPlanType(str, Enum):
    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


PLAN_ORDER: tuple[str, ...] = (
    StandardPlanType.FREE.value,
    StandardPlanType.PRO.value,
    StandardPlanType.PREMIUM.value,
    StandardPlanType.ENTERPRISE.value,
)

PLAN_LEVELS: dict[str, int] = {
    code: index for index, code in enumerate(PLAN_ORDER)
}

PLAN_UI_LABELS: dict[str, str] = {
    StandardPlanType.FREE.value: "Ücretsiz",
    StandardPlanType.PRO.value: "Pro",
    StandardPlanType.PREMIUM.value: "Premium",
    StandardPlanType.ENTERPRISE.value: "Kurumsal",
}

# Marketplace defaults
PLAN_DEFAULT_TOOL_RATE_LIMITS: dict[str, int] = {
    StandardPlanType.FREE.value: 5,
    StandardPlanType.PRO.value: 60,
    StandardPlanType.PREMIUM.value: 120,
    StandardPlanType.ENTERPRISE.value: 240,
}

PLAN_MONTHLY_TOOL_RUN_LIMITS: dict[str, int] = {
    StandardPlanType.FREE.value: 300,
    StandardPlanType.PRO.value: 2_000,
    StandardPlanType.PREMIUM.value: 10_000,
    StandardPlanType.ENTERPRISE.value: 50_000,
}

LEGACY_PLAN_ALIASES: dict[str, str] = {
    "starter": StandardPlanType.PRO.value,
    "growth": StandardPlanType.PREMIUM.value,
    "business": StandardPlanType.ENTERPRISE.value,
}


def normalize_plan_code(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return StandardPlanType.FREE.value
    mapped = LEGACY_PLAN_ALIASES.get(raw, raw)
    if mapped in PLAN_LEVELS:
        return mapped
    return StandardPlanType.FREE.value


def plan_meets_requirement(current_plan: str | None, required_plan: str | None) -> bool:
    current = normalize_plan_code(current_plan)
    required = normalize_plan_code(required_plan)
    return PLAN_LEVELS[current] >= PLAN_LEVELS[required]
