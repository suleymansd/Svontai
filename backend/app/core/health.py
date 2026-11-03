"""Liveness and dependency readiness checks."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import inspect, text

from app.core.config import settings


def _release_sha() -> str:
    for name in ("RAILWAY_GIT_COMMIT_SHA", "GIT_COMMIT_SHA", "SOURCE_VERSION"):
        value = str(os.getenv(name) or "").strip()
        if value:
            return value[:64]
    return "unknown"


def _check_database() -> dict[str, Any]:
    from app.db import session as session_module
    from app.models.autopilot import ScheduledJob

    db = session_module.SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        inspector = inspect(db.get_bind())
        migration_heads = (
            list(db.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars())
            if inspector.has_table("alembic_version")
            else []
        )
        heartbeat = (
            db.query(ScheduledJob).filter(ScheduledJob.name == "worker_heartbeat").first()
            if inspector.has_table("scheduled_jobs")
            else None
        )
        worker_meta = dict(heartbeat.meta_json or {}) if heartbeat else {}
        last_success = heartbeat.last_success_at if heartbeat else None
        if last_success and last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=timezone.utc)
        age_seconds = (
            max(0, int((datetime.now(timezone.utc) - last_success).total_seconds()))
            if last_success
            else None
        )
        pipeline_health = None
        if inspector.has_table("operator_deliveries"):
            from app.services.delivery_health_service import delivery_health
            pipeline_health = delivery_health(db)
        return {
            "migration_heads": migration_heads,
            "worker_commit": str(worker_meta.get("release_sha") or "unknown"),
            "worker_heartbeat_age_seconds": age_seconds,
            "pipeline_health": pipeline_health,
        }
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


def worker_heartbeat_status(age_seconds: int | None, max_age_seconds: int | None = None) -> str:
    """Classify the worker heartbeat as ``ok``, ``stale`` or ``missing``."""
    if age_seconds is None:
        return "missing"
    limit = settings.WORKER_HEARTBEAT_MAX_AGE_SECONDS if max_age_seconds is None else max_age_seconds
    if limit > 0 and age_seconds > limit:
        return "stale"
    return "ok"


def _worker_blocks_readiness(status: str) -> bool:
    """A stale heartbeat always fails readiness; a heartbeat that never existed only
    does so in production, where a worker is mandatory (dev/test may run API only)."""
    if settings.WORKER_HEARTBEAT_MAX_AGE_SECONDS <= 0:
        return False
    if status == "stale":
        return True
    return status == "missing" and settings.ENVIRONMENT == "prod"


async def readiness_status() -> tuple[bool, dict[str, Any]]:
    """Check dependencies required to safely accept customer traffic."""
    components: dict[str, str] = {}
    deployment: dict[str, Any] = {
        "api_commit": _release_sha(),
        "worker_commit": "unknown",
        "worker_heartbeat_age_seconds": None,
        "migration_heads": [],
    }

    try:
        database_status = await asyncio.wait_for(asyncio.to_thread(_check_database), timeout=5)
        components["database"] = "ok"
        deployment.update(database_status)
        components["worker"] = worker_heartbeat_status(deployment.get("worker_heartbeat_age_seconds"))
    except Exception:
        components["database"] = "unavailable"
        components["worker"] = "unknown"

    if settings.RATE_LIMIT_BACKEND == "redis":
        try:
            await asyncio.wait_for(asyncio.to_thread(_check_redis), timeout=4)
            components["redis"] = "ok"
        except Exception:
            components["redis"] = "unavailable"
    else:
        components["redis"] = "not_required"

    ready = all(
        value in {"ok", "not_required"} for name, value in components.items() if name != "worker"
    ) and not _worker_blocks_readiness(components["worker"])
    deployment["worker_heartbeat_max_age_seconds"] = settings.WORKER_HEARTBEAT_MAX_AGE_SECONDS
    return ready, {
        "status": "ready" if ready else "not_ready",
        "environment": settings.ENVIRONMENT,
        "components": components,
        "deployment": deployment,
    }
