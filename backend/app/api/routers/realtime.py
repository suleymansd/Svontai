"""Authenticated tenant Server-Sent Events stream."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from time import monotonic
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.db import session as db_session
from app.dependencies.auth import (
    get_access_token_payload,
    get_current_membership,
    get_current_tenant,
    get_current_user,
    security,
)
from app.services.realtime_service import realtime_channel  # Registers SQLAlchemy listeners.
from app.services.realtime_capacity import RealtimeLease

try:
    import redis.asyncio as async_redis
except ImportError:  # pragma: no cover
    async_redis = None


router = APIRouter(prefix="/realtime", tags=["realtime"])


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}\n\n"


@dataclass(frozen=True)
class RealtimePrincipal:
    """Snapshot of who is allowed to receive a tenant stream.

    Any change to these fields (user deactivated, membership removed, role changed,
    session revoked) must end an open stream within one heartbeat.
    """

    tenant_id: str
    user_id: str
    role_id: str | None
    session_id: str | None


async def resolve_realtime_principal(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_tenant_id: UUID | None = Header(default=None, alias="X-Tenant-ID"),
) -> RealtimePrincipal:
    """Authenticate SSE without retaining a database connection for the stream lifetime.

    Reuses the regular auth dependencies so revocation rules stay in one place:
    get_current_user (active flag, lock, revoked/expired session), get_current_tenant
    (membership/suspension) and get_current_membership (role + tools:read).
    """
    db = db_session.SessionLocal()
    try:
        user = await get_current_user(credentials=credentials, db=db)
        token_payload = await get_access_token_payload(credentials=credentials)
        if user.is_admin and (token_payload.get("portal") or "tenant") != "super_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin portal session required")
        tenant = await get_current_tenant(
            current_user=user,
            token_payload=token_payload,
            db=db,
            x_tenant_id=x_tenant_id,
        )
        role_id: str | None = None
        if not user.is_admin:
            membership = await get_current_membership(current_user=user, current_tenant=tenant, db=db)
            db.refresh(membership, ["role"])
            granted = {permission.key for permission in membership.role.permissions}
            if "tools:read" not in granted:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için yetkiniz yok")
            role_id = str(membership.role_id)
        session_id = token_payload.get("sid")
        return RealtimePrincipal(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            role_id=role_id,
            session_id=str(session_id) if session_id else None,
        )
    finally:
        db.close()


async def resolve_realtime_tenant_id(
    principal: RealtimePrincipal = Depends(resolve_realtime_principal),
) -> str:
    return principal.tenant_id


@router.get("/events")
async def tenant_realtime_events(
    request: Request,
    principal: RealtimePrincipal = Depends(resolve_realtime_principal),
) -> StreamingResponse:
    tenant_id = principal.tenant_id
    heartbeat_seconds = max(1, int(settings.REALTIME_HEARTBEAT_SECONDS))
    client = None
    lease = None
    if async_redis is not None and settings.RATE_LIMIT_BACKEND == "redis":
        client = async_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True,
                                          socket_connect_timeout=2, socket_timeout=20)
        lease = RealtimeLease(client, tenant_id)
        try:
            acquired = await lease.acquire(settings.REALTIME_MAX_CONNECTIONS_PER_TENANT)
        except Exception:
            await client.aclose()
            raise HTTPException(status_code=503, detail="Canli baglanti gecici olarak kullanilamiyor.")
        if not acquired:
            await client.aclose()
            raise HTTPException(status_code=429, detail="Canli baglanti sinirina ulasildi.", headers={"Retry-After": "30"})

    async def stream():
        last_auth = monotonic()
        revocation: dict | None = None

        async def still_authorized() -> bool:
            """Re-validate the principal at most once per heartbeat.

            Returns False (and records the reason) when the user was deactivated,
            removed from the tenant, had its role changed or its session revoked.
            """
            nonlocal last_auth, revocation
            if monotonic() - last_auth < heartbeat_seconds:
                return True
            last_auth = monotonic()
            try:
                header = request.headers.get("authorization", "")
                scheme, token = header.split(" ", 1)
                current = await resolve_realtime_principal(
                    credentials=HTTPAuthorizationCredentials(scheme=scheme, credentials=token),
                    x_tenant_id=UUID(request.headers["x-tenant-id"]) if request.headers.get("x-tenant-id") else None,
                )
            except HTTPException as exc:
                revocation = {"status": exc.status_code, "reason": "auth_rejected"}
                return False
            except ValueError:
                revocation = {"status": 401, "reason": "auth_rejected"}
                return False
            if current != principal:
                revocation = {"status": 403, "reason": "principal_changed"}
                return False
            return True

        def _unauthorized_frame() -> str:
            payload = {"type": "unauthorized", "code": 4401, "tenant_id": tenant_id, **(revocation or {})}
            return _sse("unauthorized", payload)

        if client is None:
            yield _sse("ready", {"type": "ready", "tenant_id": tenant_id, "live": False})
            while not await request.is_disconnected():
                await asyncio.sleep(heartbeat_seconds)
                if not await still_authorized():
                    yield _unauthorized_frame()
                    return
                yield ": heartbeat\n\n"
            return

        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(realtime_channel(tenant_id))
            yield _sse("ready", {"type": "ready", "tenant_id": tenant_id, "live": True})
            while not await request.is_disconnected():
                if not await still_authorized():
                    yield _unauthorized_frame()
                    break
                if not await lease.renew():
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=heartbeat_seconds)
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
            try:
                await lease.release()
            finally:
                try:
                    await pubsub.aclose()
                finally:
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
