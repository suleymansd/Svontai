# Routers module
from app.api.routers.auth import router as auth_router
from app.api.routers.users import router as users_router
from app.api.routers.tenants import router as tenants_router
from app.api.routers.bots import router as bots_router
from app.api.routers.knowledge import router as knowledge_router
from app.api.routers.conversations import router as conversations_router
from app.api.routers.leads import router as leads_router
from app.api.routers.whatsapp import router as whatsapp_router
from app.api.routers.public import router as public_router
from app.api.routers.admin import router as admin_router
from app.api.routers.onboarding import router as onboarding_router
from app.api.routers.whatsapp_webhook import router as whatsapp_webhook_router
from app.api.routers.subscription import router as subscription_router
from app.api.routers.tenant_onboarding import router as tenant_onboarding_router
from app.api.routers.analytics import router as analytics_router
from app.api.routers.operator import router as operator_router
from app.api.routers.channels import router as channels_router
from app.api.routers.automation import router as automation_router
from app.api.routers.me import router as me_router
from app.api.routers.feature_flags import router as feature_flags_router
from app.api.routers.system_events import router as system_events_router
from app.api.routers.incidents import router as incidents_router
from app.api.routers.tickets import router as tickets_router
from app.api.routers.appointments import router as appointments_router
from app.api.routers.notes import router as notes_router
from app.api.routers.payments import router as payments_router
from app.api.routers.api_keys import router as api_keys_router
from app.api.routers.real_estate import router as real_estate_router
from app.api.routers.webhooks_alias import router as webhooks_alias_router

__all__ = [
    "auth_router",
    "users_router",
    "tenants_router",
    "bots_router",
    "knowledge_router",
    "conversations_router",
    "leads_router",
    "whatsapp_router",
    "public_router",
    "admin_router",
    "onboarding_router",
    "whatsapp_webhook_router",
    "subscription_router",
    "tenant_onboarding_router",
    "analytics_router",
    "operator_router",
    "channels_router",
    "automation_router",
    "me_router",
    "feature_flags_router",
    "system_events_router",
    "incidents_router",
    "tickets_router",
    "appointments_router",
    "notes_router",
    "payments_router",
    "api_keys_router",
    "real_estate_router",
    "webhooks_alias_router"
]
