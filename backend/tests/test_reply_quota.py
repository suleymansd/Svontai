from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest

from tests.test_reliability_regressions import workspace  # noqa: F401


def sources(tenant_id, conversation_id, count=2, limit=1):
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.subscription import TenantSubscription
    with SessionLocal() as db:
        subscription = db.query(TenantSubscription).filter_by(tenant_id=tenant_id).one()
        subscription.plan.message_limit = limit
        messages = [Message(conversation_id=conversation_id, sender="user", content="Test") for _ in range(count)]
        db.add_all(messages)
        db.commit()
        return [item.id for item in messages]


def test_reservations_are_idempotent_and_consumed_with_delivery(client, workspace):
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.subscription import TenantSubscription
    from app.models.reply_reservation import ReplyReservation
    from app.services.reply_quota_service import reserve_reply
    from app.services.reply_usage_service import record_delivered_reply
    _, tenant_id, _, conversation_id = workspace
    first, second = sources(tenant_id, conversation_id)
    with SessionLocal() as db:
        assert reserve_reply(db, tenant_id, first)[0]
        db.commit()
        assert reserve_reply(db, tenant_id, first)[0]
        assert not reserve_reply(db, tenant_id, second)[0]
        reply = Message(conversation_id=conversation_id, sender="bot", content="Reply")
        db.add(reply)
        assert record_delivered_reply(db, tenant_id, reply, source_message_id=first)
        db.commit()
        assert not record_delivered_reply(db, tenant_id, reply, source_message_id=first)
        assert db.get(ReplyReservation, first).state == "consumed"
        assert db.query(TenantSubscription).filter_by(tenant_id=tenant_id).one().messages_used_this_month == 1
        assert not reserve_reply(db, tenant_id, second)[0]


def test_failed_generation_releases_but_ambiguous_delivery_holds_quota(client, workspace):
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.services.reply_quota_service import reserve_reply
    from app.services.reply_delivery_guard import ReplyDeliveryGuard
    _, tenant_id, _, conversation_id = workspace
    first, second = sources(tenant_id, conversation_id)
    with SessionLocal() as db:
        db.get(Message, first).external_id = "quota-test"
        assert reserve_reply(db, tenant_id, first)[0]
        db.commit()
    guard = ReplyDeliveryGuard(conversation_id, "quota-test")
    assert guard.claim()
    guard.failed()
    with SessionLocal() as db:
        assert reserve_reply(db, tenant_id, second)[0]
        db.rollback()
        assert reserve_reply(db, tenant_id, first)[0]
        db.commit()
    assert guard.claim()
    guard.set_status("dispatching")
    guard.failed()
    with SessionLocal() as db:
        assert not reserve_reply(db, tenant_id, second)[0]


def test_reservation_rejects_other_tenant_message(client, workspace):
    from app.db.session import SessionLocal
    from app.services.reply_quota_service import reserve_reply
    from tests.test_openwa_integration import _create_tenant
    _, tenant_id, _, conversation_id = workspace
    first, _ = sources(tenant_id, conversation_id)
    _, other = _create_tenant(client, email="quota-other@example.com")
    with SessionLocal() as db:
        assert not reserve_reply(db, UUID(other), first)[0]


def test_concurrent_reservations_do_not_overspend(client, workspace):
    from app.db.session import SessionLocal
    from app.services.reply_quota_service import reserve_reply
    _, tenant_id, _, conversation_id = workspace
    with SessionLocal() as db:
        if db.get_bind().dialect.name != "postgresql":
            pytest.skip("Requires PostgreSQL row locks")
    ids = sources(tenant_id, conversation_id, count=10, limit=3)
    def attempt(message_id):
        with SessionLocal() as db:
            allowed, _ = reserve_reply(db, tenant_id, message_id)
            db.commit()
            return allowed
    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(pool.map(attempt, ids)) == 3
