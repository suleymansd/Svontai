"""Liveness and dependency readiness checks."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import text

from app.core.config import settings


def _check_database() -> None:
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()


def _check_redis() -> None:
    import redis

    client = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        if client.ping() is not True:
            raise RuntimeError("Redis ping failed")
    finally:
        client.close()


async def readiness_status() -> tuple[bool, dict[str, Any]]:
    """Check dependencies required to safely accept customer traffic."""
    components: dict[str, str] = {}

    try:
        await asyncio.wait_for(asyncio.to_thread(_check_database), timeout=5)
        components["database"] = "ok"
    except Exception:
        components["database"] = "unavailable"

    if settings.RATE_LIMIT_BACKEND == "redis":
        try:
            await asyncio.wait_for(asyncio.to_thread(_check_redis), timeout=4)
            components["redis"] = "ok"
        except Exception:
            components["redis"] = "unavailable"
    else:
        components["redis"] = "not_required"

    ready = all(value in {"ok", "not_required"} for value in components.values())
    return ready, {
        "status": "ready" if ready else "not_ready",
        "environment": settings.ENVIRONMENT,
        "components": components,
    }
