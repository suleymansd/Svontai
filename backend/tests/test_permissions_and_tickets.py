import uuid
from datetime import datetime
from app.core.time import utc_now_naive
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.dependencies.permissions import require_permissions
from app.api.routers.tickets import add_ticket_message
from app.schemas.ticket import TicketMessageCreate


@pytest.mark.asyncio
async def test_require_permissions_allows_admin():
    dep = require_permissions(["tickets:manage"])
    user = SimpleNamespace(is_admin=True)
    tenant = SimpleNamespace(id=uuid.uuid4())
    db = MagicMock()

    await dep(current_user=user, current_tenant=tenant, db=db)

    db.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_require_permissions_denies_missing(monkeypatch):
    dep = require_permissions(["tickets:manage"])
    user = SimpleNamespace(is_admin=False)
    role = SimpleNamespace(permissions=[SimpleNamespace(key="tools:read")])
    membership = SimpleNamespace(role=role)
    tenant = SimpleNamespace(id=uuid.uuid4())
    db = MagicMock()
    monkeypatch.setattr(
        "app.dependencies.permissions.get_current_membership",
        AsyncMock(return_value=membership),
    )

    with pytest.raises(HTTPException) as exc:
        await dep(current_user=user, current_tenant=tenant, db=db)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_permissions_allows_when_granted(monkeypatch):
    dep = require_permissions(["tickets:manage"])
    user = SimpleNamespace(is_admin=False)
    role = SimpleNamespace(permissions=[SimpleNamespace(key="tickets:manage")])
    membership = SimpleNamespace(role=role)
    tenant = SimpleNamespace(id=uuid.uuid4())
    db = MagicMock()
    monkeypatch.setattr(
        "app.dependencies.permissions.get_current_membership",
        AsyncMock(return_value=membership),
    )

    await dep(current_user=user, current_tenant=tenant, db=db)


@pytest.mark.asyncio
async def test_add_ticket_message_sets_staff_sender_type():
    ticket_id = uuid.uuid4()
    ticket = SimpleNamespace(id=str(ticket_id), tenant_id="tenant-1", last_activity_at=None)

    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = ticket

    db = MagicMock()
    db.query.return_value = query

    def refresh(obj):
        obj.created_at = utc_now_naive()
        if getattr(obj, "id", None) is None:
            obj.id = str(uuid.uuid4())

    db.refresh.side_effect = refresh

    current_user = SimpleNamespace(id="user-1", is_admin=True)
    current_tenant = SimpleNamespace(id="tenant-1")
    payload = TicketMessageCreate(body="Test reply")

    response = await add_ticket_message(
        ticket_id=ticket_id,
        payload=payload,
        current_user=current_user,
        current_tenant=current_tenant,
        db=db
    )

    assert response.sender_type == "staff"
    assert ticket.last_activity_at is not None
