"""Autonomous tenant setup and integration diagnostics."""

from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.autopilot import AgencyClient, IntegrationHealthCheck, SetupRun
from app.models.automation import AutomationRun
from app.models.bot import Bot
from app.models.google_oauth_token import GoogleOAuthToken
from app.models.incident import Incident
from app.models.knowledge import BotKnowledgeItem
from app.models.subscription import TenantSubscription
from app.models.tenant import Tenant
from app.models.ticket import Ticket
from app.models.tool_run import ToolRun
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount
from app.services.audit_log_service import AuditLogService
from app.services.billing_service import BillingService
from app.services.subscription_service import SubscriptionService
from app.services.system_event_service import SystemEventService


DEFAULT_BOT_NAME = "SmartWA Autopilot"
DEFAULT_KNOWLEDGE_TITLE = "Otonom çalışma prensibi"
DEFAULT_PROFILE_TITLE = "İşletme bilgi formasyonu"


class AutopilotService:
    """Safe autonomous setup, repair and health scoring for a tenant."""

    def __init__(self, db: Session):
        self.db = db

    def run(self, tenant: Tenant, user: User | None = None) -> dict:
        run = SetupRun(
            tenant_id=tenant.id,
            triggered_by_user_id=user.id if user else None,
            status="running",
            actions_json=[],
            required_actions_json=[],
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        actions: list[dict] = []
        required_actions: list[dict] = []

        subscription = SubscriptionService(self.db).get_subscription(tenant.id)
        if subscription is None:
            SubscriptionService(self.db).create_subscription(tenant.id, "free")
            actions.append({"key": "subscription_created", "label": "Varsayılan abonelik oluşturuldu"})

        business_profile = self._business_profile(tenant)
        bot = self.db.query(Bot).filter(Bot.tenant_id == tenant.id).order_by(Bot.created_at.asc()).first()
        if bot is None:
            bot = Bot(
                tenant_id=tenant.id,
                name=DEFAULT_BOT_NAME,
                description=self._bot_description(tenant, business_profile),
                welcome_message="Merhaba, size nasıl yardımcı olabilirim?",
                language="tr",
                primary_color="#2563EB",
                widget_position="right",
                is_active=True,
            )
            self.db.add(bot)
            self.db.commit()
            self.db.refresh(bot)
            actions.append({"key": "default_bot_created", "label": "Varsayılan autopilot bot oluşturuldu"})

        knowledge_exists = self.db.query(BotKnowledgeItem.id).filter(
            BotKnowledgeItem.bot_id == bot.id,
            BotKnowledgeItem.title == DEFAULT_KNOWLEDGE_TITLE,
        ).first()
        if not knowledge_exists:
            self.db.add(
                BotKnowledgeItem(
                    bot_id=bot.id,
                    title=DEFAULT_KNOWLEDGE_TITLE,
                    question="SmartWA hangi durumlarda otomatik aksiyon alır?",
                    answer=(
                        "SmartWA güvenli otonomi prensibiyle çalışır. Kurulum, tanılama, limit takibi, "
                        "retry ve incident üretimi otomatik yapılır; ödeme, dış servis izni ve müşteri adına "
                        "riskli mesaj gönderimi için kullanıcı onayı istenir."
                    ),
                )
            )
            self.db.commit()
            actions.append({"key": "default_knowledge_created", "label": "Temel bilgi tabanı eklendi"})

        profile_knowledge = self.db.query(BotKnowledgeItem.id).filter(
            BotKnowledgeItem.bot_id == bot.id,
            BotKnowledgeItem.title == DEFAULT_PROFILE_TITLE,
        ).first()
        if not profile_knowledge:
            self.db.add(
                BotKnowledgeItem(
                    bot_id=bot.id,
                    title=DEFAULT_PROFILE_TITLE,
                    question="Bu işletme hakkında nasıl davranmalısın?",
                    answer=self._profile_knowledge_answer(tenant, business_profile),
                )
            )
            self.db.commit()
            actions.append({"key": "profile_knowledge_created", "label": "İşletme bilgi formasyonu seed edildi"})

        diagnostics = self.run_diagnostics(tenant)
        for item in diagnostics["items"]:
            if item["requires_user_action"]:
                required_actions.append({
                    "key": f"{item['provider']}_action_required",
                    "label": item["message"],
                    "url": item.get("action_url"),
                })

        run.status = "completed"
        run.summary = "Autopilot setup completed"
        run.actions_json = actions
        run.required_actions_json = required_actions
        run.finished_at = utc_now()
        self.db.commit()

        if user:
            AuditLogService(self.db).log(
                action="autopilot.run",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                resource_type="setup_run",
                resource_id=str(run.id),
                payload={"actions": actions, "required_actions": required_actions},
            )

        SystemEventService(self.db).log(
            tenant_id=str(tenant.id),
            source="autopilot",
            level="info",
            code="AUTOPILOT_RUN_COMPLETED",
            message="Autopilot setup run completed",
            meta_json={"actions_count": len(actions), "required_actions_count": len(required_actions)},
        )

        return self.status(tenant)

    def status(self, tenant: Tenant) -> dict:
        diagnostics = self.run_diagnostics(tenant)
        latest_run = self.db.query(SetupRun).filter(SetupRun.tenant_id == tenant.id).order_by(SetupRun.created_at.desc()).first()
        settings = dict(tenant.settings or {})
        concierge = dict(settings.get("concierge_enrichment") or {})
        profile = dict(settings.get("business_profile") or {})
        required_actions = [
            {
                "key": f"{item['provider']}_action_required",
                "label": item["message"],
                "url": item.get("action_url"),
            }
            for item in diagnostics["items"]
            if item["requires_user_action"]
        ]
        health_score = diagnostics["health_score"]
        return {
            "tenant_id": str(tenant.id),
            "status": "ready" if health_score >= 80 and not required_actions else "needs_attention",
            "health_score": health_score,
            "safe_to_autorun": True,
            "concierge_enrichment": concierge or None,
            "business_profile": {
                "status": profile.get("status") or "unknown",
                "industry": profile.get("industry") or "unknown",
                "source": profile.get("source") or "unknown",
            },
            "missing_permissions": [item["provider"] for item in diagnostics["items"] if item["status"] in {"missing", "expired"}],
            "repairable_issues": [item for item in diagnostics["items"] if item["repairable"]],
            "required_user_actions": required_actions,
            "latest_run": {
                "id": str(latest_run.id),
                "status": latest_run.status,
                "summary": latest_run.summary,
                "created_at": latest_run.created_at.isoformat(),
                "finished_at": latest_run.finished_at.isoformat() if latest_run.finished_at else None,
            } if latest_run else None,
            "diagnostics": diagnostics["items"],
        }

    def repair_provider(self, tenant: Tenant, provider: str, user: User | None = None) -> dict:
        normalized = provider.strip().lower()
        if normalized in {"billing", "email", "artifacts", "openai", "n8n"}:
            diagnostics = self.run_diagnostics(tenant)
            item = next((entry for entry in diagnostics["items"] if entry["provider"] == normalized), None)
            if item and not item["requires_user_action"]:
                return {"status": "checked", "provider": normalized, "message": item["message"], "diagnostic": item}

        return {
            "status": "requires_user_action",
            "provider": normalized,
            "message": "Bu entegrasyon için kullanıcı izni veya dış servis yapılandırması gerekiyor.",
            "action_url": self._action_url_for_provider(normalized),
        }

    def run_diagnostics(self, tenant: Tenant) -> dict:
        items = [
            self._check_openai(tenant),
            self._check_n8n(tenant),
            self._check_whatsapp(tenant),
            self._check_google(tenant),
            self._check_billing(tenant),
            self._check_email(tenant),
            self._check_artifacts(tenant),
            self._check_voice(tenant),
        ]
        for item in items:
            self._upsert_health(tenant.id, item)
        health_score = int(round(sum(item["health_score"] for item in items) / max(1, len(items))))
        return {"health_score": health_score, "items": items}

    def _upsert_health(self, tenant_id: uuid.UUID, item: dict) -> None:
        row = self.db.query(IntegrationHealthCheck).filter(
            IntegrationHealthCheck.tenant_id == tenant_id,
            IntegrationHealthCheck.provider == item["provider"],
        ).first()
        if row is None:
            row = IntegrationHealthCheck(tenant_id=tenant_id, provider=item["provider"])
            self.db.add(row)
        row.status = item["status"]
        row.health_score = item["health_score"]
        row.message = item["message"]
        row.checks_json = item.get("checks", [])
        row.repairable = item.get("repairable", False)
        row.requires_user_action = item.get("requires_user_action", False)
        row.action_url = item.get("action_url")
        row.checked_at = utc_now()
        self.db.commit()

    def _item(self, provider: str, status: str, score: int, message: str, **extra) -> dict:
        return {
            "provider": provider,
            "status": status,
            "health_score": score,
            "message": message,
            "checks": extra.pop("checks", []),
            "repairable": extra.pop("repairable", False),
            "requires_user_action": extra.pop("requires_user_action", False),
            "action_url": extra.pop("action_url", self._action_url_for_provider(provider)),
            **extra,
        }

    def _check_openai(self, tenant: Tenant) -> dict:
        if settings.OPENAI_API_KEY.strip():
            return self._item("openai", "connected", 100, "OpenAI yapılandırması hazır.")
        return self._item("openai", "missing", 40, "OpenAI API anahtarı eksik.", repairable=False)

    def _check_n8n(self, tenant: Tenant) -> dict:
        if settings.USE_N8N and settings.N8N_BASE_URL.strip():
            return self._item("n8n", "connected", 90, "n8n bağlantı yapılandırması hazır.")
        return self._item("n8n", "missing", 45, "n8n kapalı veya URL eksik.", repairable=False)

    def _check_whatsapp(self, tenant: Tenant) -> dict:
        connected = self.db.query(WhatsAppAccount.id).filter(
            WhatsAppAccount.tenant_id == tenant.id,
            WhatsAppAccount.is_active == True,
            WhatsAppAccount.phone_number_id.isnot(None),
            WhatsAppAccount.access_token_encrypted.isnot(None),
        ).first()
        if connected:
            return self._item("whatsapp", "connected", 100, "WhatsApp Cloud bağlantısı aktif.")
        return self._item(
            "whatsapp",
            "missing",
            35,
            "WhatsApp bağlantısı için Meta Embedded Signup gerekiyor.",
            requires_user_action=True,
            action_url="/dashboard/setup/whatsapp",
        )

    def _check_google(self, tenant: Tenant) -> dict:
        token = self.db.query(GoogleOAuthToken).filter(
            GoogleOAuthToken.tenant_id == tenant.id,
            GoogleOAuthToken.provider == "google",
        ).first()
        if not token:
            return self._item("google", "missing", 55, "Google entegrasyonu bağlı değil.", requires_user_action=True, action_url="/dashboard/integrations")
        if token.expires_at and token.expires_at < utc_now().replace(tzinfo=token.expires_at.tzinfo):
            return self._item("google", "expired", 45, "Google token süresi dolmuş.", requires_user_action=True, action_url="/dashboard/integrations")
        return self._item("google", "connected", 95, "Google entegrasyonu aktif.")

    def _check_billing(self, tenant: Tenant) -> dict:
        subscription = self.db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant.id).first()
        if subscription:
            return self._item("billing", "connected", 95, "Billing ve plan durumu hazır.")
        return self._item("billing", "repairable", 70, "Varsayılan plan otomatik oluşturulabilir.", repairable=True)

    def _check_email(self, tenant: Tenant) -> dict:
        if settings.EMAIL_ENABLED:
            return self._item("email", "connected", 90, "E-posta gönderimi etkin.")
        return self._item("email", "missing", 60, "E-posta gönderimi kapalı; sistem içi bildirimler çalışır.", repairable=False)

    def _check_artifacts(self, tenant: Tenant) -> dict:
        if settings.ARTIFACT_STORAGE_PROVIDER == "supabase":
            ready = bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY and settings.SUPABASE_STORAGE_BUCKET)
            if ready:
                return self._item("artifacts", "connected", 90, "Supabase artifact storage hazır.")
            return self._item("artifacts", "missing", 50, "Supabase artifact storage eksik yapılandırılmış.")
        return self._item("artifacts", "connected", 75, "Local artifact storage etkin.")

    def _check_voice(self, tenant: Tenant) -> dict:
        secret = (settings.VOICE_GATEWAY_TO_SVONTAI_SECRET or "").strip()
        secret_ready = bool(secret) and "change-this" not in secret and secret != "change-me"
        if settings.VOICE_OUTBOUND_MODE == "live":
            live_ready = bool(
                secret_ready
                and settings.VOICE_GATEWAY_PUBLIC_URL.strip()
                and settings.TWILIO_ACCOUNT_SID.strip()
                and settings.TWILIO_AUTH_TOKEN.strip()
            )
            if live_ready:
                return self._item("voice", "connected", 95, "AI arama Twilio live outbound için hazır.")
            return self._item("voice", "missing", 45, "Canlı arama için Twilio ve voice gateway env değerleri eksik.", repairable=False)
        if secret_ready:
            return self._item("voice", "dry_run", 75, "AI arama dry-run modunda hazır; gerçek arama için VOICE_OUTBOUND_MODE=live gerekir.")
        return self._item("voice", "missing", 60, "AI arama dry-run çalışır; güvenli gateway secret gerçek değerle değiştirilmelidir.", repairable=False)

    def _action_url_for_provider(self, provider: str) -> str | None:
        return {
            "whatsapp": "/dashboard/setup/whatsapp",
            "google": "/dashboard/integrations",
            "billing": "/dashboard/billing",
            "email": "/dashboard/settings",
            "n8n": "/dashboard/settings",
            "openai": "/admin/settings",
            "artifacts": "/admin/settings",
            "voice": "/dashboard/calls",
        }.get(provider)

    def _business_profile(self, tenant: Tenant) -> dict:
        return dict((tenant.settings or {}).get("business_profile") or {})

    def _bot_description(self, tenant: Tenant, profile: dict) -> str:
        industry = (profile.get("industry") or "").strip()
        if industry and industry != "unknown":
            return f"{tenant.name} için {industry} odağında müşteri iletişimini güvenli otonomiyle yöneten asistan."
        return f"{tenant.name} için müşteri iletişimini güvenli otonomiyle yöneten varsayılan asistan."

    def _profile_knowledge_answer(self, tenant: Tenant, profile: dict) -> str:
        status = profile.get("status") or "needs_enrichment"
        services = profile.get("services") or []
        faq = profile.get("faq") or []
        summary = (profile.get("summary") or "").strip()
        if status == "ready" and (summary or services or faq):
            return (
                f"İşletme: {tenant.name}\n"
                f"Sektör: {profile.get('industry') or 'Belirtilmedi'}\n"
                f"Ton: {profile.get('tone') or 'professional'}\n"
                f"Özet: {summary or 'Belirtilmedi'}\n"
                f"Hizmetler: {', '.join(map(str, services)) if services else 'Belirtilmedi'}\n"
                "Müşteri sorularında bu işletme profilini esas al."
            )
        return (
            f"İşletme: {tenant.name}\n"
            "Bilgi formasyonu şirket ekibi tarafından hazırlanıyor. Bu süreç tamamlanana kadar net olmayan konularda "
            "genel, profesyonel ve temkinli yanıt ver; kesin fiyat, taahhüt veya dış servis aksiyonu için kullanıcı onayı iste."
        )


