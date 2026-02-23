"""
SvontAi - WhatsApp Business AI Assistant
Main FastAPI application entry point.
"""

import logging
import asyncio
from contextlib import asynccontextmanager, suppress

from sqlalchemy import func, inspect, text

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.routers import (
    auth_router,
    users_router,
    tenants_router,
    bots_router,
    knowledge_router,
    conversations_router,
    leads_router,
    whatsapp_router,
    public_router,
    admin_router,
    onboarding_router,
    whatsapp_webhook_router,
    subscription_router,
    tenant_onboarding_router,
    analytics_router,
    operator_router,
    channels_router,
    n8n_tools_router,
    n8n_reply_router,
    automation_router,
    me_router,
    feature_flags_router,
    system_events_router,
    incidents_router,
    tickets_router,
    appointments_router,
    notes_router,
    payments_router,
    api_keys_router,
    real_estate_router,
    webhooks_alias_router,
    voice_events_router,
    calls_router,
    telephony_router,
    voice_intent_router,
    voice_call_summary_router,
    debug_router,
    n8n_dev_token_router,
    tool_runner_router,
    assistant_router,
    integrations_router,
    billing_router,
)

# TEMP runtime guard for production troubleshooting:
# confirms missing model modules and critical columns fail fast with clear log.
try:
    from app.models.tenant_tool import TenantTool  # noqa: F401
    from app.models.tool import Tool  # noqa: F401
    print("TenantTool import OK")
    print("Tool columns:", list(Tool.__table__.columns.keys()))
    if "slug" not in Tool.__table__.columns.keys():
        raise RuntimeError("Tool.slug column missing in model definition")
