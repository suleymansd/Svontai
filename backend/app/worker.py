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
from app.core.observability import capture_exception, configure_observability
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
from app.services.database_backup_service import DatabaseBackupService
from app.services.openwa_client import OpenWAError, openwa_client
from zoneinfo import ZoneInfo


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("smartwa.worker")
configure_observability("worker")


_OPENWA_QR_STATUSES = {"qr_ready", "qr", "authentication_required", "logged_out"}
_OPENWA_RECONNECTABLE_STATUSES = {"failed", "disconnected", "stopped", "error"}
_OPENWA_TRANSITIONAL_STATUSES = {"created", "initializing", "connecting", "starting"}


def _openwa_recovery_action(
    *,
    status: str,
    connected: bool,
    was_active: bool,
    previous_failures: int,
    previous_health: str,
) -> str:
    """Return the safe recovery action for an OpenWA session state."""
    if connected:
        return "none"
    normalized = status.strip().lower()
    if normalized in _OPENWA_QR_STATUSES:
        return "qr_required"
    if normalized in _OPENWA_TRANSITIONAL_STATUSES:
        return "wait"
    if normalized in _OPENWA_RECONNECTABLE_STATUSES and (
        was_active or previous_failures > 0 or previous_health == "disconnected"
    ):
        return "reconnect"
    return "none"


def _mark_openwa_qr_required(db, account: WhatsAppAccount) -> None:
    metadata = dict(account.provider_metadata_json or {})
    first_alert = not metadata.get("qr_alerted_at")
    now = utc_now_naive().isoformat()
    account.provider_metadata_json = {
        **metadata,
        "health_status": "action_required",
        "qr_required_at": metadata.get("qr_required_at") or now,
        "qr_alerted_at": metadata.get("qr_alerted_at") or now,
    }
    account.last_error = "WhatsApp QR bağlantısı yeniden onaylanmalı."
    db.commit()
    if not first_alert:
        return

    SystemEventService(db).log(
        tenant_id=str(account.tenant_id),
        source="openwa",
        level="warn",
        code="OPENWA_QR_REQUIRED",
        message="WhatsApp oturumu çıkış yaptı; QR kodunun yeniden taranması gerekiyor.",
        meta_json={"session_id": account.provider_session_id},
    )
    asyncio.run(PushNotificationService(db).send_to_tenant(
        tenant_id=account.tenant_id,
        event_type="integration_alert",
        title="WhatsApp bağlantısını yenileyin",
        body="Telefonunuzdan SvontAI QR kodunu yeniden tarayın.",
        url="/dashboard/setup/whatsapp",
        tag="svontai-openwa-qr-required",
    ))


