"""Audit A09: usage increments are idempotent and count correctly under concurrency."""

from concurrent.futures import ThreadPoolExecutor

from tests.test_reliability_regressions import workspace  # noqa: F401


def _counter(tenant_id):
    from app.db.session import SessionLocal
    from app.services.usage_counter_service import UsageCounterService
    with SessionLocal() as db:
        return UsageCounterService(db).get_or_create(tenant_id)


def test_same_idempotency_key_increments_once(client, workspace):
    from app.db.session import SessionLocal
    from app.models.usage_ledger import UsageLedgerEntry
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, _, _ = workspace
    with SessionLocal() as db:
        service = UsageCounterService(db)
        service.increment(tenant_id=tenant_id, message_count=1, tool_calls=2, idempotency_key="ai_reply:dup")
        service.increment(tenant_id=tenant_id, message_count=1, tool_calls=2, idempotency_key="ai_reply:dup")
        service.increment(tenant_id=tenant_id, message_count=1, idempotency_key="ai_reply:other")
        service.increment(tenant_id=tenant_id, message_count=1)  # legacy call without a key still counts
        assert db.query(UsageLedgerEntry).filter_by(tenant_id=tenant_id).count() == 2
        assert db.get(UsageLedgerEntry, db.query(UsageLedgerEntry.id).filter_by(
            idempotency_key="ai_reply:dup").scalar()).amounts_json == {"message_count": 1, "tool_calls": 2}
    counter = _counter(tenant_id)
    assert counter.message_count == 3
    assert counter.tool_calls == 2


def test_replayed_key_survives_separate_sessions_and_commit_false(client, workspace):
    from app.db.session import SessionLocal
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, _, _ = workspace
    for _ in range(3):
        with SessionLocal() as db:
            UsageCounterService(db).increment(tenant_id=tenant_id, voice_seconds=90, commit=False,
                                              idempotency_key="voice_seconds:call-1")
            db.commit()
    assert _counter(tenant_id).voice_seconds == 90


def test_fifty_concurrent_increments_with_distinct_keys_count_fifty(client, workspace):
    from app.db.session import SessionLocal
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, _, _ = workspace

    def attempt(index):
        with SessionLocal() as db:
            UsageCounterService(db).increment(tenant_id=tenant_id, workflow_runs=1,
                                              idempotency_key=f"workflow_run:{index}")
        return 1

    with SessionLocal() as db:
        concurrent = db.get_bind().dialect.name == "postgresql"
    if concurrent:
        with ThreadPoolExecutor(max_workers=10) as pool:
            assert sum(pool.map(attempt, range(50))) == 50
    else:  # the in-memory SQLite test engine shares one connection, so threads would serialize anyway
        assert sum(map(attempt, range(50))) == 50
    assert _counter(tenant_id).workflow_runs == 50


def test_delivered_reply_metering_uses_reservation_key(client, workspace):
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.usage_ledger import UsageLedgerEntry
    from app.services.reply_usage_service import record_delivered_reply
    _, tenant_id, _, conversation_id = workspace
    with SessionLocal() as db:
        source = Message(conversation_id=conversation_id, sender="user", content="Soru")
        reply = Message(conversation_id=conversation_id, sender="bot", content="Yanit")
        db.add_all([source, reply])
        db.commit()
        assert record_delivered_reply(db, tenant_id, reply, source_message_id=source.id)
        db.commit()
        assert db.query(UsageLedgerEntry).filter_by(idempotency_key=f"ai_reply:{source.id}").count() == 1
    assert _counter(tenant_id).message_count == 1
