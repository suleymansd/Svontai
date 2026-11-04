"""Audit A13: daily AI token budgets, per-call token metering, distributed contact limit."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from tests.test_reliability_regressions import workspace  # noqa: F401


class _FakeRedis:
    """Minimal INCRBY/TTL/EXPIRE/MGET model of the two Lua paths the service uses."""

    def __init__(self):
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def eval(self, _script, _key_count, key, amount, ttl):
        self.values[key] = self.values.get(key, 0) + int(amount)
        self.ttls.setdefault(key, int(ttl))
        return self.values[key]

    def mget(self, keys):
        return [self.values.get(key) for key in keys]


def _redis_service(monkeypatch, fake):
    from app.services import ai_budget_service as module
    monkeypatch.setattr(module.settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(module, "redis", object())
    service = module.AIBudgetService()
    service._redis_client = fake
    return service


def _usage_response(prompt_tokens=120, completion_tokens=30, text="Merhaba, yardımcı olabilirim."):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def _metered_service(monkeypatch, response):
    from app.services.ai_service import AIService
    service = AIService()
    create = AsyncMock(return_value=response)
    monkeypatch.setattr(service, "_get_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(service, "_check_rate_limit", lambda *args: (True, "ok"))
    return service, create


def test_budget_defaults_are_conservative():
    from app.core.config import Settings
    assert Settings.model_fields["AI_DAILY_TOKEN_BUDGET_PER_TENANT"].default == 200000
    assert Settings.model_fields["AI_DAILY_TOKEN_BUDGET_GLOBAL"].default == 1000000


def test_redis_counters_share_tenant_and_global_totals_with_ttl_to_midnight(monkeypatch):
    from app.services import ai_budget_service as module
    fake = _FakeRedis()
    service = _redis_service(monkeypatch, fake)
    monkeypatch.setattr(module.settings, "AI_DAILY_TOKEN_BUDGET_PER_TENANT", 150)
    monkeypatch.setattr(module.settings, "AI_DAILY_TOKEN_BUDGET_GLOBAL", 10_000)
    tenant_a, tenant_b = uuid4(), uuid4()
    db_writes = []
    monkeypatch.setattr(service, "_record_db", lambda *args: db_writes.append(args))

    service.record(tenant_a, 100, 20)
    assert service.usage_today(tenant_a) == (120, 120)
    service.check(tenant_a)
    service.record(tenant_a, 30, 0)
    assert len(db_writes) == 2  # the durable monthly counters are always written too
    assert service.usage_today(tenant_a) == (150, 150)
    with pytest.raises(module.AIBudgetExceeded) as exc:
        service.check(tenant_a)
    assert exc.value.scope == "tenant"
    service.check(tenant_b)  # another tenant is unaffected until the global cap
    day = module.utc_day_key()
    tenant_key, global_key = service._keys(tenant_a, day)
    assert set(fake.values) == {tenant_key, global_key}
    assert 60 <= fake.ttls[global_key] <= 86_400
    assert fake.ttls[global_key] == fake.ttls[tenant_key]

    monkeypatch.setattr(module.settings, "AI_DAILY_TOKEN_BUDGET_GLOBAL", 150)
    with pytest.raises(module.AIBudgetExceeded) as exc:
        service.check(tenant_b)
    assert exc.value.scope == "global"


def test_database_fallback_tracks_monthly_tokens_and_rolls_the_day(client, workspace, monkeypatch):
    from app.db.session import SessionLocal
    from app.services import ai_budget_service as module
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, _, _ = workspace
    monkeypatch.setattr(module.settings, "RATE_LIMIT_BACKEND", "memory")
    service = module.AIBudgetService()
    service.record(tenant_id, 100, 25)
    service.record(tenant_id, 50, 5)
    with SessionLocal() as db:
        counter = UsageCounterService(db).get_or_create(tenant_id)
        assert counter.extra_json["ai_input_tokens"] == 150
        assert counter.extra_json["ai_output_tokens"] == 30
        assert counter.extra_json["ai_calls"] == 2
        assert counter.extra_json["ai_tokens_today"] == {"day": module.utc_day_key(), "tokens": 180}
    assert service.usage_today(tenant_id) == (180, 180)
    assert service.usage_today(None) == (0, 180)
    monkeypatch.setattr(module.settings, "AI_DAILY_TOKEN_BUDGET_PER_TENANT", 180)
    with pytest.raises(module.AIBudgetExceeded):
        service.check(tenant_id)
    with SessionLocal() as db:  # a new UTC day starts from zero but keeps the monthly totals
        UsageCounterService(db).add_ai_tokens(tenant_id, input_tokens=7, output_tokens=1, day="2099-01-01")
        counter = UsageCounterService(db).get_or_create(tenant_id, period_key="2099-01")
        assert counter.extra_json["ai_tokens_today"] == {"day": "2099-01-01", "tokens": 8}
        assert UsageCounterService(db).ai_tokens_today(tenant_id, "2099-01-01") == (8, 8)


def test_generate_reply_records_provider_usage(client, workspace, monkeypatch):
    from app.db.session import SessionLocal
    from app.models.bot import Bot
    from app.models.conversation import Conversation
    from app.services import ai_budget_service as module
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, bot_id, conversation_id = workspace
    monkeypatch.setattr(module.settings, "RATE_LIMIT_BACKEND", "memory")
    service, create = _metered_service(monkeypatch, _usage_response(120, 30))
    with SessionLocal() as db:
        reply = asyncio.run(service.generate_reply(db.get(Bot, bot_id), [], db.get(Conversation, conversation_id), "Fiyat nedir?"))
    assert reply.startswith("Merhaba")
    create.assert_awaited_once()
    with SessionLocal() as db:
        extra = UsageCounterService(db).get_or_create(tenant_id).extra_json
    assert (extra["ai_input_tokens"], extra["ai_output_tokens"]) == (120, 30)


def test_generate_reply_estimates_tokens_when_provider_omits_usage(client, workspace, monkeypatch):
    from app.db.session import SessionLocal
    from app.models.bot import Bot
    from app.models.conversation import Conversation
    from app.services import ai_budget_service as module
    from app.services.usage_counter_service import UsageCounterService
    _, tenant_id, bot_id, conversation_id = workspace
    monkeypatch.setattr(module.settings, "RATE_LIMIT_BACKEND", "memory")
    bare = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="x" * 400))])
    service, _ = _metered_service(monkeypatch, bare)
    with SessionLocal() as db:
        asyncio.run(service.generate_reply(db.get(Bot, bot_id), [], db.get(Conversation, conversation_id), "Soru"))
        extra = UsageCounterService(db).get_or_create(tenant_id).extra_json
    assert extra["ai_output_tokens"] == 100
    assert extra["ai_input_tokens"] > 0


def test_generate_reply_and_generate_text_skip_model_when_budget_exhausted(client, workspace, monkeypatch):
    from app.db.session import SessionLocal
    from app.models.bot import Bot
    from app.models.conversation import Conversation
    from app.services import ai_budget_service as module
    _, tenant_id, bot_id, conversation_id = workspace
    monkeypatch.setattr(module.settings, "RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr(module.settings, "AI_DAILY_TOKEN_BUDGET_PER_TENANT", 100)
    module.ai_budget_service.record(tenant_id, 90, 10)
    service, create = _metered_service(monkeypatch, _usage_response())
    with SessionLocal() as db:
        bot, conversation = db.get(Bot, bot_id), db.get(Conversation, conversation_id)
        with pytest.raises(module.AIBudgetExceeded):
            asyncio.run(service.generate_reply(bot, [], conversation, "Soru", raise_on_provider_error=False))
        with pytest.raises(module.AIBudgetExceeded):
            asyncio.run(service.generate_text(system_prompt="s", user_text="u", tenant_id=tenant_id))
        voice = asyncio.run(service.generate_voice_reply(bot=bot, knowledge_items=[], user_text="Soru", transcript=[]))
    assert "yanıt oluşturamıyorum" in voice
    create.assert_not_awaited()


def _inbound(tenant_id, conversation_id, external_id):
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.services.reply_quota_service import reserve_reply
    with SessionLocal() as db:
        message = Message(conversation_id=conversation_id, sender="user", content="Randevu", external_id=external_id)
        db.add(message)
        db.commit()
        assert reserve_reply(db, tenant_id, message.id)[0]
        db.commit()
        return message.id


def test_webhook_budget_exhaustion_routes_to_operator_without_calling_model(client, workspace, monkeypatch):
    from app.api.routers import whatsapp_webhook
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.reply_reservation import ReplyReservation
    from app.models.conversation import Conversation
    from app.models.system_event import SystemEvent
    from app.models.ticket import Ticket
    from app.models.whatsapp_account import WhatsAppAccount
    from app.services import ai_budget_service as module
    from app.services.ai_service import ai_service
    from app.services.whatsapp_gateway_service import whatsapp_gateway_service
    _, tenant_id, bot_id, conversation_id = workspace
    monkeypatch.setattr(module.settings, "RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr(module.settings, "AI_DAILY_TOKEN_BUDGET_PER_TENANT", 100)
    module.ai_budget_service.record(tenant_id, 100, 0)
    create = AsyncMock(return_value=_usage_response())
    monkeypatch.setattr(ai_service, "_get_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    send_text = AsyncMock(return_value={"message_id": "wamid.sent"})
    monkeypatch.setattr(whatsapp_gateway_service, "send_text", send_text)
    push = AsyncMock()
    monkeypatch.setattr(whatsapp_webhook, "send_tenant_push_notification", push)
    with SessionLocal() as db:
        db.add(WhatsAppAccount(tenant_id=tenant_id, provider="meta", phone_number_id="pn-1", display_phone_number="+90555",
                               token_status="active", webhook_status="verified", is_active=True, is_verified=True))
        db.commit()

    def run(external_id):
        return asyncio.run(whatsapp_webhook.process_whatsapp_reply_in_background(
            tenant_id=tenant_id, bot_id=bot_id, conversation_id=conversation_id, account_phone_number_id="pn-1",
            provider="meta", from_number="905551112233", to_number="pn-1", message_content="Randevu",
            message_id=external_id, timestamp="1", correlation_id="corr", contact_name=None, raw_payload=None,
            use_n8n=False, n8n_workflow_id=None,
        ))

    first = _inbound(tenant_id, conversation_id, "wamid.budget-1")
    second = _inbound(tenant_id, conversation_id, "wamid.budget-2")
    run("wamid.budget-1")
    run("wamid.budget-2")
    run("wamid.budget-1")  # redelivery of an already handled inbound is a no-op

    create.assert_not_awaited()
    send_text.assert_not_awaited()
    with SessionLocal() as db:
        assert db.query(Message).filter(Message.conversation_id == conversation_id, Message.sender == "bot").count() == 0
        assert db.get(ReplyReservation, first).state == "budget_exceeded"
        # the handoff paused the conversation, so the second inbound never reached the model path
        assert db.get(ReplyReservation, second).state == "released"
        assert db.query(ReplyReservation).filter_by(tenant_id=tenant_id, state="reserved").count() == 0
        inbound = db.get(Message, first)
        assert inbound.raw_payload["reply_delivery"]["outcome"] == "budget_exceeded"
        assert inbound.raw_payload["reply_delivery"]["status"] == "completed"
        events = db.query(SystemEvent).filter_by(code="AI_BUDGET_EXCEEDED", tenant_id=str(tenant_id)).all()
        assert len(events) == 1
        assert events[0].meta_json["scope"] == "tenant"
        conversation = db.get(Conversation, conversation_id)
        assert conversation.is_ai_paused and conversation.status == "waiting"
        assert db.query(Ticket).filter(Ticket.tenant_id == str(tenant_id), Ticket.status == "open",
                                       Ticket.subject == f"AI kalite kontrolü: {conversation_id}").count() == 1
        exc = module.AIBudgetExceeded("tenant", tenant_id, 100, 100)
        assert not module.ai_budget_service.emit_exceeded_event_once(db, tenant_id, exc)  # once per tenant per day
        assert db.query(SystemEvent).filter_by(code="AI_BUDGET_EXCEEDED", tenant_id=str(tenant_id)).count() == 1
    push.assert_awaited_once()


def test_contact_rate_limit_is_shared_through_redis(monkeypatch):
    from app.core import rate_limit as rate_limit_module
    from app.services import ai_service as module
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(rate_limit_module, "redis", object())
    fake = _FakeRedis()
    fake.eval = lambda _script, _n, key, _window: fake.values.__setitem__(key, fake.values.get(key, 0) + 1) or fake.values[key]
    minute, hour = module._ai_limiter(3, 60), module._ai_limiter(100, 3600)
    minute.clear(), hour.clear()
    minute._redis_client = hour._redis_client = fake
    replica_a, replica_b = module.AIService(), module.AIService()
    conversation = str(uuid4())
    assert replica_a._check_rate_limit(conversation, 3, 100)[0]
    assert replica_b._check_rate_limit(conversation, 3, 100)[0]
    assert replica_a._check_rate_limit(conversation, 3, 100)[0]
    assert not replica_b._check_rate_limit(conversation, 3, 100)[0]  # fourth call on another replica is refused
    assert any("ai-conversation-60-3" in key for key in fake.values)
    assert not minute.attempts  # nothing was counted in process memory
