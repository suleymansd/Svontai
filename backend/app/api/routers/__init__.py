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
    "operator_router"
]
