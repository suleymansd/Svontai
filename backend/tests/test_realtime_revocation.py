"""A17: open realtime streams end within one heartbeat once the principal is revoked.

Starlette's TestClient buffers a streaming response until the app finishes, so the
route's StreamingResponse body iterator is driven directly inside an asyncio loop.
"""

import asyncio
import json
import uuid
from time import monotonic
from uuid import UUID

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from app.core.time import utc_now_naive
from tests.test_product_realtime_retention import _headers, _tenant_session


HEARTBEAT_SECONDS = 1


@pytest.fixture
def fast_heartbeat(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "REALTIME_HEARTBEAT_SECONDS", HEARTBEAT_SECONDS)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "memory")


def _frames(chunk: str) -> list[dict]:
    """Parse SSE frames of one chunk into {event, data} dicts (comments become event='comment')."""
    parsed = []
    for frame in chunk.split("\n\n"):
        if not frame.strip():
            continue
        if frame.startswith(":"):
            parsed.append({"event": "comment", "data": None})
            continue
        event = next((line[6:].strip() for line in frame.split("\n") if line.startswith("event:")), None)
        data = "\n".join(line[5:].strip() for line in frame.split("\n") if line.startswith("data:"))
        parsed.append({"event": event, "data": json.loads(data) if data else None})
    return parsed


def _run_stream_until_revoked(headers: dict, revoke) -> dict:
    from app.api.routers.realtime import resolve_realtime_principal, tenant_realtime_events

    async def scenario():
        scheme, token = headers["Authorization"].split(" ", 1)
        principal = await resolve_realtime_principal(
            credentials=HTTPAuthorizationCredentials(scheme=scheme, credentials=token),
            x_tenant_id=UUID(headers["X-Tenant-ID"]),
        )
        never = asyncio.Event()

        async def receive():
            await never.wait()  # client never disconnects on its own
            return {"type": "http.disconnect"}

        scope = {
            "type": "http", "method": "GET", "path": "/realtime/events", "query_string": b"",
            "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        }
        response = await tenant_realtime_events(Request(scope, receive), principal)
        iterator = response.body_iterator.__aiter__()

        first = _frames(await iterator.__anext__())
        assert first[0]["event"] == "ready" and first[0]["data"]["type"] == "ready"

        await asyncio.to_thread(revoke)
        started = monotonic()
        heartbeats = 0
        unauthorized = None
        while unauthorized is None:
            chunk = await asyncio.wait_for(iterator.__anext__(), timeout=HEARTBEAT_SECONDS * 4)
            for frame in _frames(chunk):
                if frame["event"] == "comment":
                    heartbeats += 1
                elif frame["event"] == "unauthorized":
                    unauthorized = frame["data"]
            assert heartbeats <= 1, "stream kept heartbeating after revocation"
        elapsed = monotonic() - started
        assert elapsed < HEARTBEAT_SECONDS * 3, f"revocation took {elapsed:.1f}s"

        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(iterator.__anext__(), timeout=HEARTBEAT_SECONDS * 2)
        return unauthorized

    payload = asyncio.run(scenario())
    assert payload["type"] == "unauthorized"
    assert payload["code"] == 4401
    return payload


def test_stream_ends_when_user_is_deactivated(client, fast_heartbeat):
    from app.db.session import SessionLocal
    from app.models.user import User

    token, tenant_id = _tenant_session(client, "realtime-deactivate@example.com")

    def revoke():
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "realtime-deactivate@example.com").one()
            user.is_active = False
            db.commit()

    payload = _run_stream_until_revoked(_headers(token, tenant_id), revoke)
    assert payload["status"] == 403
    assert payload["reason"] == "auth_rejected"


def test_stream_ends_when_session_is_revoked(client, fast_heartbeat):
    from app.db.session import SessionLocal
    from app.models.session import UserSession
    from app.models.user import User

    token, tenant_id = _tenant_session(client, "realtime-session@example.com")

    def revoke():
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "realtime-session@example.com").one()
            sessions = db.query(UserSession).filter(UserSession.user_id == user.id).all()
            assert sessions, "login must have created a tracked session"
            for session in sessions:
                session.revoked_at = utc_now_naive()
            db.commit()

    payload = _run_stream_until_revoked(_headers(token, tenant_id), revoke)
    assert payload["status"] == 401


def test_stream_ends_when_role_changes(client, fast_heartbeat):
    from app.db.session import SessionLocal
    from app.models.tenant_membership import TenantMembership
    from app.models.user import User
    from app.services.rbac_service import RbacService

    token, tenant_id = _tenant_session(client, "realtime-role@example.com")
    headers = _headers(token, tenant_id)
    assert client.get("/data-retention", headers=headers).status_code == 200  # ensures owner membership exists

    def change_role():
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "realtime-role@example.com").one()
            membership = db.query(TenantMembership).filter(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == uuid.UUID(tenant_id),
            ).one()
            manager = RbacService(db).get_role_by_name("manager")
            assert manager is not None and manager.id != membership.role_id
            membership.role_id = manager.id
            db.commit()

    payload = _run_stream_until_revoked(headers, change_role)
    assert payload["reason"] == "principal_changed"


def test_stream_ends_when_membership_is_removed(client, fast_heartbeat):
    from app.db.session import SessionLocal
    from app.models.tenant import Tenant
    from app.models.tenant_membership import TenantMembership
    from app.models.user import User

    token, tenant_id = _tenant_session(client, "realtime-member@example.com")
    headers = _headers(token, tenant_id)
    assert client.get("/data-retention", headers=headers).status_code == 200

    def remove_membership():
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "realtime-member@example.com").one()
            tenant = db.get(Tenant, uuid.UUID(tenant_id))
            other = User(
                email="realtime-new-owner@example.com", full_name="New owner", password_hash="x",
                is_active=True, email_verified=True,
            )
            db.add(other)
            db.flush()
            tenant.owner_id = other.id  # user is no longer owner...
            db.query(TenantMembership).filter(  # ...and no longer a member
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == tenant.id,
            ).delete(synchronize_session=False)
            db.commit()

    payload = _run_stream_until_revoked(headers, remove_membership)
    assert payload["status"] == 403
    assert payload["reason"] == "auth_rejected"
