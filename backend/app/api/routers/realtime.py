"""Authenticated tenant Server-Sent Events stream."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.db.session import SessionLocal
from app.dependencies.auth import (
    get_access_token_payload,
    get_current_membership,
    get_current_tenant,
    get_current_user,
    security,
)
from app.services.realtime_service import realtime_channel  # Registers SQLAlchemy listeners.

try:
    import redis.asyncio as async_redis
except ImportError:  # pragma: no cover
    async_redis = None


router = APIRouter(prefix="/realtime", tags=["realtime"])


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}\n\n"


async def resolve_realtime_tenant_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_tenant_id: UUID | None = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    """Authenticate SSE without retaining a database connection for the stream lifetime."""
    db = SessionLocal()
    try:
        user = await get_current_user(credentials=credentials, db=db)
        token_payload = await get_access_token_payload(credentials=credentials)
        if user.is_admin and (token_payload.get("portal") or "tenant") != "super_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin portal session required")
        tenant = await get_current_tenant(current_user=user, db=db, x_tenant_id=x_tenant_id)
        if not user.is_admin:
            membership = await get_current_membership(current_user=user, current_tenant=tenant, db=db)
            db.refresh(membership, ["role"])
            granted = {permission.key for permission in membership.role.permissions}
            if "tools:read" not in granted:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için yetkiniz yok")
        return str(tenant.id)
    finally:
        db.close()


@router.get("/events")
async def tenant_realtime_events(
    request: Request,
    tenant_id: str = Depends(resolve_realtime_tenant_id),
) -> StreamingResponse:
    async def stream():
        yield _sse("ready", {"tenant_id": tenant_id})
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
            await pubsub.subscribe(realtime_channel(tenant_id))
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
            await pubsub.unsubscribe(realtime_channel(tenant_id))
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
