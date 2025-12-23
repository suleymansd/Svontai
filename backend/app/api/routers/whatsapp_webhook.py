"""
WhatsApp Webhook endpoint for receiving messages and events from Meta.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Request, Response, HTTPException, status, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.onboarding_service import OnboardingService
from app.services.meta_api import meta_api_service
from app.core.encryption import decrypt_token
from app.models.whatsapp_account import WhatsAppAccount

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Webhook"])


# Rate limiting state (in production, use Redis)
_webhook_requests = {}


def rate_limit_check(phone_number_id: str, max_per_minute: int = 100) -> bool:
    """
    Simple rate limiting check.
    In production, use Redis or a proper rate limiter.
    """
    import time
    current_time = int(time.time() / 60)  # Current minute
    key = f"{phone_number_id}:{current_time}"
    
    _webhook_requests[key] = _webhook_requests.get(key, 0) + 1
    
    # Clean old entries
    old_keys = [k for k in _webhook_requests if not k.endswith(f":{current_time}")]
    for k in old_keys:
        del _webhook_requests[k]
    
    return _webhook_requests[key] <= max_per_minute


@router.get("/webhook")
async def webhook_verification(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle webhook verification from Meta.
    
    Meta sends a GET request with:
    - hub.mode: should be "subscribe"
    - hub.verify_token: the token we set during webhook configuration
    - hub.challenge: random string to echo back
    """
    params = request.query_params
    
    mode = params.get("hub.mode")
    verify_token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    logger.info(f"Webhook verification request: mode={mode}, token={verify_token[:10]}...")
    
    if mode != "subscribe":
        logger.warning(f"Invalid webhook mode: {mode}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid mode"
        )
    
    if not verify_token:
        logger.warning("Missing verify token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing verify token"
        )
    
    # Find account by verify token
    service = OnboardingService(db)
    account = service.get_account_by_verify_token(verify_token)
    
    if not account:
        logger.warning(f"Invalid verify token: {verify_token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid verify token"
        )
    
    # Mark webhook as verified
    service.mark_webhook_verified(account.tenant_id)
    
    logger.info(f"Webhook verified for tenant {account.tenant_id}")
    
    # Return the challenge to confirm verification
    return Response(content=challenge, media_type="text/plain")


@router.post("/webhook")
async def webhook_events(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle incoming webhook events from Meta.
    
    Events include:
    - messages: incoming messages
    - message_status: delivery/read receipts
    - message_template_status_update: template status changes
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature (if available)
    signature = request.headers.get("X-Hub-Signature-256")
    if signature:
        if not meta_api_service.verify_webhook_signature(body, signature):
            logger.warning("Invalid webhook signature")
            # In production, you might want to reject invalid signatures
            # For now, we log and continue for debugging
    
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON"
        )
    
    logger.info(f"Webhook event received: {json.dumps(payload)[:500]}")
    
    # Acknowledge quickly (Meta expects response within 20 seconds)
    # Process in background
    background_tasks.add_task(process_webhook_event, payload, db)
    
    return {"status": "ok"}


async def process_webhook_event(payload: dict, db: Session):
    """
    Process webhook event in background.
    
    Args:
        payload: The webhook payload from Meta.
        db: Database session.
    """
    try:
        obj = payload.get("object")
        
        if obj != "whatsapp_business_account":
            logger.info(f"Ignoring non-WhatsApp webhook: {obj}")
            return
        
        entries = payload.get("entry", [])
        
        for entry in entries:
            waba_id = entry.get("id")
            changes = entry.get("changes", [])
            
            for change in changes:
                field = change.get("field")
                value = change.get("value", {})
                
                if field == "messages":
                    await process_message_event(waba_id, value, db)
                elif field == "message_template_status_update":
                    await process_template_status_event(waba_id, value, db)
                else:
                    logger.info(f"Ignoring webhook field: {field}")
    
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}", exc_info=True)