class AgencyService:
    """Agency-facing client summaries and health."""

    def __init__(self, db: Session):
        self.db = db
        self.autopilot = AutopilotService(db)

    def list_clients(self, agency_tenant: Tenant) -> list[dict]:
        relationships = self.db.query(AgencyClient).filter(
            AgencyClient.agency_tenant_id == agency_tenant.id,
            AgencyClient.status == "active",
        ).all()
        if not relationships:
            return [self._tenant_summary(agency_tenant, relationship=None)]

        clients: list[dict] = []
        for relationship in relationships:
            tenant = self.db.query(Tenant).filter(Tenant.id == relationship.client_tenant_id).first()
            if tenant:
                clients.append(self._tenant_summary(tenant, relationship=relationship))
        return clients

    def create_client_relationship(
        self,
        agency_tenant: Tenant,
        client_tenant_id: uuid.UUID,
        user: User,
        notes: str | None = None,
    ) -> dict:
        if agency_tenant.id == client_tenant_id:
            return {"created": False, "detail": "Ajans kendi tenant'ını müşteri olarak ekleyemez."}

        client_tenant = self.db.query(Tenant).filter(Tenant.id == client_tenant_id).first()
        if client_tenant is None:
            return {"created": False, "detail": "Client tenant bulunamadı."}

        relationship = self.db.query(AgencyClient).filter(
            AgencyClient.agency_tenant_id == agency_tenant.id,
            AgencyClient.client_tenant_id == client_tenant_id,
        ).first()
        if relationship is None:
            relationship = AgencyClient(
                agency_tenant_id=agency_tenant.id,
                client_tenant_id=client_tenant_id,
                status="active",
                notes=notes,
                created_by_user_id=user.id,
            )
            self.db.add(relationship)
            created = True
        else:
            relationship.status = "active"
            relationship.notes = notes if notes is not None else relationship.notes
            created = False

        self.db.commit()
        self.db.refresh(relationship)
        return {"created": created, "client": self._tenant_summary(client_tenant, relationship=relationship)}

    def update_client_relationship(
        self,
        agency_tenant: Tenant,
        relationship_id: uuid.UUID,
        status: str | None = None,
        notes: str | None = None,
    ) -> dict:
        relationship = self._relationship_for_agency(agency_tenant.id, relationship_id)
        if relationship is None:
            return {"found": False, "detail": "Ajans müşteri ilişkisi bulunamadı."}

        if status is not None:
            relationship.status = status
        if notes is not None:
            relationship.notes = notes
        self.db.commit()
        tenant = self.db.query(Tenant).filter(Tenant.id == relationship.client_tenant_id).first()
        return {"found": True, "client": self._tenant_summary(tenant, relationship=relationship) if tenant else None}

    def archive_client_relationship(self, agency_tenant: Tenant, relationship_id: uuid.UUID) -> dict:
        return self.update_client_relationship(agency_tenant, relationship_id, status="archived")

    def get_client_health(self, agency_tenant: Tenant, client_tenant_id: uuid.UUID) -> dict:
        if agency_tenant.id != client_tenant_id:
            relationship = self.db.query(AgencyClient).filter(
                AgencyClient.agency_tenant_id == agency_tenant.id,
                AgencyClient.client_tenant_id == client_tenant_id,
                AgencyClient.status == "active",
            ).first()
            if relationship is None:
                return {"found": False, "detail": "Client tenant bu ajansa bağlı değil."}

        tenant = self.db.query(Tenant).filter(Tenant.id == client_tenant_id).first()
        if tenant is None:
            return {"found": False, "detail": "Client tenant bulunamadı."}

        status = self.autopilot.status(tenant)
        return {
            "found": True,
            "client": self._tenant_summary(tenant, relationship=None),
            "autopilot": status,
            "recent_runs": self._recent_runs(tenant.id),
            "open_tickets": self._open_ticket_count(tenant.id),
            "open_incidents": self._open_incident_count(tenant.id),
        }

    def _tenant_summary(self, tenant: Tenant, relationship: AgencyClient | None) -> dict:
        billing = BillingService(self.db).get_limits_payload(tenant.id)
        health = self.autopilot.status(tenant)
        return {
            "tenant_id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "relationship_id": str(relationship.id) if relationship else None,
            "status": relationship.status if relationship else "self",
            "health_score": health["health_score"],
            "autopilot_status": health["status"],
            "plan": billing["plan"],
            "monthly_runs_used": billing["usage"]["monthly_runs_used"],
            "monthly_runs_limit": billing["limits"]["monthly_runs"],
            "open_tickets": self._open_ticket_count(tenant.id),
            "open_incidents": self._open_incident_count(tenant.id),
        }

    def _relationship_for_agency(self, agency_tenant_id: uuid.UUID, relationship_id: uuid.UUID) -> AgencyClient | None:
        return self.db.query(AgencyClient).filter(
            AgencyClient.id == relationship_id,
            AgencyClient.agency_tenant_id == agency_tenant_id,
        ).first()

    def _recent_runs(self, tenant_id: uuid.UUID) -> list[dict]:
        rows = self.db.query(AutomationRun).filter(AutomationRun.tenant_id == str(tenant_id)).order_by(AutomationRun.created_at.desc()).limit(5).all()
        return [
            {
                "id": str(row.id),
                "status": row.status,
                "channel": row.channel,
                "created_at": row.created_at.isoformat(),
                "error_message": row.error_message,
            }
            for row in rows
        ]

    def _open_ticket_count(self, tenant_id: uuid.UUID) -> int:
        return int(self.db.query(func.count(Ticket.id)).filter(Ticket.tenant_id == str(tenant_id), Ticket.status.in_(["open", "pending"])).scalar() or 0)

    def _open_incident_count(self, tenant_id: uuid.UUID) -> int:
        return int(self.db.query(func.count(Incident.id)).filter(Incident.tenant_id == str(tenant_id), Incident.status != "resolved").scalar() or 0)
