"""Railway worker entrypoint for autonomous scheduled operations."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import timedelta

from app.core.config import settings
from app.core.time import utc_now_naive
from app.db.session import SessionLocal
from app.models.automation import AutomationRun, AutomationRunStatus
from app.models.tenant import Tenant
from app.services.appointment_reminder_service import AppointmentReminderService
from app.services.autopilot_service import AutopilotService
from app.services.real_estate_service import RealEstateService
from app.services.scheduled_job_service import scheduled_job_lock
from app.services.system_event_service import SystemEventService
from app.services.voice_automation_service import VoiceAutomationService


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("smartwa.worker")


async def _run_every(name: str, interval_seconds: int, fn) -> None:
    while True:
        try:
            await asyncio.to_thread(fn)
        except Exception as exc:
            logger.warning("%s failed: %s", name, exc)
        await asyncio.sleep(interval_seconds)


def _dispatch_reminders() -> None:
    if not settings.APPOINTMENT_REMINDER_ENABLED or not settings.EMAIL_ENABLED:
        return
    db = SessionLocal()
    try:
        with scheduled_job_lock(db, "appointment_reminders", settings.APPOINTMENT_REMINDER_INTERVAL_SECONDS) as job:
            if job is not None:
                AppointmentReminderService(db).dispatch_due_reminders()
    finally:
        db.close()


def _run_real_estate_automation() -> None:
    if not settings.REAL_ESTATE_AUTOMATION_ENABLED:
        return
    db = SessionLocal()
    try:
        with scheduled_job_lock(db, "real_estate_automation", settings.REAL_ESTATE_AUTOMATION_INTERVAL_SECONDS) as job:
            if job is None:
                return
            result = asyncio.run(RealEstateService(db).run_automation_cycle())
            if result.get("tenant_count", 0) > 0:
                logger.info("real_estate_cycle tenants=%s", result.get("tenant_count"))
    finally:
        db.close()


def _run_integration_diagnostics() -> None:
    db = SessionLocal()
    try:
        with scheduled_job_lock(db, "integration_diagnostics", 300) as job:
            if job is None:
                return
            service = AutopilotService(db)
            tenants = db.query(Tenant).all()
            for tenant in tenants:
                service.run_diagnostics(tenant)
    finally:
        db.close()


def _cleanup_stuck_runs() -> None:
    db = SessionLocal()
    try:
        with scheduled_job_lock(db, "stuck_run_cleanup", 60) as job:
            if job is None:
                return
            cutoff = utc_now_naive() - timedelta(minutes=max(5, settings.N8N_TIMEOUT_SECONDS))
            rows = db.query(AutomationRun).filter(
                AutomationRun.status == AutomationRunStatus.RUNNING.value,
                AutomationRun.started_at.isnot(None),
                AutomationRun.started_at < cutoff,
            ).all()
            for row in rows:
                row.mark_timeout()
                SystemEventService(db).log(
                    tenant_id=str(row.tenant_id),
                    source="worker",
                    level="warn",
                    code="AUTOMATION_RUN_TIMEOUT",
                    message="Automation run marked timeout by worker watchdog",
                    meta_json={"run_id": str(row.id), "workflow_id": row.n8n_workflow_id},
                    correlation_id=row.correlation_id,
                )
            if rows:
                db.commit()
    finally:
        db.close()


def _run_outbound_voice_jobs() -> None:
    db = SessionLocal()
    try:
        with scheduled_job_lock(db, "outbound_voice_jobs", 30, lock_seconds=25) as job:
            if job is None:
                return
            result = VoiceAutomationService(db).run_due_outbound_jobs(limit=20)
            if result.get("started", 0) or result.get("failed", 0):
                logger.info("outbound_voice_jobs result=%s", result)
    finally:
        db.close()


async def main() -> None:
    logger.info("SmartWA worker starting")
    tasks = [
        asyncio.create_task(_run_every("appointment_reminders", settings.APPOINTMENT_REMINDER_INTERVAL_SECONDS, _dispatch_reminders)),
        asyncio.create_task(_run_every("real_estate_automation", settings.REAL_ESTATE_AUTOMATION_INTERVAL_SECONDS, _run_real_estate_automation)),
        asyncio.create_task(_run_every("integration_diagnostics", 300, _run_integration_diagnostics)),
        asyncio.create_task(_run_every("stuck_run_cleanup", 60, _cleanup_stuck_runs)),
        asyncio.create_task(_run_every("outbound_voice_jobs", 30, _run_outbound_voice_jobs)),
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


if __name__ == "__main__":
    asyncio.run(main())
