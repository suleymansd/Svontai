"""Persistent scheduled job locking for worker processes."""

from __future__ import annotations

import socket
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.autopilot import ScheduledJob

class ScheduledJobService:
    """Coordinates recurring jobs across multiple worker instances."""

    def __init__(self, db: Session, owner: str | None = None):
        self.db = db
        self.owner = owner or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"

    def acquire(self, name: str, interval_seconds: int, lock_seconds: int | None = None) -> ScheduledJob | None:
        now = utc_now()
        self._ensure_job_exists(name, interval_seconds, now)
        statement = (
            update(ScheduledJob)
            .where(
                ScheduledJob.name == name,
                or_(ScheduledJob.next_run_at.is_(None), ScheduledJob.next_run_at <= now),
                or_(ScheduledJob.locked_until.is_(None), ScheduledJob.locked_until <= now),
            )
            .values(
                status="running",
                lock_owner=self.owner,
                locked_until=now + timedelta(seconds=lock_seconds or max(60, interval_seconds)),
                last_run_at=now,
                interval_seconds=interval_seconds,
                updated_at=now,
            )
            .returning(ScheduledJob.id)
        )
        job_id = self.db.execute(statement).scalar_one_or_none()
        self.db.commit()
        if job_id is None:
            return None
        return self.db.get(ScheduledJob, job_id)

    def _ensure_job_exists(self, name: str, interval_seconds: int, now: datetime) -> None:
        values = {
            "name": name,
            "status": "idle",
            "interval_seconds": interval_seconds,
            "next_run_at": now,
            "meta_json": {},
        }
        dialect = self.db.get_bind().dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            statement = insert(ScheduledJob).values(**values).on_conflict_do_nothing(index_elements=["name"])
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert

            statement = insert(ScheduledJob).values(**values).on_conflict_do_nothing(index_elements=["name"])
        else:
            if self.db.query(ScheduledJob.id).filter(ScheduledJob.name == name).first():
                return
            self.db.add(ScheduledJob(**values))
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
            return
        self.db.execute(statement)
        self.db.commit()

    def mark_success(self, job: ScheduledJob) -> None:
        now = utc_now()
        self.db.execute(
            update(ScheduledJob)
            .where(ScheduledJob.id == job.id, ScheduledJob.lock_owner == self.owner)
            .values(
                status="idle",
                lock_owner=None,
                locked_until=None,
                retry_count=0,
                last_error=None,
                last_success_at=now,
                next_run_at=now + timedelta(seconds=job.interval_seconds),
                updated_at=now,
            )
        )
        self.db.commit()

    def mark_failure(self, job: ScheduledJob, exc: Exception) -> None:
        job_id = job.id
        self.db.rollback()
        job = self.db.get(ScheduledJob, job_id)
        if job is None or job.lock_owner != self.owner:
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
