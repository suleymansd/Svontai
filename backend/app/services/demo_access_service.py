"""Customer demos are separate identities, never passwordless access to real accounts."""

import secrets
from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import RateLimiter, require_rate_limit
from app.core.security import create_access_token, create_refresh_token, get_password_hash, hash_token
from app.core.time import utc_now_naive
from app.models.bot import Bot
from app.models.bot_settings import BotSettings
from app.models.demo_access import DemoAccess
from app.models.knowledge import BotKnowledgeItem
from app.models.onboarding import AuditLog
from app.models.plan import Plan
from app.models.session import UserSession
from app.models.subscription import TenantSubscription
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.models.tenant_onboarding import TenantOnboarding
from app.models.user import User
from app.services.rbac_service import RbacService

demo_login_limiter = RateLimiter(30, 300, "demo-login")
demo_write_limiter = RateLimiter(60, 60, "demo-write")
AI_REQUEST_LIMIT = 200

# Keep credentials, billing and external side effects out of bearer-link demos.
DEMO_WRITE_PATHS = {
    "/auth/logout", "/bots", "/bots/{bot_id}", "/bots/{bot_id}/simulate",
    "/bots/assistant-profile/training", "/bots/assistant-profile/capabilities/{capability_key}",
    "/bots/assistant-profile/trainer/message", "/bots/assistant-profile/trainer/{session_id}/apply",
    "/bots/{bot_id}/knowledge", "/bots/{bot_id}/knowledge/{item_id}",
    "/leads", "/leads/{lead_id}", "/notes", "/notes/{note_id}",
    "/appointments", "/appointments/{appointment_id}", "/appointments/settings",
    "/product-analytics/events",
}


def ensure_demo_active(demo: DemoAccess) -> None:
    if demo.revoked_at or demo.expires_at <= utc_now_naive():
        raise HTTPException(403, detail={"code": "DEMO_ACCESS_ENDED", "message": "Bu özel erişim bağlantısı artık aktif değil. SvontAI ekibiyle iletişime geçin."})


def guard_demo_request(db: Session, user: User, request: Request | None = None) -> DemoAccess | None:
    demo = db.query(DemoAccess).filter(DemoAccess.user_id == user.id).first()
    if demo is None:
        return None
    ensure_demo_active(demo)
    if user.is_admin:
        raise HTTPException(403, detail="Demo hesabına yönetici erişimi verilemez.")
    if request is None:
        return demo
    path = getattr(request.scope.get("route"), "path", request.url.path)
    denied_read = path in {"/integrations/google/start", "/api/onboarding/whatsapp/openwa/qr"}
    is_write = request.method not in {"GET", "HEAD", "OPTIONS"}
    if denied_read or (is_write and path not in DEMO_WRITE_PATHS):
        raise HTTPException(403, detail={"code": "DEMO_ACTION_UNAVAILABLE", "message": "Bu işlem canlı hesap gerektiriyor. Özel erişimde AI asistanını, müşterileri, notları ve randevuları test edebilirsiniz."})
    if is_write:
        require_rate_limit(demo_write_limiter, str(demo.id))
    if path in {"/bots/{bot_id}/simulate", "/bots/assistant-profile/trainer/message"} and is_write:
        # Reserve before provider invocation, atomically across all API instances.
        result = db.execute(update(DemoAccess).where(
            DemoAccess.id == demo.id,
            DemoAccess.ai_requests_used < AI_REQUEST_LIMIT,
            DemoAccess.revoked_at.is_(None),
            DemoAccess.expires_at > utc_now_naive(),
        ).values(ai_requests_used=DemoAccess.ai_requests_used + 1))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(429, detail="Bu test alanının AI kullanım sınırına ulaşıldı. SvontAI ekibiyle iletişime geçin.")
        db.commit()
    return demo


def prevent_public_demo_bot(db: Session, bot: Bot) -> None:
    if db.query(DemoAccess.id).filter(DemoAccess.tenant_id == bot.tenant_id).first():
        raise HTTPException(403, detail="Özel erişim asistanı yalnızca panelde test edilebilir.")


