"""Authenticated tenant Server-Sent Events stream."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.dependencies.auth import get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.services.realtime_service import realtime_channel  # Registers SQLAlchemy listeners.

try:
    import redis.asyncio as async_redis
except ImportError:  # pragma: no cover
    async_redis = None


router = APIRouter(prefix="/realtime", tags=["realtime"])


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}\n\n"


@router.get("/events")
async def tenant_realtime_events(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    _: None = Depends(require_permissions(["tools:read"])),
) -> StreamingResponse:
    async def stream():
        yield _sse("ready", {"tenant_id": str(tenant.id)})
        if async_redis is None or settings.RATE_LIMIT_BACKEND != "redis":
            while not await request.is_disconnected():
                await asyncio.sleep(15)
                yield ": heartbeat\n\n"
            return

        client = async_redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=20,
        )
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(realtime_channel(tenant.id))
            while not await request.is_disconnected():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15)
                if message and message.get("type") == "message":
                    raw_data = message.get("data")
                    try:
                        payload = json.loads(raw_data)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    yield _sse("update", payload)
                else:
                    yield ": heartbeat\n\n"
        finally:
            await pubsub.unsubscribe(realtime_channel(tenant.id))
            await pubsub.aclose()
            await client.aclose()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
