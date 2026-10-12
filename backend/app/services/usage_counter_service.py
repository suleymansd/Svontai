"""
Tenant usage counter service (monthly) for billing-aware metering.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.usage_counter import TenantUsageCounter


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
    ) -> TenantUsageCounter:
        counter = self.get_or_create(tenant_id, period_key=period_key, commit=commit)
        values = {
            name: getattr(TenantUsageCounter, name) + max(0, int(amount))
            for name, amount in {
                "message_count": message_count, "voice_seconds": voice_seconds,
                "workflow_runs": workflow_runs, "tool_calls": tool_calls,
                "outbound_calls": outbound_calls,
            }.items()
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
