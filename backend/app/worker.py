"""Railway worker entrypoint for autonomous scheduled operations."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from datetime import timedelta
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.config import settings
from app.core.time import utc_now_naive
from app.db.session import SessionLocal, engine
from app.models.automation import AutomationRun, AutomationRunStatus
from app.models.tenant import Tenant
from app.models.whatsapp_account import WhatsAppAccount
from app.services.appointment_reminder_service import AppointmentReminderService
from app.services.autopilot_service import AutopilotService
from app.services.real_estate_service import RealEstateService
from app.services.scheduled_job_service import scheduled_job_lock
from app.services.system_event_service import SystemEventService
from app.services.voice_automation_service import VoiceAutomationService
from app.services.onboarding_service import OnboardingService
from app.services.analytics_service import AnalyticsService
from app.services.push_notification_service import PushNotificationService
from app.services.email_service import EmailService
from app.services.google_calendar_service import GoogleCalendarService
from zoneinfo import ZoneInfo


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("smartwa.worker")


def _expected_migration_heads() -> set[str]:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return set(ScriptDirectory.from_config(config).get_heads())


def _database_migration_heads() -> set[str]:
    with engine.connect() as connection:
        return set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())


def _wait_for_database_schema(timeout_seconds: int = 180, poll_seconds: int = 5) -> None:
    expected = _expected_migration_heads()
    deadline = time.monotonic() + timeout_seconds
    last_seen: set[str] | None = None
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            last_seen = _database_migration_heads()
            last_error = None
            if last_seen == expected:
                logger.info("Database migration head ready: %s", ",".join(sorted(expected)))
                return
        except Exception as exc:
            last_error = exc

        logger.info(
            "Waiting for database migrations expected=%s current=%s",
            ",".join(sorted(expected)),
            ",".join(sorted(last_seen or set())) or "unavailable",
        )
        time.sleep(poll_seconds)

    detail = str(last_error) if last_error else f"current={sorted(last_seen or set())}"
    raise RuntimeError(
        f"Database migrations did not reach head {sorted(expected)} within {timeout_seconds}s: {detail}"
    )


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


def _sync_openwa_sessions() -> None:
    if not settings.OPENWA_ENABLED:
        return
    db = SessionLocal()
    try:
        with scheduled_job_lock(db, "openwa_session_health", 120, lock_seconds=100) as job:
            if job is None:
                return
            accounts = db.query(WhatsAppAccount).filter(
                WhatsAppAccount.provider == "openwa",
                WhatsAppAccount.provider_session_id.isnot(None),
            ).all()
            service = OnboardingService(db)
            for account in accounts:
                was_active = account.is_active
                try:
                    result = asyncio.run(service.refresh_openwa_status(account.tenant_id))
                    if was_active and not result.get("connected"):
                        SystemEventService(db).log(
                            tenant_id=str(account.tenant_id),
                            source="openwa",
                            level="warn",
                            code="OPENWA_SESSION_DISCONNECTED",
                            message="WhatsApp QR oturumu bağlantısını kaybetti.",
                            meta_json={
                                "session_id": account.provider_session_id,
                                "status": result.get("status"),
                            },
                        )
                except Exception as exc:
                    account.provider_metadata_json = {
                        **(account.provider_metadata_json or {}),
                        "health_status": "unavailable",
                    }
                    account.last_error = str(exc)[:1000]
                    db.commit()
                    logger.warning(
                        "openwa_session_health tenant_id=%s failed=%s",
                        account.tenant_id,
                        exc,
                    )
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


def _sync_google_calendar_appointments() -> None:
    db = SessionLocal()
    try:
        with scheduled_job_lock(db, "google_calendar_appointment_sync", 120, lock_seconds=100) as job:
            if job is None:
                return
            service = GoogleCalendarService(db)
            push_result = service.sync_pending_appointments(limit=100)
            pull_result = service.pull_appointment_updates(limit_tenants=100)
            if push_result.get("processed", 0) or pull_result.get("events", 0) or pull_result.get("failed", 0):
                logger.info(
                    "google_calendar_appointment_sync push=%s pull=%s",
                    push_result,
                    pull_result,
                )
    finally:
        db.close()


def _operational_report_key(local_now, period: str) -> str | None:
    if period == "daily":
        return local_now.date().isoformat() if local_now.hour >= 18 else None
    if period == "weekly" and local_now.weekday() == 0 and local_now.hour >= 9:
        return f"{local_now.isocalendar().year}-W{local_now.isocalendar().week:02d}"
    return None


def _send_operational_reports(period: str) -> None:
    db = SessionLocal()
    try:
        job_name = f"{period}_operational_report"
        with scheduled_job_lock(db, job_name, 3600, lock_seconds=300) as job:
            if job is None:
                return
            for tenant in db.query(Tenant).all():
                enabled_key = f"{period}_operational_report_enabled"
                if (tenant.settings or {}).get(enabled_key, True) is False:
                    continue
                timezone_name = str((tenant.settings or {}).get("timezone") or "Europe/Istanbul")
                try:
                    local_now = utc_now_naive().replace(tzinfo=ZoneInfo("UTC")).astimezone(
                        ZoneInfo(timezone_name)
                    )
                except Exception:
                    local_now = utc_now_naive().replace(tzinfo=ZoneInfo("UTC")).astimezone(
                        ZoneInfo("Europe/Istanbul")
                    )
                report_key = _operational_report_key(local_now, period)
                if report_key is None:
                    continue
                sent_key = f"{period}_operational_report_last_sent"
                if (tenant.settings or {}).get(sent_key) == report_key:
                    continue
                analytics_period = "week" if period == "weekly" else "today"
                report = AnalyticsService(db).get_operational_report(tenant, analytics_period)
                event_type = "weekly_report" if period == "weekly" else "daily_report"
                label = "haftalık" if period == "weekly" else "günlük"
                result = asyncio.run(PushNotificationService(db).send_to_tenant(
                    tenant_id=tenant.id,
                    event_type=event_type,
                    title=f"SvontAI {label} raporunuz hazır",
                    body=report["summary"],
                    url="/dashboard",
                    tag=f"svontai-{period}-report",
                    extra={"period": analytics_period},
                ))
                email_sent = False
                if (tenant.settings or {}).get("operational_report_email_enabled", True) is not False:
                    email_sent = EmailService.send_email(
                        recipients=tenant.owner.email,
                        subject=report["title"],
                        text_body=report["text"],
                    )
                if result.get("sent", 0) > 0 or email_sent:
                    tenant.settings = {
                        **(tenant.settings or {}),
                        sent_key: report_key,
                    }
                    db.commit()
    finally:
        db.close()


def _send_daily_operational_reports() -> None:
    _send_operational_reports("daily")


def _send_weekly_operational_reports() -> None:
    _send_operational_reports("weekly")


async def main() -> None:
    logger.info("SmartWA worker starting")
    await asyncio.to_thread(_wait_for_database_schema)
    tasks = [
        asyncio.create_task(_run_every("appointment_reminders", settings.APPOINTMENT_REMINDER_INTERVAL_SECONDS, _dispatch_reminders)),
        asyncio.create_task(_run_every("real_estate_automation", settings.REAL_ESTATE_AUTOMATION_INTERVAL_SECONDS, _run_real_estate_automation)),
        asyncio.create_task(_run_every("integration_diagnostics", 300, _run_integration_diagnostics)),
        asyncio.create_task(_run_every("openwa_session_health", 120, _sync_openwa_sessions)),
        asyncio.create_task(_run_every("stuck_run_cleanup", 60, _cleanup_stuck_runs)),
        asyncio.create_task(_run_every("outbound_voice_jobs", 30, _run_outbound_voice_jobs)),
        asyncio.create_task(_run_every("google_calendar_appointment_sync", 120, _sync_google_calendar_appointments)),
        asyncio.create_task(_run_every("daily_operational_report", 3600, _send_daily_operational_reports)),
        asyncio.create_task(_run_every("weekly_operational_push", 3600, _send_weekly_operational_reports)),
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