async def process_message_event(waba_id: str, value: dict, db: Session):
    """
    Process incoming message event.
    
    Args:
        waba_id: WhatsApp Business Account ID.
        value: The message value object.
        db: Database session.
    """
    metadata = value.get("metadata", {})
    phone_number_id = metadata.get("phone_number_id")
    display_phone_number = metadata.get("display_phone_number")
    
    # Rate limit check
    if not rate_limit_check(phone_number_id):
        logger.warning(f"Rate limit exceeded for {phone_number_id}")
        return
    
    # Find WhatsApp account
    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.phone_number_id == phone_number_id
    ).first()
    
    if not account:
        logger.warning(f"No account found for phone_number_id: {phone_number_id}")
        return
    
    contacts = value.get("contacts", [])
    messages = value.get("messages", [])
    
    for message in messages:
        message_id = message.get("id")
        from_number = message.get("from")
        timestamp = message.get("timestamp")
        message_type = message.get("type")
        
        # Get contact name if available
        contact_name = None
        for contact in contacts:
            if contact.get("wa_id") == from_number:
                profile = contact.get("profile", {})
                contact_name = profile.get("name")
                break
        
        logger.info(
            f"Message received: id={message_id}, from={from_number}, "
            f"type={message_type}, contact={contact_name}"
        )
        
        # Handle different message types
        content = None
        if message_type == "text":
            content = message.get("text", {}).get("body")
        elif message_type == "image":
            content = "[Image received]"
        elif message_type == "audio":
            content = "[Audio received]"
        elif message_type == "video":
            content = "[Video received]"
        elif message_type == "document":
            content = "[Document received]"
        elif message_type == "location":
            content = "[Location received]"
        elif message_type == "contacts":
            content = "[Contact received]"
        elif message_type == "interactive":
            # Button reply or list reply
            interactive = message.get("interactive", {})
            if "button_reply" in interactive:
                content = interactive["button_reply"].get("title")
            elif "list_reply" in interactive:
                content = interactive["list_reply"].get("title")
        
        if content:
            # TODO: Route to AI service for response
            # For now, just log
            logger.info(f"Message content: {content[:100]}")
            
            # Create conversation/message in database
            # This would connect to your existing bot/conversation system
            await handle_incoming_message(
                account=account,
                from_number=from_number,
                contact_name=contact_name,
                message_content=content,
                message_type=message_type,
                message_id=message_id,
                db=db
            )
    
    # Handle statuses (delivery, read receipts)
    statuses = value.get("statuses", [])
    for status_update in statuses:
        status_value = status_update.get("status")
        recipient_id = status_update.get("recipient_id")
        message_id = status_update.get("id")
        
        logger.info(
            f"Message status: id={message_id}, recipient={recipient_id}, "
            f"status={status_value}"
        )


async def process_template_status_event(waba_id: str, value: dict, db: Session):
    """
    Process template status update event.
    
    Args:
        waba_id: WhatsApp Business Account ID.
        value: The status update value.
        db: Database session.
    """
    event = value.get("event")
    message_template_id = value.get("message_template_id")
    message_template_name = value.get("message_template_name")
    
    logger.info(
        f"Template status update: name={message_template_name}, "
        f"event={event}"
    )
    
    # TODO: Update template status in database if you track templates


async def handle_incoming_message(
    account: WhatsAppAccount,
    from_number: str,
    contact_name: Optional[str],
    message_content: str,
    message_type: str,
    message_id: str,
    db: Session
):
    """
    Handle incoming message and generate AI response.
    
    This connects to the existing bot/AI system.
    """
    from app.models.bot import Bot
    from app.models.conversation import Conversation, ConversationSource
    from app.models.message import Message, MessageSender
    from app.models.knowledge import BotKnowledgeItem
    from app.services.ai_service import ai_service
    
    # Find a bot for this tenant
    bot = db.query(Bot).filter(
        Bot.tenant_id == account.tenant_id,
        Bot.is_active == True
    ).first()
    
    if not bot:
        logger.warning(f"No active bot found for tenant {account.tenant_id}")
        return
    
    # Find or create conversation
    conversation = db.query(Conversation).filter(
        Conversation.bot_id == bot.id,
        Conversation.external_user_id == from_number,
        Conversation.source == ConversationSource.WHATSAPP.value
    ).first()
    
    if not conversation:
        conversation = Conversation(
            bot_id=bot.id,
            external_user_id=from_number,
            customer_name=contact_name,
            customer_phone=from_number,
            source=ConversationSource.WHATSAPP.value
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    elif contact_name and not conversation.customer_name:
        conversation.customer_name = contact_name
        db.commit()
    
    # Save incoming message
    user_message = Message(
        conversation_id=conversation.id,
        sender=MessageSender.USER.value,
        content=message_content,
        external_id=message_id
    )
    db.add(user_message)
    db.commit()
    
    # Get knowledge items for context
    knowledge_items = db.query(BotKnowledgeItem).filter(
        BotKnowledgeItem.bot_id == bot.id
    ).all()
    
    # Refresh conversation to get all messages
    db.refresh(conversation, ["messages"])
    
    # Generate AI response
    try:
        ai_response = await ai_service.generate_reply(
            bot=bot,
            knowledge_items=knowledge_items,
            conversation=conversation,
            last_user_message=message_content
        )
        
        # Save bot response
        bot_message = Message(
            conversation_id=conversation.id,
            sender=MessageSender.BOT.value,
            content=ai_response
        )
        db.add(bot_message)
        db.commit()
        
        # Send response via WhatsApp
        access_token = decrypt_token(account.access_token_encrypted)
        if access_token:
            try:
                await meta_api_service.send_text_message(
                    access_token=access_token,
                    phone_number_id=account.phone_number_id,
                    to=from_number,
                    text=ai_response
                )
                logger.info(f"Response sent to {from_number}")
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message: {e}")
        else:
            logger.error("No access token available to send response")
    
    except Exception as e:
        logger.error(f"Error generating AI response: {e}", exc_info=True)

