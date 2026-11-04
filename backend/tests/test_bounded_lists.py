"""A12: list endpoints are bounded and page with a stable cursor."""

from datetime import timedelta
from uuid import UUID

import pytest

from tests.test_openwa_integration import _create_tenant, _headers


@pytest.fixture
def tenant(client):
    from app.db.session import SessionLocal
    from app.services.subscription_service import SubscriptionService

    token, tenant_id = _create_tenant(client)
    with SessionLocal() as db:
        if SubscriptionService(db).get_subscription(UUID(tenant_id)) is None:
            SubscriptionService(db).create_subscription(UUID(tenant_id), "free")
            db.commit()
    return _headers(token, tenant_id), UUID(tenant_id)


def _seed_appointments(tenant_id: UUID, count: int) -> None:
    from app.core.time import utc_now_naive
    from app.db.session import SessionLocal
    from app.models.appointment import Appointment

    base = utc_now_naive().replace(microsecond=0) + timedelta(days=1)
    with SessionLocal() as db:
        for index in range(count):
            # Two appointments per slot so the (starts_at, id) tie-break is exercised.
            db.add(Appointment(
                tenant_id=tenant_id,
                customer_name=f"Customer {index}",
                subject="Slot",
                starts_at=base + timedelta(minutes=30 * (index // 2)),
                duration_minutes=30,
                status="scheduled",
            ))
        db.commit()


def test_appointments_list_enforces_limit_cap(client, tenant):
    headers, tenant_id = tenant
    _seed_appointments(tenant_id, 230)

    assert client.get("/appointments", params={"limit": 201}, headers=headers).status_code == 422
    assert client.get("/appointments", params={"limit": 0}, headers=headers).status_code == 422

    default_page = client.get("/appointments", headers=headers)
    assert default_page.status_code == 200
    assert len(default_page.json()) == 100

    max_page = client.get("/appointments", params={"limit": 200}, headers=headers)
    assert len(max_page.json()) == 200


def test_appointments_cursor_pages_do_not_overlap(client, tenant):
    headers, tenant_id = tenant
    _seed_appointments(tenant_id, 25)

    seen: list[str] = []
    after_id = None
    pages = 0
    while True:
        params = {"limit": 7}
        if after_id:
            params["after_id"] = after_id
        response = client.get("/appointments", params=params, headers=headers)
        assert response.status_code == 200, response.text
        rows = response.json()
        pages += 1
        if not rows:
            break
        keys = [(row["starts_at"], row["id"]) for row in rows]
        assert keys == sorted(keys), "page must be ordered by (starts_at, id)"
        seen.extend(row["id"] for row in rows)
        after_id = rows[-1]["id"]
        if len(rows) < 7:
            break

    assert pages == 4
    assert len(seen) == 25
    assert len(set(seen)) == 25, "cursor pages must not overlap"


def test_appointments_cursor_rejects_foreign_or_unknown_id(client, tenant):
    headers, tenant_id = tenant
    _seed_appointments(tenant_id, 2)
    other_headers, other_tenant_id = tenant_fixture_for_other(client)
    _seed_appointments(other_tenant_id, 1)
    foreign_id = client.get("/appointments", headers=other_headers).json()[0]["id"]

    assert client.get("/appointments", params={"after_id": foreign_id}, headers=headers).status_code == 404
    assert client.get(
        "/appointments", params={"after_id": "00000000-0000-0000-0000-000000000000"}, headers=headers
    ).status_code == 404


def tenant_fixture_for_other(client):
    from app.db.session import SessionLocal
    from app.services.subscription_service import SubscriptionService

    token, tenant_id = _create_tenant(client, email="other-tenant@example.com")
    with SessionLocal() as db:
        if SubscriptionService(db).get_subscription(UUID(tenant_id)) is None:
            SubscriptionService(db).create_subscription(UUID(tenant_id), "free")
            db.commit()
    return _headers(token, tenant_id), UUID(tenant_id)


def test_notes_and_knowledge_lists_cap_limit_at_200(client, tenant):
    headers, tenant_id = tenant
    from app.db.session import SessionLocal
    from app.models.note import WorkspaceNote

    with SessionLocal() as db:
        for index in range(205):
            db.add(WorkspaceNote(tenant_id=tenant_id, title=f"Note {index}", content="x"))
        db.commit()

    assert client.get("/notes", params={"limit": 201}, headers=headers).status_code == 422
    assert len(client.get("/notes", headers=headers).json()) == 100
    assert len(client.get("/notes", params={"limit": 200}, headers=headers).json()) == 200
    assert len(client.get("/notes", params={"limit": 200, "skip": 200}, headers=headers).json()) == 5

    bot = client.post("/bots", json={"name": "KB", "assistant_type": "primary"}, headers=headers)
    assert bot.status_code == 201, bot.text
    assert client.get(
        f"/bots/{bot.json()['id']}/knowledge", params={"limit": 500}, headers=headers
    ).status_code == 422
