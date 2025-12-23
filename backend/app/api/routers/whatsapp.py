"""
WhatsApp webhook and integration router.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.whatsapp import WhatsAppIntegration
from app.models.conversation import Conversation, ConversationSource
from app.models.message import Message, MessageSender
from app.models.knowledge import BotKnowledgeItem
from app.schemas.whatsapp import (
    WhatsAppIntegrationCreate,
    WhatsAppIntegrationResponse,
    WhatsAppIntegrationUpdate
)
from app.services.whatsapp_service import whatsapp_service
from app.services.ai_service import ai_service

router = APIRouter(tags=["WhatsApp"])


# ============= Webhook Endpoints =============

@router.get("/whatsapp/webhook")
async def verify_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> Response:
    """
    Verify webhook for WhatsApp Cloud API.
    Meta will call this endpoint to verify the webhook.
    
    Query params:
        hub.mode: Should be "subscribe"
        hub.verify_token: Your verify token
        hub.challenge: Challenge to return
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if not all([mode, token, challenge]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing verification parameters"
        )
    
    # Find integration with this verify token
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.webhook_verify_token == token,
        WhatsAppIntegration.is_active == True
    ).first()
    
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid verify token"
        )
    
    result = whatsapp_service.verify_webhook(mode, token, challenge, token)
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification failed"
        )
    
    return Response(content=result, media_type="text/plain")


@router.post("/whatsapp/webhook")
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> dict:
    """
    Receive incoming WhatsApp messages.
    This endpoint processes incoming messages and sends AI-generated responses.
    """
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ok"}
    
    # Parse the incoming message
    parsed = whatsapp_service.parse_incoming_message(payload)
    
    if parsed is None:
        # Not a message event, return success
        return {"status": "ok"}
    
    phone_number_id = parsed.get("phone_number_id")
    sender_phone = parsed.get("from")
    message_text = parsed.get("text", "")
    
    if not all([phone_number_id, sender_phone, message_text]):
        return {"status": "ok"}
    
    # Find the integration by phone number ID
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.whatsapp_phone_number_id == phone_number_id,
        WhatsAppIntegration.is_active == True
    ).first()
    
    if integration is None or integration.bot_id is None:
        return {"status": "no_integration"}
    
    # Get the bot
    bot = db.query(Bot).filter(
        Bot.id == integration.bot_id,
        Bot.is_active == True
    ).first()
    
    if bot is None:
        return {"status": "no_bot"}
    
    # Find or create conversation
    conversation = db.query(Conversation).filter(
        Conversation.bot_id == bot.id,
        Conversation.external_user_id == sender_phone,
        Conversation.source == ConversationSource.WHATSAPP.value
    ).first()
    
    if conversation is None:
        conversation = Conversation(
            bot_id=bot.id,
            external_user_id=sender_phone,
            source=ConversationSource.WHATSAPP.value,
            extra_data={"contact_name": parsed.get("contact_name", "")}
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        sender=MessageSender.USER.value,
        content=message_text,
        raw_payload=parsed.get("raw_payload")
    )
    db.add(user_message)
    db.commit()
    
    # Get knowledge items for AI context
    knowledge_items = db.query(BotKnowledgeItem).filter(
        BotKnowledgeItem.bot_id == bot.id
    ).all()
    
    # Generate AI response
    ai_response = await ai_service.generate_reply(
        bot=bot,
        knowledge_items=knowledge_items,
        conversation=conversation,
        last_user_message=message_text
    )
    
    # Save bot message
    bot_message = Message(
        conversation_id=conversation.id,
        sender=MessageSender.BOT.value,
        content=ai_response
    )
    db.add(bot_message)
    db.commit()
    
    # Send response via WhatsApp
    try:
        await whatsapp_service.send_message(
            integration=integration,
            recipient_phone=sender_phone,
            message=ai_response
        )
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
    
    return {"status": "ok"}


# ============= Integration Management Endpoints =============

@router.post("/bots/{bot_id}/whatsapp-integration", response_model=WhatsAppIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_whatsapp_integration(
    bot_id: UUID,
    integration_data: WhatsAppIntegrationCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
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
    
    return integration


@router.get("/bots/{bot_id}/whatsapp-integration", response_model=WhatsAppIntegrationResponse | None)
async def get_whatsapp_integration(
    bot_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
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

