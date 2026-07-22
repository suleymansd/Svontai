"""Non-destructive, tenant-scoped production readiness verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.autopilot import ScheduledJob, SetupRun
from app.models.bot import Bot
from app.models.push_subscription import PushSubscription
from app.models.tenant import Tenant
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount
from app.services.audit_log_service import AuditLogService
from app.services.autopilot_service import AutopilotService
from app.services.system_event_service import SystemEventService


class SystemVerificationService:
    """Runs safe checks without sending messages, calls, or paid provider requests."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _check(
        key: str,
        label: str,
        status: str,
        message: str,
        *,
        critical: bool = False,
        action_url: str | None = None,
        meta: dict | None = None,
    ) -> dict:
        return {
            "key": key,
            "label": label,
            "status": status,
            "message": message,
            "critical": critical,
            "action_url": action_url,
            "meta": meta or {},
        }

    def run(self, tenant: Tenant, user: User | None = None) -> dict:
        checks: list[dict] = []

        try:
            self.db.execute(text("SELECT 1"))
            checks.append(self._check("database", "Veritabanı", "passed", "Veritabanı bağlantısı çalışıyor.", critical=True))
        except Exception:
            self.db.rollback()
            checks.append(self._check("database", "Veritabanı", "failed", "Veritabanı sağlık kontrolü başarısız.", critical=True))

        active_bot = self.db.query(Bot).filter(
            Bot.tenant_id == tenant.id,
            Bot.is_active.is_(True),
        ).first()
        checks.append(self._check(
            "active_bot",
            "İşletme asistanı",
            "passed" if active_bot else "failed",
            "Aktif işletme asistanı hazır." if active_bot else "Aktif bot bulunamadı; Autopilot'u çalıştırın.",
            critical=True,
            action_url="/dashboard/bots" if not active_bot else None,
        ))

        profile = dict((tenant.settings or {}).get("business_profile") or {})
        profile_ready = profile.get("status") == "ready" and bool(str(profile.get("summary") or "").strip())
        checks.append(self._check(
            "business_profile",
            "İşletme bilgisi",
            "passed" if profile_ready else "failed",
            "İşletme bilgi formasyonu hazır." if profile_ready else "İşletme özeti tamamlanmadan güvenilir özel yanıt üretilemez.",
            critical=True,
            action_url="/dashboard/bots" if not profile_ready else None,
        ))

        diagnostics = AutopilotService(self.db).run_diagnostics(tenant)
        provider_map = {item["provider"]: item for item in diagnostics["items"]}
        for provider, label, critical in (
            ("openai", "Yapay zeka", True),
            ("whatsapp", "WhatsApp", True),
            ("n8n", "Otomasyon", False),
            ("google", "Google Calendar", False),
            ("email", "E-posta", False),
            ("artifacts", "Dosya depolama", False),
            ("voice", "AI arama", False),
        ):
            item = provider_map.get(provider) or {}
            connected = item.get("status") in {"connected", "dry_run"}
            checks.append(self._check(
                f"provider_{provider}",
                label,
                "passed" if connected else ("failed" if critical else "warning"),
                str(item.get("message") or "Entegrasyon durumu alınamadı."),
                critical=critical,
                action_url=item.get("action_url"),
                meta={"provider_status": item.get("status")},
            ))

        now = utc_now()
        jobs = self.db.query(ScheduledJob).order_by(ScheduledJob.updated_at.desc()).all()
        fresh_jobs = []
        for job in jobs:
            last_success = self._aware(job.last_success_at)
            freshness = timedelta(seconds=max(900, int(job.interval_seconds or 300) * 3))
            if last_success and now - last_success <= freshness:
                fresh_jobs.append(job.name)
        worker_ok = bool(fresh_jobs)
        checks.append(self._check(
            "worker",
            "Arka plan worker",
            "passed" if worker_ok else "failed",
            "Worker görevleri güncel çalışıyor." if worker_ok else "Yakın zamanda başarılı worker görevi görülmedi.",
            critical=True,
            action_url="/admin/system-events" if not worker_ok else None,
            meta={"fresh_jobs": fresh_jobs[:12]},
        ))

        appointment_settings = dict((tenant.settings or {}).get("appointment_settings") or {})
        appointment_ready = bool(appointment_settings.get("configured"))
        checks.append(self._check(
            "appointments",
            "Randevu uygunluğu",
            "passed" if appointment_ready else "warning",
            "Çalışma saatleri ve hizmetler tanımlı." if appointment_ready else "Randevu kullanılacaksa çalışma saatlerini tanımlayın.",
            action_url="/dashboard/appointments" if not appointment_ready else None,
        ))

        push_count = self.db.query(PushSubscription).filter(
            PushSubscription.tenant_id == tenant.id,
            PushSubscription.enabled.is_(True),
        ).count()
        checks.append(self._check(
            "push_notifications",
            "Telefon bildirimleri",
            "passed" if push_count else "warning",
            "Aktif cihaz bildirimi var." if push_count else "Telefon bildirimi henüz etkinleştirilmemiş.",
            action_url="/dashboard/settings" if not push_count else None,
            meta={"active_subscriptions": push_count},
        ))

        if settings.OPENWA_ENABLED:
            active_openwa = self.db.query(WhatsAppAccount).filter(
                WhatsAppAccount.provider == "openwa",
                WhatsAppAccount.is_active.is_(True),
            ).count()
            capacity = max(1, settings.OPENWA_MAX_ACTIVE_SESSIONS)
            remaining = max(0, capacity - active_openwa)
            capacity_ok = active_openwa <= capacity
            checks.append(self._check(
                "openwa_capacity",
                "WhatsApp QR kapasitesi",
                "passed" if capacity_ok and remaining > 0 else ("warning" if capacity_ok else "failed"),
                f"{active_openwa}/{capacity} aktif QR oturumu kullanılıyor.",
                critical=not capacity_ok,
                action_url="/admin/launch" if remaining == 0 else None,
                meta={"active": active_openwa, "capacity": capacity, "remaining": remaining},
            ))

        failed_critical = [item for item in checks if item["critical"] and item["status"] == "failed"]
        warnings = [item for item in checks if item["status"] == "warning"]
        score_values = {"passed": 100, "warning": 65, "failed": 0}
        score = int(round(sum(score_values[item["status"]] for item in checks) / max(1, len(checks))))
        ready = not failed_critical
        result = {
            "status": "ready" if ready else "blocked",
            "ready_for_launch": ready,
            "score": score,
            "checked_at": now.isoformat(),
            "summary": "Sistem satış kullanımı için hazır." if ready else f"{len(failed_critical)} kritik kontrol tamamlanmalı.",
            "failed_critical": [item["key"] for item in failed_critical],
            "warning_count": len(warnings),
            "checks": checks,
        }

        setup_run = SetupRun(
            tenant_id=tenant.id,
            triggered_by_user_id=user.id if user else None,
            status="completed" if ready else "blocked",
            summary=f"SYSTEM_VERIFICATION:{result['status']}:{score}",
            actions_json=checks,
            required_actions_json=[item for item in checks if item["status"] != "passed"],
            finished_at=now,
        )
        self.db.add(setup_run)
        self.db.commit()

        if user:
            AuditLogService(self.db).log(
                action="system.verification.run",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                resource_type="setup_run",
                resource_id=str(setup_run.id),
                payload={"status": result["status"], "score": score, "failed_critical": result["failed_critical"]},
            )
        SystemEventService(self.db).log(
            tenant_id=str(tenant.id),
            source="verification",
            level="info" if ready else "warning",
            code="SYSTEM_VERIFICATION_COMPLETED",
            message=result["summary"],
            meta_json={"score": score, "failed_critical": result["failed_critical"], "warning_count": len(warnings)},
        )
        result["run_id"] = str(setup_run.id)
        return result

