"""
Tenant usage counter service (monthly) for billing-aware metering.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.usage_counter import TenantUsageCounter
from app.models.usage_ledger import UsageLedgerEntry

AI_TOKENS_TODAY_KEY = "ai_tokens_today"


def _current_period_key_utc(now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


class UsageCounterService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, tenant_id: UUID, period_key: str | None = None, *, commit: bool = True) -> TenantUsageCounter:
        period_key = period_key or _current_period_key_utc()
        counter = self.db.query(TenantUsageCounter).filter(
            TenantUsageCounter.tenant_id == tenant_id,
            TenantUsageCounter.period_key == period_key,
        ).first()
        if counter:
            return counter

        insert = pg_insert if self.db.get_bind().dialect.name == "postgresql" else sqlite_insert
        self.db.execute(insert(TenantUsageCounter).values(
            tenant_id=tenant_id, period_key=period_key,
        ).on_conflict_do_nothing(index_elements=["tenant_id", "period_key"]))
        if commit:
            self.db.commit()
        return self.db.query(TenantUsageCounter).filter_by(tenant_id=tenant_id, period_key=period_key).one()

    def increment_voice_seconds(self, tenant_id: UUID, seconds: int, period_key: str | None = None) -> TenantUsageCounter:
        return self.increment(tenant_id=tenant_id, voice_seconds=seconds, period_key=period_key)

    def increment_message_count(self, tenant_id: UUID, count: int = 1, period_key: str | None = None) -> TenantUsageCounter:
        return self.increment(tenant_id=tenant_id, message_count=count, period_key=period_key)

    def increment_workflow_runs(self, tenant_id: UUID, count: int = 1, period_key: str | None = None) -> TenantUsageCounter:
        return self.increment(tenant_id=tenant_id, workflow_runs=count, period_key=period_key)

    def increment_tool_calls(self, tenant_id: UUID, count: int = 1, period_key: str | None = None) -> TenantUsageCounter:
        return self.increment(tenant_id=tenant_id, tool_calls=count, period_key=period_key)

    def increment_outbound_calls(self, tenant_id: UUID, count: int = 1, period_key: str | None = None) -> TenantUsageCounter:
        return self.increment(tenant_id=tenant_id, outbound_calls=count, period_key=period_key)

    def increment(
        self,
        *,
        tenant_id: UUID,
        message_count: int = 0,
        voice_seconds: int = 0,
        workflow_runs: int = 0,
        tool_calls: int = 0,
        outbound_calls: int = 0,
        period_key: str | None = None,
        extra: dict | None = None,
        commit: bool = True,
        idempotency_key: str | None = None,
    ) -> TenantUsageCounter:
        """Add to the monthly counters.

        With ``idempotency_key`` (reservation id, provider message id, run id)
        the increment is recorded in the unique-indexed usage ledger inside the
        same transaction, so a retried job that replays the key adds nothing.
        """
        period_key = period_key or _current_period_key_utc()
        counter = self.get_or_create(tenant_id, period_key=period_key, commit=commit)
        amounts = {
            "message_count": message_count, "voice_seconds": voice_seconds,
            "workflow_runs": workflow_runs, "tool_calls": tool_calls,
            "outbound_calls": outbound_calls,
        }
        if idempotency_key and not self._claim_ledger(tenant_id, idempotency_key, period_key, amounts):
            if commit:
                self.db.commit()
            return counter
        values = {
            name: getattr(TenantUsageCounter, name) + max(0, int(amount))
            for name, amount in amounts.items()
        }
        if extra:
            current = self.db.query(TenantUsageCounter).filter_by(id=counter.id).populate_existing().with_for_update().one()
            values["extra_json"] = {**(current.extra_json or {}), **extra}
        self.db.execute(update(TenantUsageCounter).where(TenantUsageCounter.id == counter.id).values(**values))
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(counter)
        return counter

    def add_ai_tokens(
        self, tenant_id: UUID, *, input_tokens: int, output_tokens: int, day: str,
        period_key: str | None = None, commit: bool = True,
    ) -> TenantUsageCounter:
        """Add model tokens to the monthly counter keys and the rolling UTC-day total."""
        period_key = period_key or day[:7]
        counter = self.get_or_create(tenant_id, period_key=period_key, commit=commit)
        current = self.db.query(TenantUsageCounter).filter_by(id=counter.id).populate_existing().with_for_update().one()
        extra = dict(current.extra_json or {})
        extra["ai_input_tokens"] = int(extra.get("ai_input_tokens") or 0) + max(0, int(input_tokens))
        extra["ai_output_tokens"] = int(extra.get("ai_output_tokens") or 0) + max(0, int(output_tokens))
        extra["ai_calls"] = int(extra.get("ai_calls") or 0) + 1
        today = dict(extra.get(AI_TOKENS_TODAY_KEY) or {})
        if today.get("day") != day:
            today = {"day": day, "tokens": 0}
        today["tokens"] = int(today.get("tokens") or 0) + max(0, int(input_tokens)) + max(0, int(output_tokens))
        extra[AI_TOKENS_TODAY_KEY] = today
        self.db.execute(update(TenantUsageCounter).where(TenantUsageCounter.id == counter.id).values(extra_json=extra))
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(counter)
        return counter

    def ai_tokens_today(self, tenant_id: UUID | None, day: str) -> tuple[int, int]:
        """Return (tenant_tokens, global_tokens) for a UTC day; database fallback for the budget check."""
        rows = self.db.query(TenantUsageCounter.tenant_id, TenantUsageCounter.extra_json).filter(
            TenantUsageCounter.period_key == day[:7],
        ).all()
        tenant_total = global_total = 0
        for row_tenant_id, extra in rows:
            today = (extra or {}).get(AI_TOKENS_TODAY_KEY) or {}
            if today.get("day") != day:
                continue
            tokens = int(today.get("tokens") or 0)
            global_total += tokens
            if tenant_id is not None and str(row_tenant_id) == str(tenant_id):
                tenant_total = tokens
        return tenant_total, global_total

    def _claim_ledger(self, tenant_id: UUID, idempotency_key: str, period_key: str, amounts: dict) -> bool:
        """Return True exactly once per key; the unique index arbitrates concurrent retries."""
        insert = pg_insert if self.db.get_bind().dialect.name == "postgresql" else sqlite_insert
        result = self.db.execute(insert(UsageLedgerEntry).values(
            id=uuid4(), tenant_id=tenant_id, idempotency_key=idempotency_key[:160], period_key=period_key,
            amounts_json={name: int(amount) for name, amount in amounts.items() if amount},
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ).on_conflict_do_nothing(index_elements=["idempotency_key"]))
        return bool(result.rowcount)