class DemoAccessService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def new_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def url(token: str) -> str:
        # Fragments do not travel in HTTP request URLs, referrers or access logs.
        return f"{settings.FRONTEND_URL.rstrip('/')}/demo#token={token}"

    def create(self, name: str, days: int, admin: User) -> tuple[DemoAccess, str]:
        rbac = RbacService(self.db)
        rbac.ensure_defaults()
        role = rbac.get_role_by_name("owner")
        plan = self.db.query(Plan).filter(Plan.name == "premium", Plan.is_active.is_(True)).first()
        if plan is None:
            raise HTTPException(409, detail="Aktif Premium plan bulunamadı.")
        if role is None:
            raise HTTPException(503, detail="İşletme rolü hazır değil.")
        now = utc_now_naive()
        token = self.new_token()
        user = User(
            id=uuid4(), email=f"demo-{uuid4().hex}@demo.svontai.com",
            full_name=name, password_hash=get_password_hash(secrets.token_urlsafe(32)),
            is_active=True, is_admin=False, email_verified=False,
        )
        self.db.add(user)
        self.db.flush()
        tenant = Tenant(id=uuid4(), name=name, owner_id=user.id, settings={
            "provisioning_source": "private_demo",
            "daily_operational_report_enabled": False,
            "weekly_operational_report_enabled": False,
            "operational_report_email_enabled": False,
        })
        self.db.add(tenant)
        self.db.flush()
        demo = DemoAccess(
            name=name, token_hash=hash_token(token), user_id=user.id, tenant_id=tenant.id,
            created_by=admin.id, created_at=now, expires_at=now + timedelta(days=days),
        )
        self.db.add(demo)
        self.db.add(TenantMembership(tenant_id=tenant.id, user_id=user.id, role_id=role.id, status="active"))
        self.db.add(TenantSubscription(
            tenant_id=tenant.id, plan_id=plan.id, status="trial", started_at=now,
            trial_ends_at=demo.expires_at, current_period_start=now, current_period_end=demo.expires_at,
            extra_data={"source": "private_demo"},
        ))
        onboarding = TenantOnboarding.create_default(tenant.id)
        onboarding.dismissed = True
        onboarding.dismissed_at = now
        self.db.add(onboarding)
        bot = Bot(id=uuid4(), tenant_id=tenant.id, name=f"{name} Asistanı", assistant_type="primary", is_active=True)
        self.db.add(bot)
        self.db.flush()
        self.db.add(BotSettings(bot_id=bot.id, response_tone="professional", enable_guardrails=True))
        self.db.add(BotKnowledgeItem(
            bot_id=bot.id, title="Örnek bilgi: özel test alanı",
            question="Bu alanda neler deneyebilirim?",
            answer="Bu özel alanda AI asistanıyla konuşabilir, işletme bilgilerinizi ekleyebilir, müşteri kayıtlarını, notları ve randevuları test edebilirsiniz. Bu bilgi örnek amaçlıdır; kendi hizmet bilgilerinizi ekleyebilirsiniz.",
        ))
        self.db.flush()
        self.audit(demo, admin.id, "demo_access.created")
        self.db.commit()
        return demo, token

    def audit(self, demo: DemoAccess, user_id, action: str):
        self.db.add(AuditLog(
            tenant_id=demo.tenant_id, user_id=user_id, action=action,
            resource_type="demo_access", resource_id=str(demo.id),
            payload_json={"expires_at": demo.expires_at.isoformat()},
        ))

    def revoke_sessions(self, demo: DemoAccess):
        self.db.query(UserSession).filter(UserSession.user_id == demo.user_id, UserSession.revoked_at.is_(None)).update(
            {"revoked_at": utc_now_naive()}, synchronize_session=False,
        )

    def enter(self, token: str, ip: str, user_agent: str) -> tuple[str, str]:
        demo = self.db.query(DemoAccess).filter(DemoAccess.token_hash == hash_token(token)).with_for_update().first()
        if demo is None:
            raise HTTPException(403, detail={"code": "DEMO_ACCESS_ENDED", "message": "Bu özel erişim bağlantısı geçersiz veya artık aktif değil."})
        ensure_demo_active(demo)
        user = self.db.get(User, demo.user_id)
        tenant = self.db.get(Tenant, demo.tenant_id)
        if not user or not user.is_active or user.is_admin or user.two_factor_enabled or not tenant or tenant.owner_id != user.id or (tenant.settings or {}).get("suspended"):
            raise HTTPException(403, detail="Bu özel erişim bağlantısı kullanılamıyor.")
        now = utc_now_naive()
        session_id = uuid4()
        claims = {"sub": str(user.id), "portal": "tenant", "mfa": False, "client": "web", "demo_access_id": str(demo.id)}
        refresh = create_refresh_token(claims, session_id=str(session_id))
        self.db.add(UserSession(
            id=session_id, user_id=user.id, refresh_token_hash=hash_token(refresh),
            ip_address=ip[:50], user_agent=user_agent[:500], created_at=now,
            expires_at=min(demo.expires_at, now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)),
        ))
        demo.last_used_at = now
        demo.visit_count += 1
        user.last_login = now
        self.audit(demo, user.id, "demo_access.entered")
        access = create_access_token({**claims, "sid": str(session_id)}, expires_delta=min(
            demo.expires_at - now, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        ))
        self.db.commit()
        return access, refresh
