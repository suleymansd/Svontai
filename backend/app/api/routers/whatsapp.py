"""
WhatsApp webhook and integration router.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.whatsapp import WhatsAppIntegration
from app.models.user import User
from app.schemas.whatsapp import (
    WhatsAppIntegrationCreate,
    WhatsAppIntegrationResponse
)
from app.services.audit_log_service import AuditLogService

router = APIRouter(tags=["WhatsApp"])


# ============= Integration Management Endpoints =============

@router.post("/bots/{bot_id}/whatsapp-integration", response_model=WhatsAppIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_whatsapp_integration(
    bot_id: UUID,
    integration_data: WhatsAppIntegrationCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["settings:write"]))
) -> WhatsAppIntegration:
    """
    Create or update WhatsApp integration for a bot.
    
    Args:
        bot_id: The bot ID.
        integration_data: WhatsApp integration credentials.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The created/updated integration.
    """
    # Verify bot belongs to tenant
    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        Bot.tenant_id == current_tenant.id
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot bulunamadı"
        )
    
    # Check for existing integration
    existing = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.bot_id == bot_id
    ).first()
    
    if existing:
        # Update existing
        existing.whatsapp_phone_number_id = integration_data.whatsapp_phone_number_id
        existing.whatsapp_business_account_id = integration_data.whatsapp_business_account_id
        existing.access_token = integration_data.access_token
        existing.webhook_verify_token = integration_data.webhook_verify_token
        db.commit()
        db.refresh(existing)
        AuditLogService(db).log(
            action="whatsapp.integration.update",
            tenant_id=str(current_tenant.id),
            user_id=str(current_user.id),
            resource_type="whatsapp_integration",
            resource_id=str(existing.id),
            payload={
                "bot_id": str(bot_id),
                "waba_id": integration_data.whatsapp_business_account_id,
                "phone_number_id": integration_data.whatsapp_phone_number_id
            },
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("User-Agent") if request else None
        )
        return existing
    
    # Create new
    integration = WhatsAppIntegration(
        tenant_id=current_tenant.id,
        bot_id=bot_id,
        whatsapp_phone_number_id=integration_data.whatsapp_phone_number_id,
        whatsapp_business_account_id=integration_data.whatsapp_business_account_id,
        access_token=integration_data.access_token,
        webhook_verify_token=integration_data.webhook_verify_token
    )
    
    db.add(integration)
    db.commit()
    db.refresh(integration)

    AuditLogService(db).log(
        action="whatsapp.integration.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="whatsapp_integration",
        resource_id=str(integration.id),
        payload={
            "bot_id": str(bot_id),
            "waba_id": integration_data.whatsapp_business_account_id,
            "phone_number_id": integration_data.whatsapp_phone_number_id
        },
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    
    return integration


@router.get("/bots/{bot_id}/whatsapp-integration", response_model=WhatsAppIntegrationResponse | None)
async def get_whatsapp_integration(
    bot_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> WhatsAppIntegration | None:
    """
    Get WhatsApp integration for a bot.
    
    Args:
        bot_id: The bot ID.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The WhatsApp integration or None.
    """
    # Verify bot belongs to tenant
    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        Bot.tenant_id == current_tenant.id
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot bulunamadı"
        )
    
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.bot_id == bot_id
    ).first()
    
    return integration
