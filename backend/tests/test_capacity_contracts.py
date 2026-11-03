"""Local multi-tenant database load contract, not a provider capacity guarantee."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

import pytest

from tests.test_reliability_regressions import workspace  # noqa: F401


def test_100_tenant_concurrent_quota_isolation(client, workspace):
    from app.db.session import SessionLocal
    from app.models.bot import Bot
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.subscription import TenantSubscription
    from app.models.tenant import Tenant
    from app.services.reply_quota_service import reserve_reply
    _, tenant_id, _, _ = workspace
    requests = []
    with SessionLocal() as db:
        if db.get_bind().dialect.name != "postgresql":
            pytest.skip("Capacity contract needs local PostgreSQL")
        owner_id = db.get(Tenant, tenant_id).owner_id
        plan = db.query(TenantSubscription).filter_by(tenant_id=tenant_id).one().plan
        plan.message_limit = 1
        for index in range(100):
            tenant = Tenant(owner_id=owner_id, name=f"Capacity {index}")
            db.add(tenant)
            db.flush()
            bot = Bot(tenant_id=tenant.id, name="Capacity")
            db.add(bot)
            db.flush()
            conversation = Conversation(bot_id=bot.id, external_user_id="test", source="whatsapp")
            db.add(conversation)
            db.add(TenantSubscription(tenant_id=tenant.id, plan_id=plan.id, status="active"))
            db.flush()
            for _ in range(3):
                message = Message(conversation_id=conversation.id, sender="user", content="Synthetic capacity test")
                db.add(message)
                db.flush()
                requests.append((tenant.id, message.id))
        db.commit()
    def attempt(pair):
        started = perf_counter()
        with SessionLocal() as db:
            allowed, _ = reserve_reply(db, *pair)
            db.commit()
            return pair[0], allowed, perf_counter() - started
    started = perf_counter()
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, requests))
    granted = Counter(tenant for tenant, allowed, _ in results if allowed)
    assert len(granted) == 100 and set(granted.values()) == {1}
    timings = sorted(item[2] for item in results)
    print(f"100 tenants / 300 reservations / 12 concurrent DB workers: elapsed={perf_counter()-started:.3f}s p95={timings[284]:.3f}s")
