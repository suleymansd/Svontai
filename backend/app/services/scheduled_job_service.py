"""Persistent scheduled job locking for worker processes."""

from __future__ import annotations

import socket
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.autopilot import ScheduledJob


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ScheduledJobService:
    """Coordinates recurring jobs across multiple worker instances."""

    def __init__(self, db: Session, owner: str | None = None):
        self.db = db
        self.owner = owner or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"

    def acquire(self, name: str, interval_seconds: int, lock_seconds: int | None = None) -> ScheduledJob | None:
        now = utc_now()
        job = self.db.query(ScheduledJob).filter(ScheduledJob.name == name).first()
        if job is None:
            job = ScheduledJob(
                name=name,
                status="idle",
                interval_seconds=interval_seconds,
                next_run_at=now,
            )
            self.db.add(job)
            self.db.flush()

        next_run_at = _as_utc(job.next_run_at)
        locked_until = _as_utc(job.locked_until)

        if next_run_at and next_run_at > now:
            self.db.commit()
            return None

        if locked_until and locked_until > now and job.lock_owner != self.owner:
            self.db.commit()
            return None

        job.status = "running"
        job.lock_owner = self.owner
        job.locked_until = now + timedelta(seconds=lock_seconds or max(60, interval_seconds))
        job.last_run_at = now
        job.interval_seconds = interval_seconds
        job.updated_at = now
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_success(self, job: ScheduledJob) -> None:
        now = utc_now()
        job.status = "idle"
        job.lock_owner = None
        job.locked_until = None
        job.retry_count = 0
        job.last_error = None
        job.last_success_at = now
        job.next_run_at = now + timedelta(seconds=job.interval_seconds)
        job.updated_at = now
        self.db.commit()

    def mark_failure(self, job: ScheduledJob, exc: Exception) -> None:
        job_id = job.id
        self.db.rollback()
        job = self.db.get(ScheduledJob, job_id)
        if job is None:
            return

        now = utc_now()
        job.retry_count += 1
        backoff_seconds = min(job.interval_seconds, 30 * (2 ** min(job.retry_count, 6)))
        job.status = "failed" if job.retry_count >= job.max_retries else "retrying"
        job.lock_owner = None
        job.locked_until = None
        job.last_error = str(exc)[:4000]
        job.next_run_at = now + timedelta(seconds=backoff_seconds)
        job.updated_at = now
        self.db.commit()


@contextmanager
def scheduled_job_lock(
    db: Session,
    name: str,
    interval_seconds: int,
    lock_seconds: int | None = None,
) -> Iterator[ScheduledJob | None]:
    service = ScheduledJobService(db)
    job = service.acquire(name, interval_seconds, lock_seconds=lock_seconds)
    try:
        yield job
    except Exception as exc:
        if job is not None:
            try:
                service.mark_failure(job, exc)
            except Exception:
                db.rollback()
        raise
    else:
        if job is not None:
            service.mark_success(job)
