"""Privacy-safe product analytics collection and aggregation."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.product_event import ProductEvent


_EVENT_NAME = re.compile(r"^[a-z][a-z0-9_.-]{1,79}$")
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_BLOCKED_PROPERTY_PARTS = {
    "content",
    "email",
    "message",
    "name",
    "password",
    "phone",
    "prompt",
    "query",
    "secret",
    "text",
    "token",
}
_ALLOWED_CATEGORIES = {"navigation", "action", "error", "funnel", "performance"}
_ALLOWED_EVENT_NAMES = {
    "api_error",
    "assistant_simulator_message",
    "assistant_simulator_opened",
    "dashboard_viewed",
    "flow_abandoned",
    "form_error",
    "onboarding_completed",
    "page_view",
    "repeated_action",
    "simulator_error",
    "ui_action",
    "whatsapp_setup_opened",
}
_ALLOWED_PROPERTY_KEYS = {
    "action",
    "count",
    "duration_ms",
    "method",
    "mode",
    "provider",
    "result",
    "route",
    "status",
    "step",
    "turn",
}
_SAFE_PROPERTY_VALUE = re.compile(r"^[A-Za-z0-9_./:-]{1,200}$")
_FRICTION_EVENT_NAMES = {
    "api_error",
    "form_error",
    "flow_abandoned",
    "repeated_action",
    "simulator_error",
}


def _clean_path(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(str(value).strip())
    path = parsed.path or "/"
    return path[:300] if path.startswith("/") else f"/{path[:299]}"


def _clean_properties(value: dict[str, Any] | None) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for raw_key, raw_value in (value or {}).items():
        key = str(raw_key).strip().lower()[:50]
        if (
            not key
            or key not in _ALLOWED_PROPERTY_KEYS
            or any(part in key for part in _BLOCKED_PROPERTY_PARTS)
        ):
            continue
        if isinstance(raw_value, bool) or raw_value is None:
            cleaned[key] = raw_value
        elif isinstance(raw_value, (int, float)):
            cleaned[key] = raw_value
        elif isinstance(raw_value, str) and _SAFE_PROPERTY_VALUE.fullmatch(raw_value):
            cleaned[key] = _clean_path(raw_value) if key == "route" else raw_value
    return cleaned


class ProductAnalyticsService:
    """Collect events without storing form fields, chat content, or direct identifiers."""

    def __init__(self, db: Session):
        self.db = db

    def record_batch(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID | None,
        events: list[dict[str, Any]],
    ) -> int:
        now = utc_now_naive()
        accepted = 0
        for payload in events:
            name = str(payload.get("name") or "").strip().lower()
            category = str(payload.get("category") or "action").strip().lower()
            session_id = str(payload.get("session_id") or "").strip()
            if (
                not _EVENT_NAME.fullmatch(name)
                or name not in _ALLOWED_EVENT_NAMES
                or not _SESSION_ID.fullmatch(session_id)
            ):
                continue
            if category not in _ALLOWED_CATEGORIES:
                category = "action"
            occurred_at = payload.get("occurred_at")
            if not isinstance(occurred_at, datetime):
                occurred_at = now
            if occurred_at.tzinfo is not None:
                occurred_at = occurred_at.replace(tzinfo=None)
            if occurred_at < now - timedelta(days=2) or occurred_at > now + timedelta(minutes=5):
                occurred_at = now
            self.db.add(ProductEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                name=name,
                category=category,
                path=_clean_path(payload.get("path")),
                session_id=session_id,
                properties_json=_clean_properties(payload.get("properties")),
                occurred_at=occurred_at,
            ))
            accepted += 1
        if accepted:
            self.db.commit()
        return accepted

    def friction_summary(self, *, days: int = 30, tenant_id: UUID | None = None) -> dict[str, Any]:
        since = utc_now_naive() - timedelta(days=days)
        base_filters = [ProductEvent.occurred_at >= since]
        if tenant_id is not None:
            base_filters.append(ProductEvent.tenant_id == tenant_id)

        total_events = self.db.query(func.count(ProductEvent.id)).filter(*base_filters).scalar() or 0
        active_sessions = (
            self.db.query(func.count(func.distinct(ProductEvent.session_id)))
            .filter(*base_filters)
            .scalar()
            or 0
        )
        active_users = (
            self.db.query(func.count(func.distinct(ProductEvent.user_id)))
            .filter(*base_filters, ProductEvent.user_id.isnot(None))
            .scalar()
            or 0
        )

        top_paths = (
            self.db.query(ProductEvent.path, func.count(ProductEvent.id).label("count"))
            .filter(*base_filters, ProductEvent.path.isnot(None))
            .group_by(ProductEvent.path)
            .order_by(func.count(ProductEvent.id).desc())
            .limit(12)
            .all()
        )
        top_events = (
            self.db.query(ProductEvent.name, func.count(ProductEvent.id).label("count"))
            .filter(*base_filters)
            .group_by(ProductEvent.name)
            .order_by(func.count(ProductEvent.id).desc())
            .limit(20)
            .all()
        )
        friction = (
            self.db.query(
                ProductEvent.name,
                ProductEvent.path,
                func.count(ProductEvent.id).label("count"),
            )
            .filter(
                *base_filters,
                or_(
                    ProductEvent.category == "error",
                    ProductEvent.name.in_(_FRICTION_EVENT_NAMES),
                ),
            )
            .group_by(ProductEvent.name, ProductEvent.path)
            .order_by(func.count(ProductEvent.id).desc())
            .limit(20)
            .all()
        )

        funnel_names = [
            "dashboard_viewed",
            "assistant_simulator_opened",
            "assistant_simulator_message",
            "whatsapp_setup_opened",
            "onboarding_completed",
        ]
        funnel_rows = (
            self.db.query(ProductEvent.name, func.count(func.distinct(ProductEvent.session_id)))
            .filter(*base_filters, ProductEvent.name.in_(funnel_names))
            .group_by(ProductEvent.name)
            .all()
        )
        funnel_map = {name: count for name, count in funnel_rows}

        return {
            "period_days": days,
            "total_events": int(total_events),
            "active_sessions": int(active_sessions),
            "active_users": int(active_users),
            "top_paths": [{"path": path, "count": count} for path, count in top_paths],
            "top_events": [{"name": name, "count": count} for name, count in top_events],
            "friction": [
                {"name": name, "path": path, "count": count}
                for name, path, count in friction
            ],
            "funnel": [
                {"name": name, "sessions": int(funnel_map.get(name, 0))}
                for name in funnel_names
            ],
        }
