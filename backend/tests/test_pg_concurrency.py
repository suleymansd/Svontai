"""PostgreSQL concurrency contracts (audit A20) and a readiness latency smoke (A14).

The three concurrency tests only run when ``TEST_DATABASE_URL`` points at a local
PostgreSQL database (the CI backend job sets it for the reliability lane). They use
real threads and one session per thread so row locks and ``SKIP LOCKED`` are exercised
by separate connections, not by one session pretending to be two.
"""

from __future__ import annotations

import json
import os
import statistics
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from tests.test_openwa_integration import _create_tenant

POSTGRES_URL = os.environ.get("TEST_DATABASE_URL", "")
requires_postgres = pytest.mark.skipif(
    not POSTGRES_URL.startswith("postgresql"),
    reason="Requires TEST_DATABASE_URL pointing at a local PostgreSQL test database",
)


@pytest.fixture
def tenant_id(client) -> UUID:
    from app.db.session import SessionLocal

    _, raw_tenant_id = _create_tenant(client, email=f"pg-{uuid4().hex[:8]}@example.com")
    with SessionLocal() as db:
        assert db.get_bind().dialect.name == "postgresql", "fixture must be bound to PostgreSQL"
    return UUID(raw_tenant_id)


@requires_postgres
def test_overlapping_manual_bookings_only_one_succeeds(tenant_id):
    from fastapi import HTTPException
    from app.core.time import utc_now_naive
    from app.db.session import SessionLocal
    from app.models.appointment import Appointment
    from app.services.appointment_booking_guard import lock_booking_calendar, require_available_interval

    start = utc_now_naive() + timedelta(days=3)
    barrier = Barrier(2)

    def book(label: str) -> int:
        with SessionLocal() as db:
            barrier.wait(timeout=10)
            try:
                lock_booking_calendar(db, tenant_id)
                require_available_interval(db, tenant_id, start, 60)
                db.add(Appointment(tenant_id=tenant_id, customer_name=label, subject="Overlap", starts_at=start, duration_minutes=60))
                db.commit()
                return 201
            except HTTPException as exc:
                db.rollback()
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(book, ["first", "second"]))
    assert outcomes == [201, 409], outcomes

    with SessionLocal() as db:
        stored = db.query(Appointment).filter(Appointment.tenant_id == tenant_id, Appointment.starts_at == start).count()
    assert stored == 1


@requires_postgres
def test_parallel_usage_increments_are_not_lost(tenant_id):
    from app.db.session import SessionLocal
    from app.services.usage_counter_service import UsageCounterService

    increments = 50
    workers = 10
    period_key = "2099-01"
    barrier = Barrier(workers)

    def increment(index: int) -> None:
        with SessionLocal() as db:
            if index < workers:
                barrier.wait(timeout=10)
            UsageCounterService(db).increment_message_count(tenant_id, period_key=period_key)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(increment, range(increments)))

    with SessionLocal() as db:
        counter = UsageCounterService(db).get_or_create(tenant_id, period_key=period_key)
        assert counter.message_count == increments
        rows = db.execute(
            text(
                "SELECT count(*) FROM tenant_usage_counters WHERE tenant_id = :tenant_id AND period_key = :period_key"
            ),
            {"tenant_id": tenant_id, "period_key": period_key},
        ).scalar_one()
    assert rows == 1, "get_or_create must not create duplicate counters under contention"


@requires_postgres
def test_two_workers_claim_the_same_inbox_event_once(tenant_id):
    from app.db.session import SessionLocal
    from app.services.webhook_inbox_service import WebhookInboxService

    payload = {"event": "message.received", "deliveryId": uuid4().hex, "data": {"body": "claim-race"}}
    body = json.dumps(payload, separators=(",", ":")).encode()
    with SessionLocal() as db:
        row, created = WebhookInboxService(db, owner="setup").enqueue(
            provider="openwa", body=body, payload=payload, event_type="message.received", tenant_id=tenant_id,
        )
        assert created
        event_id = row.id

    barrier = Barrier(2)

    def claim(owner: str) -> list:
        with SessionLocal() as db:
            barrier.wait(timeout=10)
            return [claimed for claimed in WebhookInboxService(db, owner=owner).claim_batch(limit=20) if claimed == event_id]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["worker-a", "worker-b"]))
    winners = [result for result in results if result]
    assert len(winners) == 1, results

    with SessionLocal() as db:
        from app.models.webhook_inbox import WebhookInboxEvent

        stored = db.get(WebhookInboxEvent, event_id)
        assert stored.status == "processing"
        assert stored.attempt_count == 1
        assert stored.lock_owner in {"worker-a", "worker-b"}


def test_health_ready_latency_smoke(client, record_property):
    """A14: 200 sequential readiness probes; p95 budget 250 ms.

    Informational by default (prints and records the percentile, warns when over
    budget) so a slow CI runner cannot fail the suite. Set HEALTH_SMOKE_STRICT=1 to
    turn the budget into an assertion.
    """
    budget_ms = 250.0
    samples_ms: list[float] = []
    statuses: dict[int, int] = {}
    for _ in range(200):
        started = time.perf_counter()
        response = client.get("/health/ready")
        samples_ms.append((time.perf_counter() - started) * 1000)
        statuses[response.status_code] = statuses.get(response.status_code, 0) + 1

    assert set(statuses) <= {200, 503}, statuses
    assert statuses.get(200, 0) == 200, f"readiness must answer 200 under the test fixture: {statuses}"

    ordered = sorted(samples_ms)
    p50 = statistics.median(ordered)
    p95 = ordered[int(len(ordered) * 0.95) - 1]
    summary = f"health/ready x{len(ordered)}: p50={p50:.1f}ms p95={p95:.1f}ms max={ordered[-1]:.1f}ms budget={budget_ms:.0f}ms"
    print(summary)
    record_property("health_ready_p95_ms", round(p95, 1))
    if p95 >= budget_ms:
        if os.environ.get("HEALTH_SMOKE_STRICT") == "1":
            pytest.fail(summary)
        warnings.warn(f"readiness p95 over budget (informational): {summary}", stacklevel=1)
