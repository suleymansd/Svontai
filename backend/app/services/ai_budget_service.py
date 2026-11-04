"""Daily AI token budget per tenant and for the whole deployment (audit A13).

Runaway model spend is the top operational risk, so every model call is metered
(input and output tokens) and generation is refused once a UTC-day budget is
reached. Redis holds the hot daily counters (INCRBY with a TTL to midnight UTC)
so all replicas share one total; the monthly usage counters in the database are
always written as well and serve as the fallback when Redis is unavailable.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings

try:
    import redis
except ImportError:  # pragma: no cover - dependency is present in production
    redis = None

logger = logging.getLogger(__name__)

AI_BUDGET_REDIS_PREFIX = "svontai:ai-budget"
AI_BUDGET_EXCEEDED_CODE = "AI_BUDGET_EXCEEDED"

_REDIS_INCR_SCRIPT = """
local total = redis.call('INCRBY', KEYS[1], ARGV[1])
if redis.call('TTL', KEYS[1]) < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return total
"""


def utc_day_key(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d")


def seconds_until_midnight_utc(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60, int((midnight - now).total_seconds()))


def estimate_tokens(text: str) -> int:
    """Conservative size estimate used only when the provider omits usage."""
    return max(1, len(text or "") // 4)


class AIBudgetExceeded(RuntimeError):
    """Raised before any model call when the tenant or global daily budget is spent."""

    def __init__(self, scope: str, tenant_id: UUID | None, used: int, limit: int):
        self.scope = scope
        self.tenant_id = tenant_id
        self.used = used
        self.limit = limit
        super().__init__(f"AI daily token budget exceeded ({scope}): {used}/{limit}")

    def meta(self) -> dict:
        return {"scope": self.scope, "used": self.used, "limit": self.limit, "day": utc_day_key()}


class AIBudgetService:
    def __init__(self) -> None:
        self._redis_client = None
        self._redis_warning_logged = False

    # -- backends -----------------------------------------------------------------
    def _redis(self):
        if settings.RATE_LIMIT_BACKEND != "redis" or redis is None:
            return None
        if self._redis_client is None:
            self._redis_client = redis.Redis.from_url(
                settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1,
            )
        return self._redis_client

    def _redis_unavailable(self, reason: str) -> None:
        self._redis_client = None
        if not self._redis_warning_logged:
            self._redis_warning_logged = True
            logger.error("Redis AI budget counters unavailable; using database fallback (%s)", reason)

    @staticmethod
    def _keys(tenant_id: UUID | None, day: str) -> tuple[str | None, str]:
        tenant_key = f"{AI_BUDGET_REDIS_PREFIX}:{day}:tenant:{tenant_id}" if tenant_id else None
        return tenant_key, f"{AI_BUDGET_REDIS_PREFIX}:{day}:global"

    # -- reads ----------------------------------------------------------------------
    def usage_today(self, tenant_id: UUID | None) -> tuple[int, int]:
        """Return (tenant_tokens, global_tokens) spent so far this UTC day."""
        day = utc_day_key()
        tenant_key, global_key = self._keys(tenant_id, day)
        client = self._redis()
        if client is not None:
            try:
                values = client.mget([tenant_key or global_key, global_key])
                return (int(values[0] or 0) if tenant_key else 0), int(values[1] or 0)
            except Exception as exc:
                self._redis_unavailable(str(exc))
        return self._usage_today_db(tenant_id, day)

    @staticmethod
    def _usage_today_db(tenant_id: UUID | None, day: str) -> tuple[int, int]:
        from app.db.session import SessionLocal
        from app.services.usage_counter_service import UsageCounterService
        with SessionLocal() as db:
            return UsageCounterService(db).ai_tokens_today(tenant_id, day)

    def check(self, tenant_id: UUID | None) -> None:
        """Raise AIBudgetExceeded when today's spend already reached a budget."""
        tenant_used, global_used = self.usage_today(tenant_id)
        global_limit = int(settings.AI_DAILY_TOKEN_BUDGET_GLOBAL)
        if global_limit > 0 and global_used >= global_limit:
            raise AIBudgetExceeded("global", tenant_id, global_used, global_limit)
        tenant_limit = int(settings.AI_DAILY_TOKEN_BUDGET_PER_TENANT)
        if tenant_id is not None and tenant_limit > 0 and tenant_used >= tenant_limit:
            raise AIBudgetExceeded("tenant", tenant_id, tenant_used, tenant_limit)

    # -- writes ---------------------------------------------------------------------
    def record(self, tenant_id: UUID | None, input_tokens: int, output_tokens: int, *, model: str | None = None) -> None:
        """Meter one model call. Never raises: a metering failure is logged, not surfaced."""
        input_tokens = max(0, int(input_tokens or 0))
        output_tokens = max(0, int(output_tokens or 0))
        total = input_tokens + output_tokens
        day = utc_day_key()
        if tenant_id is not None:
            try:
                self._record_db(tenant_id, input_tokens, output_tokens, day)
            except Exception:
                logger.exception("ai_budget.db_record_failed tenant_id=%s", tenant_id)
        client = self._redis()
        if client is not None and total > 0:
            tenant_key, global_key = self._keys(tenant_id, day)
            try:
                ttl = seconds_until_midnight_utc()
                if tenant_key:
                    client.eval(_REDIS_INCR_SCRIPT, 1, tenant_key, total, ttl)
                client.eval(_REDIS_INCR_SCRIPT, 1, global_key, total, ttl)
            except Exception as exc:
                self._redis_unavailable(str(exc))
        logger.info(
            "ai_usage tenant_id=%s model=%s input_tokens=%s output_tokens=%s",
            tenant_id, model, input_tokens, output_tokens,
        )

    @staticmethod
    def _record_db(tenant_id: UUID, input_tokens: int, output_tokens: int, day: str) -> None:
        from app.db.session import SessionLocal
        from app.services.usage_counter_service import UsageCounterService
        with SessionLocal() as db:
            UsageCounterService(db).add_ai_tokens(tenant_id, input_tokens=input_tokens, output_tokens=output_tokens, day=day)

    def emit_exceeded_event_once(self, db: Session, tenant_id: UUID, exc: AIBudgetExceeded) -> bool:
        """Log SystemEvent AI_BUDGET_EXCEEDED at most once per tenant per UTC day."""
        from app.models.system_event import SystemEvent
        from app.services.system_event_service import SystemEventService
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        already = db.query(SystemEvent.id).filter(
            SystemEvent.code == AI_BUDGET_EXCEEDED_CODE,
            SystemEvent.tenant_id == str(tenant_id),
            SystemEvent.created_at >= day_start,
        ).first()
        if already:
            return False
        SystemEventService(db).log(
            tenant_id=str(tenant_id),
            source="ai_budget",
            level="warning",
            code=AI_BUDGET_EXCEEDED_CODE,
            message="Daily AI token budget reached; replies are routed to the operator queue until midnight UTC.",
            meta_json=exc.meta(),
        )
        return True


ai_budget_service = AIBudgetService()
