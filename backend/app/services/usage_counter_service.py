"""
Tenant usage counter service (monthly) for billing-aware metering.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.usage_counter import TenantUsageCounter


def _current_period_key_utc(now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


class UsageCounterService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, tenant_id: UUID, period_key: str | None = None) -> TenantUsageCounter:
        period_key = period_key or _current_period_key_utc()
        counter = self.db.query(TenantUsageCounter).filter(
            TenantUsageCounter.tenant_id == tenant_id,
            TenantUsageCounter.period_key == period_key,
        ).first()
        if counter:
            return counter

        counter = TenantUsageCounter(tenant_id=tenant_id, period_key=period_key)
        self.db.add(counter)
        self.db.commit()
        self.db.refresh(counter)
        return counter

    def increment_voice_seconds(self, tenant_id: UUID, seconds: int, period_key: str | None = None) -> TenantUsageCounter:
        counter = self.get_or_create(tenant_id, period_key=period_key)
        counter.voice_seconds = int(counter.voice_seconds or 0) + int(max(0, seconds))
        self.db.commit()
        self.db.refresh(counter)
        return counter

    def increment_message_count(self, tenant_id: UUID, count: int = 1, period_key: str | None = None) -> TenantUsageCounter:
        counter = self.get_or_create(tenant_id, period_key=period_key)
        counter.message_count = int(counter.message_count or 0) + int(max(0, count))
        self.db.commit()
        self.db.refresh(counter)
        return counter

    def increment_workflow_runs(self, tenant_id: UUID, count: int = 1, period_key: str | None = None) -> TenantUsageCounter:
        counter = self.get_or_create(tenant_id, period_key=period_key)
        counter.workflow_runs = int(counter.workflow_runs or 0) + int(max(0, count))
        self.db.commit()
        self.db.refresh(counter)
        return counter

    def increment_tool_calls(self, tenant_id: UUID, count: int = 1, period_key: str | None = None) -> TenantUsageCounter:
        counter = self.get_or_create(tenant_id, period_key=period_key)
        counter.tool_calls = int(counter.tool_calls or 0) + int(max(0, count))
        self.db.commit()
        self.db.refresh(counter)
        return counter

    def increment_outbound_calls(self, tenant_id: UUID, count: int = 1, period_key: str | None = None) -> TenantUsageCounter:
        counter = self.get_or_create(tenant_id, period_key=period_key)
        counter.outbound_calls = int(counter.outbound_calls or 0) + int(max(0, count))
        self.db.commit()
        self.db.refresh(counter)
        return counter

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
    ) -> TenantUsageCounter:
        counter = self.get_or_create(tenant_id, period_key=period_key)
        if message_count:
            counter.message_count = int(counter.message_count or 0) + int(max(0, message_count))
        if voice_seconds:
            counter.voice_seconds = int(counter.voice_seconds or 0) + int(max(0, voice_seconds))
        if workflow_runs:
            counter.workflow_runs = int(counter.workflow_runs or 0) + int(max(0, workflow_runs))
        if tool_calls:
            counter.tool_calls = int(counter.tool_calls or 0) + int(max(0, tool_calls))
        if outbound_calls:
            counter.outbound_calls = int(counter.outbound_calls or 0) + int(max(0, outbound_calls))
        if extra:
            counter.extra_json = {**(counter.extra_json or {}), **extra}
        self.db.commit()
        self.db.refresh(counter)
        return counter
