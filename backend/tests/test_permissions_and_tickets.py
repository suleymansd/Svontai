import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.dependencies.permissions import require_permissions
from app.api.routers.tickets import add_ticket_message
from app.schemas.ticket import TicketMessageCreate


@pytest.mark.asyncio
async def test_require_permissions_allows_admin():
    dep = require_permissions(["tickets:manage"])
    user = SimpleNamespace(is_admin=True)
    membership = SimpleNamespace(role=SimpleNamespace(permissions=[]))
    db = MagicMock()

    await dep(current_user=user, membership=membership, db=db)

    db.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_require_permissions_denies_missing():
    dep = require_permissions(["tickets:manage"])
    user = SimpleNamespace(is_admin=False)
    role = SimpleNamespace(permissions=[SimpleNamespace(key="tools:read")])
    membership = SimpleNamespace(role=role)
    db = MagicMock()

    with pytest.raises(HTTPException) as exc:
        await dep(current_user=user, membership=membership, db=db)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_permissions_allows_when_granted():
    dep = require_permissions(["tickets:manage"])
    user = SimpleNamespace(is_admin=False)
    role = SimpleNamespace(permissions=[SimpleNamespace(key="tickets:manage")])
    membership = SimpleNamespace(role=role)
    db = MagicMock()

    await dep(current_user=user, membership=membership, db=db)


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
        obj.created_at = datetime.utcnow()
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
