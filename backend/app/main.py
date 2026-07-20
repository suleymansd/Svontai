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
from app.core.rate_limit import global_ip_rate_limiter, rate_limit_key
from app.core.observability import configure_observability
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
    voice_automation_router,
    debug_router,
    n8n_dev_token_router,
    tool_runner_router,
    assistant_router,
    integrations_router,
    notifications_router,
    billing_router,
    setup_autopilot_router,
    agency_router,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if (settings.ENVIRONMENT == "dev" or settings.TOOL_RUNNER_DEBUG) else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
configure_observability("api")


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


def _ensure_conversations_schema_compatibility() -> None:
    """
    Ensure critical conversation columns exist for backward-compatible deployments.
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        bind = db.get_bind()
        inspector = inspect(bind)
        table_names = set(inspector.get_table_names())
        if "conversations" not in table_names:
            return

        conversation_columns = {column["name"] for column in inspector.get_columns("conversations")}
        statements: list[str] = []
        if "source" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN source VARCHAR(50) NOT NULL DEFAULT 'whatsapp'")
        if "status" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'ai_active'")
        if "is_ai_paused" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN is_ai_paused BOOLEAN NOT NULL DEFAULT 0")
        if "operator_id" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN operator_id VARCHAR(36) NULL")
        if "takeover_at" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN takeover_at DATETIME NULL")
        if "has_lead" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN has_lead BOOLEAN NOT NULL DEFAULT 0")
        if "lead_score" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN lead_score INTEGER NOT NULL DEFAULT 0")
        if "summary" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN summary TEXT NULL")
        if "tags" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN tags JSON NOT NULL DEFAULT '[]'")
        if "extra_data" not in conversation_columns:
            statements.append("ALTER TABLE conversations ADD COLUMN extra_data JSON NOT NULL DEFAULT '{}'")

        if statements:
            for statement in statements:
                db.execute(text(statement))
            db.commit()
            logger.warning("Applied conversation schema compatibility patch: %s", ", ".join(statements))
    finally:
        db.close()


def _ensure_messages_schema_compatibility() -> None:
    """
    Ensure critical message columns exist for backward-compatible deployments.
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        bind = db.get_bind()
        inspector = inspect(bind)
        table_names = set(inspector.get_table_names())
        if "messages" not in table_names:
            return

        message_columns = {column["name"] for column in inspector.get_columns("messages")}
        statements: list[str] = []
        if "external_id" not in message_columns:
            statements.append("ALTER TABLE messages ADD COLUMN external_id VARCHAR(255) NULL")

        if statements:
            for statement in statements:
                db.execute(text(statement))
            db.commit()
            logger.warning("Applied message schema compatibility patch: %s", ", ".join(statements))
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
    if settings.TOOL_RUNNER_DEBUG:
        logger.info(
            "Tool runner startup debug USE_N8N=%s N8N_BASE_URL=%s "\
            "N8N_INTERNAL_RUN_ENDPOINT_TEMPLATE=%s N8N_TOOL_RUNNER_WORKFLOW_ID=%s",
            settings.USE_N8N,
            settings.N8N_BASE_URL,
            settings.N8N_INTERNAL_RUN_ENDPOINT_TEMPLATE,
            settings.N8N_TOOL_RUNNER_WORKFLOW_ID,
        )

    reminder_task: asyncio.Task | None = None
    real_estate_task: asyncio.Task | None = None
    if settings.RUN_SCHEDULED_JOBS_IN_WEB:
        logger.warning("Scheduled jobs are running in the web process; use only for local development")
        if settings.APPOINTMENT_REMINDER_ENABLED and settings.EMAIL_ENABLED:
            reminder_task = asyncio.create_task(_appointment_reminder_loop())
        if settings.REAL_ESTATE_AUTOMATION_ENABLED:
            real_estate_task = asyncio.create_task(_real_estate_automation_loop())
    
    # Initialize default plans if needed
    from app.db.session import SessionLocal
    from app.services.subscription_service import SubscriptionService
    from app.services.rbac_service import RbacService
    from app.services.tool_seed_service import seed_initial_tools
    
    initializers = (
        ("plans", lambda db: SubscriptionService(db).get_or_create_free_plan()),
        ("RBAC", lambda db: RbacService(db).ensure_defaults()),
        ("tool catalog", seed_initial_tools),
    )
    for initializer_name, initializer in initializers:
        db = SessionLocal()
        try:
            initializer(db)
            logger.info("Default %s initialized", initializer_name)
        except Exception as exc:
            db.rollback()
            logger.warning("Could not initialize %s: %s", initializer_name, exc)
        finally:
            db.close()

    if settings.ENVIRONMENT == "dev":
        try:
            _ensure_leads_schema_compatibility()
        except Exception as exc:
            logger.warning("Could not apply leads schema compatibility patch: %s", exc)

        try:
            _ensure_conversations_schema_compatibility()
        except Exception as exc:
            logger.warning("Could not apply conversations schema compatibility patch: %s", exc)

        try:
            _ensure_messages_schema_compatibility()
        except Exception as exc:
            logger.warning("Could not apply messages schema compatibility patch: %s", exc)

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




@app.middleware("http")
async def global_rate_limit_middleware(request: Request, call_next):
    if request.url.path not in {"/", "/health", "/health/live", "/health/ready"} and not global_ip_rate_limiter.allow(rate_limit_key(request, "global")):
        return JSONResponse(
            status_code=429,
            content={"detail": "Çok fazla istek. Lütfen birkaç dakika sonra tekrar deneyin."},
        )
    return await call_next(request)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Return generic error in production
    if settings.ENVIRONMENT == "prod":
        return JSONResponse(
            status_code=500,
            content={"detail": "Bir hata olu\u015ftu. L\u00fctfen daha sonra tekrar deneyin."}
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
app.include_router(voice_automation_router)
app.include_router(calls_router)
app.include_router(telephony_router)
app.include_router(tool_runner_router)
app.include_router(assistant_router)
app.include_router(integrations_router)
app.include_router(notifications_router)
app.include_router(billing_router)
app.include_router(setup_autopilot_router)
app.include_router(agency_router)

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
    """Backward-compatible readiness endpoint for monitoring."""
    return await health_ready()


@app.get("/health/live")
async def health_live():
    """Process liveness check that has no external dependencies."""
    return {"status": "alive", "environment": settings.ENVIRONMENT}


@app.get("/health/ready")
async def health_ready():
    """Readiness check for the database and distributed rate limiter."""
    from app.core.health import readiness_status

    ready, payload = await readiness_status()
    if not ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "dev"
    )