except Exception as e:  # pragma: no cover
    print("Tool/TenantTool import FAILED:", e)
    raise

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "dev" else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _ensure_leads_schema_compatibility() -> None:
    """
    Ensure critical lead columns exist for backward-compatible deployments.
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        bind = db.get_bind()
        inspector = inspect(bind)
        table_names = set(inspector.get_table_names())
        if "leads" not in table_names:
            return

        lead_columns = {column["name"] for column in inspector.get_columns("leads")}
        statements: list[str] = []
        if "status" not in lead_columns:
            statements.append("ALTER TABLE leads ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'new'")
        if "source" not in lead_columns:
            statements.append("ALTER TABLE leads ADD COLUMN source VARCHAR(50) NOT NULL DEFAULT 'web'")

        if statements:
            for statement in statements:
                db.execute(text(statement))
            db.commit()
            logger.warning("Applied lead schema compatibility patch: %s", ", ".join(statements))
    finally:
        db.close()


def _bootstrap_first_admin() -> None:
    """
    One-time bootstrap for first global admin user.
    """
    from app.db.session import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        existing_admin = db.query(User.id).filter(User.is_admin.is_(True)).first()
        if existing_admin:
            return

        bootstrap_email = (settings.BOOTSTRAP_ADMIN_EMAIL or "").strip().lower()
        if not bootstrap_email:
            logger.warning(
                "Bootstrap admin skipped: no admin user exists but BOOTSTRAP_ADMIN_EMAIL is empty."
            )
            return

        user = db.query(User).filter(func.lower(User.email) == bootstrap_email).first()
        if not user:
            logger.warning("Bootstrap admin skipped: user not found for %s", bootstrap_email)
            return

        user.is_admin = True
        db.commit()
        logger.warning("Bootstrap admin granted")
        logger.warning("Bootstrap admin executed for %s", user.email)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

async def _appointment_reminder_loop() -> None:
    from app.db.session import SessionLocal
    from app.services.appointment_reminder_service import AppointmentReminderService

    while True:
        try:
            def _dispatch() -> None:
                db = SessionLocal()
                try:
                    AppointmentReminderService(db).dispatch_due_reminders()
                finally:
                    db.close()

            await asyncio.to_thread(_dispatch)
        except Exception as exc:
            logger.warning("Appointment reminder loop error: %s", exc)

        await asyncio.sleep(settings.APPOINTMENT_REMINDER_INTERVAL_SECONDS)


async def _real_estate_automation_loop() -> None:
    from app.db.session import SessionLocal
    from app.services.real_estate_service import RealEstateService

    while True:
        try:
            db = SessionLocal()
            try:
                result = await RealEstateService(db).run_automation_cycle()
                if result.get("tenant_count", 0) > 0:
                    logger.info(
                        "Real Estate automation cycle completed: tenants=%s followups_sent=%s weekly_sent=%s",
                        result.get("tenant_count", 0),
                        result.get("followups", {}).get("sent", 0),
                        result.get("weekly_reports_sent", 0),
                    )
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Real Estate automation loop error: %s", exc)

        await asyncio.sleep(settings.REAL_ESTATE_AUTOMATION_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("SvontAi API starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    reminder_task: asyncio.Task | None = None
    real_estate_task: asyncio.Task | None = None
    if settings.APPOINTMENT_REMINDER_ENABLED and settings.EMAIL_ENABLED:
        reminder_task = asyncio.create_task(_appointment_reminder_loop())
    if settings.REAL_ESTATE_AUTOMATION_ENABLED:
        real_estate_task = asyncio.create_task(_real_estate_automation_loop())
    
    # Initialize default plans if needed
    from app.db.session import SessionLocal
    from app.services.subscription_service import SubscriptionService
    from app.services.rbac_service import RbacService
    
    try:
        db = SessionLocal()
        service = SubscriptionService(db)
        service.get_or_create_free_plan()
        RbacService(db).ensure_defaults()
        db.close()
        logger.info("Default plans initialized")
    except Exception as e:
        logger.warning(f"Could not initialize plans: {e}")

    try:
        _ensure_leads_schema_compatibility()
    except Exception as exc:
        logger.warning("Could not apply leads schema compatibility patch: %s", exc)

    try:
        _bootstrap_first_admin()
    except Exception as exc:
        logger.warning("Could not execute bootstrap admin flow: %s", exc)
    
    yield
    
    # Shutdown
    if reminder_task:
        reminder_task.cancel()
        with suppress(asyncio.CancelledError):
            await reminder_task
    if real_estate_task:
        real_estate_task.cancel()
        with suppress(asyncio.CancelledError):
            await real_estate_task
    logger.info("SvontAi API shutting down...")


# Create FastAPI application
app = FastAPI(
    title="SvontAi API",
    description="WhatsApp Business AI Assistant - RESTful API",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT == "dev" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "dev" else None,
    lifespan=lifespan
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Return generic error in production
    if settings.ENVIRONMENT == "prod":
        return JSONResponse(
            status_code=500,
            content={"detail": "Bir hata oluştu. Lütfen daha sonra tekrar deneyin."}
        )
    
    # Return detailed error in development
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__}
    )


# Configure CORS - Allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "dev" else [settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Include routers - Core
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(bots_router)
app.include_router(knowledge_router)
app.include_router(conversations_router)
app.include_router(leads_router)
app.include_router(public_router)

# Include routers - WhatsApp
app.include_router(whatsapp_router)
app.include_router(onboarding_router, prefix="/api")
app.include_router(whatsapp_webhook_router)

# Include routers - SaaS Features
app.include_router(subscription_router)
app.include_router(tenant_onboarding_router)
app.include_router(analytics_router)
app.include_router(operator_router)

# Include routers - Admin
app.include_router(admin_router)

# Include routers - n8n Channel Callbacks
app.include_router(channels_router)
app.include_router(n8n_tools_router)
app.include_router(n8n_reply_router)
app.include_router(n8n_dev_token_router)

# Include routers - Automation Settings
app.include_router(automation_router)
app.include_router(me_router)
app.include_router(feature_flags_router)
app.include_router(system_events_router)
app.include_router(incidents_router)
app.include_router(tickets_router)
app.include_router(appointments_router)
app.include_router(notes_router)
app.include_router(payments_router)
app.include_router(api_keys_router)
app.include_router(real_estate_router)
app.include_router(webhooks_alias_router)
app.include_router(voice_events_router)
app.include_router(voice_intent_router)
app.include_router(voice_call_summary_router)
app.include_router(calls_router)
app.include_router(telephony_router)
app.include_router(tool_runner_router)
app.include_router(assistant_router)
app.include_router(integrations_router)
app.include_router(billing_router)

# Temporary debug endpoints (development only)
if settings.ENVIRONMENT == "dev":
    app.include_router(debug_router)


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "name": "SvontAi API",
        "version": "1.0.0",
        "status": "healthy",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "dev"
    )