def _openwa_qr_is_ready(payload: dict | None) -> bool:
    return bool(payload and str(payload.get("qrCode") or "").strip())


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
            capture_exception(exc)
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
                previous_metadata = dict(account.provider_metadata_json or {})
                previous_failures = int(previous_metadata.get("reconnect_failure_count") or 0)
                try:
                    result = asyncio.run(service.refresh_openwa_status(account.tenant_id))
                    recovery_action = _openwa_recovery_action(
                        status=str(result.get("status") or "unknown"),
                        connected=bool(result.get("connected")),
                        was_active=was_active,
                        previous_failures=previous_failures,
                        previous_health=str(previous_metadata.get("health_status") or ""),
                    )
                    if recovery_action == "reconnect":
                        asyncio.run(openwa_client.start_session(account.provider_session_id))
                        result = asyncio.run(service.refresh_openwa_status(account.tenant_id))
                        recovery_action = _openwa_recovery_action(
                            status=str(result.get("status") or "unknown"),
                            connected=bool(result.get("connected")),
                            was_active=was_active,
                            previous_failures=previous_failures,
                            previous_health=str(previous_metadata.get("health_status") or ""),
                        )
                        rotation_already_attempted = bool(
                            previous_metadata.get("auto_session_rotation_started_at")
                            or previous_metadata.get("auto_session_rotated_at")
                        )
                        if recovery_action == "reconnect" and not rotation_already_attempted:
                            old_session_id = account.provider_session_id
                            rotation_started_at = utc_now_naive().isoformat()
                            account.provider_metadata_json = {
                                **(account.provider_metadata_json or {}),
                                "auto_session_rotation_started_at": rotation_started_at,
                                "auto_session_rotated_from": old_session_id,
                            }
                            db.commit()
                            result = asyncio.run(
                                service.reconnect_openwa(
                                    account.tenant_id,
                                    force_new_session=True,
                                )
                            )
                            db.refresh(account)
                            account.provider_metadata_json = {
                                **(account.provider_metadata_json or {}),
                                "auto_session_rotated_at": utc_now_naive().isoformat(),
                                "auto_session_rotated_from": old_session_id,
                                "auto_session_rotated_to": account.provider_session_id,
                            }
                            db.commit()
                            SystemEventService(db).log(
                                tenant_id=str(account.tenant_id),
                                source="openwa",
                                level="warn",
                                code="OPENWA_SESSION_AUTO_ROTATED",
                                message="Bozuk WhatsApp oturumu silindi ve yeni QR oturumu oluşturuldu.",
                                meta_json={
                                    "previous_session_id": old_session_id,
                                    "session_id": account.provider_session_id,
                                },
                            )
                            asyncio.run(PushNotificationService(db).send_to_tenant(
                                tenant_id=account.tenant_id,
                                event_type="integration_alert",
                                title="Yeni WhatsApp QR kodu hazır",
                                body="Eski oturum güvenli şekilde yenilendi. Telefonunuzdan yeni QR kodunu tarayın.",
                                url="/dashboard/setup/whatsapp",
                                tag="svontai-openwa-session-rotated",
                            ))
                            recovery_action = _openwa_recovery_action(
                                status=str(result.get("status") or "unknown"),
                                connected=bool(result.get("connected")),
                                was_active=was_active,
                                previous_failures=previous_failures,
                                previous_health=str(previous_metadata.get("health_status") or ""),
                            )

                    if recovery_action == "qr_required":
                        _mark_openwa_qr_required(db, account)
                        continue

                    if recovery_action == "wait":
                        try:
                            qr_payload = asyncio.run(
                                openwa_client.get_qr(account.provider_session_id)
                            )
                        except OpenWAError as exc:
                            if exc.status_code != 400:
                                raise
                            qr_payload = {}

                        if _openwa_qr_is_ready(qr_payload):
                            account.provider_metadata_json = {
                                **(account.provider_metadata_json or {}),
                                "engine_status": str(qr_payload.get("status") or "qr_ready"),
                                "health_status": "action_required",
                            }
                            db.commit()
                            _mark_openwa_qr_required(db, account)
                            continue

                        account.provider_metadata_json = {
                            **(account.provider_metadata_json or {}),
                            "health_status": "connecting",
                        }
                        account.last_error = None
                        db.commit()
                        continue

                    if result.get("connected"):
                        if previous_failures:
                            account.provider_metadata_json = {
                                key: value
                                for key, value in (account.provider_metadata_json or {}).items()
                                if key not in {
                                    "reconnect_failure_count",
                                    "reconnect_alerted_at",
                                    "last_reconnect_attempt_at",
                                }
                            }
                            db.commit()
                            SystemEventService(db).log(
                                tenant_id=str(account.tenant_id),
                                source="openwa",
                                level="info",
                                code="OPENWA_SESSION_RECOVERED",
                                message="WhatsApp QR oturumu otomatik olarak yeniden bağlandı.",
                                meta_json={"session_id": account.provider_session_id},
                            )
                        continue

                    if recovery_action == "reconnect":
                        raise RuntimeError(
                            f"OpenWA session did not recover (status={result.get('status') or 'unknown'})"
                        )

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
                    metadata = dict(account.provider_metadata_json or {})
                    failure_count = int(metadata.get("reconnect_failure_count") or 0) + 1
                    account.provider_metadata_json = {
                        **metadata,
                        "health_status": "unavailable",
                        "reconnect_failure_count": failure_count,
                        "last_reconnect_attempt_at": utc_now_naive().isoformat(),
                    }
                    account.last_error = str(exc)[:1000]
                    db.commit()
                    SystemEventService(db).log(
                        tenant_id=str(account.tenant_id),
                        source="openwa",
                        level="error",
                        code="OPENWA_RECONNECT_FAILED",
                        message="WhatsApp QR oturumu otomatik olarak yeniden bağlanamadı.",
                        meta_json={
                            "session_id": account.provider_session_id,
                            "failure_count": failure_count,
                            "error": str(exc)[:300],
                        },
                    )
                    if failure_count >= 3 and not metadata.get("reconnect_alerted_at"):
                        asyncio.run(PushNotificationService(db).send_to_tenant(
                            tenant_id=account.tenant_id,
                            event_type="integration_alert",
                            title="WhatsApp bağlantınız kontrol edilmeli",
                            body="SvontAI yeniden bağlanmayı denedi. Telefonunuzdan QR bağlantısını yenileyin.",
                            url="/dashboard/setup/whatsapp",
                            tag="svontai-openwa-reconnect",
                            extra={"failure_count": failure_count},
                        ))
                        account.provider_metadata_json = {
                            **(account.provider_metadata_json or {}),
                            "reconnect_alerted_at": utc_now_naive().isoformat(),
                        }
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
                    email_sent = EmailService.send_operational_report_email(
                        recipients=tenant.owner.email,
                        report=report,
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


def _run_database_backup() -> None:
    if not settings.DATABASE_BACKUP_ENABLED:
        return
    db = SessionLocal()
    try:
        interval = max(3600, settings.DATABASE_BACKUP_INTERVAL_SECONDS)
        with scheduled_job_lock(
            db,
            "encrypted_database_backup",
            interval,
            lock_seconds=min(interval, 4 * 3600),
        ) as job:
            if job is None:
                return
            result = DatabaseBackupService().run()
            logger.info(
                "database_backup uploaded key=%s bytes=%s restore_verified=%s expired_removed=%s",
                result.object_key,
                result.encrypted_size,
                result.restore_verified,
                result.expired_removed,
            )
    finally:
        db.close()


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
        asyncio.create_task(_run_every("encrypted_database_backup", 300, _run_database_backup)),
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("SmartWA worker stopped")
