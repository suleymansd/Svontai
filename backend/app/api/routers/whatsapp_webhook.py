"""
WhatsApp Webhook endpoint for receiving messages and events from Meta.

This module handles all incoming WhatsApp webhook events. When n8n integration
is enabled (USE_N8N=true and tenant.use_n8n=true), messages are forwarded to
n8n for workflow processing. Otherwise, the legacy AI response flow is used.
"""

import json
import logging
import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Response, HTTPException, status, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.onboarding_service import OnboardingService
from app.services.meta_api import meta_api_service
from app.services.system_event_service import SystemEventService
from app.core.encryption import decrypt_token
from app.core.config import settings
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
    
    IMPORTANT: This endpoint MUST return HTTP 200 within 20 seconds.
    All processing is done in background tasks to ensure quick response.
    n8n triggers are executed asynchronously with their own DB sessions.
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
    # Process in background - pass background_tasks for nested async tasks
    background_tasks.add_task(process_webhook_event, payload, db, background_tasks)
    
    return {"status": "ok"}


async def process_webhook_event(
    payload: dict,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None
):
    """
    Process webhook event in background.
    
    Args:
        payload: The webhook payload from Meta.
        db: Database session.
        background_tasks: FastAPI background tasks for async operations.
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
                    await process_message_event(waba_id, value, db, background_tasks)
                elif field == "message_template_status_update":
                    await process_template_status_event(waba_id, value, db)
                else:
                    logger.info(f"Ignoring webhook field: {field}")
    
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}", exc_info=True)


async def process_message_event(
    waba_id: str,
    value: dict,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None
):
    """
    Process incoming message event.
    
    Args:
        waba_id: WhatsApp Business Account ID.
        value: The message value object.
        db: Database session.
        background_tasks: FastAPI background tasks for async n8n operations.
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
        correlation_id = str(uuid.uuid4())
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
            logger.info(f"Message content: {content[:100]}")
            
            # Route to handler (n8n or legacy AI)
            # Pass background_tasks for async n8n triggering
            await handle_incoming_message(
                account=account,
                from_number=from_number,
                contact_name=contact_name,
                message_content=content,
                message_type=message_type,
                message_id=message_id,
                correlation_id=correlation_id,
                db=db,
                timestamp=timestamp,
                raw_payload=value,  # Pass raw payload for n8n
                background_tasks=background_tasks
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

    if not waba_id:
        return

    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.waba_id == waba_id
    ).first()
    if not account:
        logger.warning("Template status update ignored, account not found for waba_id=%s", waba_id)
        return

    from app.models.real_estate import RealEstateTemplateRegistry

    query = db.query(RealEstateTemplateRegistry).filter(
        RealEstateTemplateRegistry.tenant_id == account.tenant_id
    )
    if message_template_id:
        query = query.filter(
            (RealEstateTemplateRegistry.meta_template_id == message_template_id)
            | (RealEstateTemplateRegistry.name == message_template_name)
        )
    elif message_template_name:
        query = query.filter(RealEstateTemplateRegistry.name == message_template_name)
    else:
        return

    rows = query.all()
    if not rows:
        logger.info("Template status update: no matching template registry rows")
        return

    normalized_event = (event or "").strip().lower()
    for row in rows:
        row.status = normalized_event or row.status
        if normalized_event in {"approved", "active"}:
            row.is_approved = True
        elif normalized_event in {"rejected", "paused", "disabled"}:
            row.is_approved = False

    db.commit()


async def handle_incoming_message(
    account: WhatsAppAccount,
    from_number: str,
    contact_name: Optional[str],
    message_content: str,
    message_type: str,
    message_id: str,
    correlation_id: Optional[str],
    db: Session,
    timestamp: Optional[str] = None,
    raw_payload: Optional[dict] = None,
    background_tasks: Optional[BackgroundTasks] = None
):
    """
    Handle incoming message and route to appropriate handler.
    
    This function routes messages to either:
    1. n8n workflow engine (if USE_N8N=true and tenant.use_n8n=true)
    2. Legacy AI response system (default)
    
    The routing is transparent - messages are always stored, and the
    appropriate handler is selected based on feature flags.
    
    IMPORTANT: n8n triggering is done via BackgroundTasks to ensure
    the webhook returns HTTP 200 quickly (Meta requires response within 20s).
    """
    correlation_id = correlation_id or str(uuid.uuid4())

    from app.models.bot import Bot
    from app.models.conversation import Conversation, ConversationSource, ConversationStatus
    from app.models.message import Message, MessageSender
    from app.models.knowledge import BotKnowledgeItem
    from app.services.ai_service import ai_service
    from app.services.n8n_client import get_n8n_client, trigger_n8n_in_background
    from app.services.real_estate_service import RealEstateService
    from app.models.automation import AutomationChannel, AutomationRunStatus
    
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
            source=ConversationSource.WHATSAPP.value,
            extra_data={
                "contact_name": contact_name,
                "phone_number": from_number
            }
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    elif contact_name and not (conversation.extra_data or {}).get("contact_name"):
        conversation.extra_data = {
            **(conversation.extra_data or {}),
            "contact_name": contact_name
        }
        db.commit()
    
    # Save incoming message (always, regardless of n8n or legacy)
    user_message = Message(
        conversation_id=conversation.id,
        sender=MessageSender.USER.value,
        content=message_content,
        external_id=message_id
    )
    db.add(user_message)
    db.commit()
    
    # Check if AI/automation is paused for this conversation
    if conversation.is_ai_paused or conversation.status == ConversationStatus.HUMAN_TAKEOVER.value:
        logger.info(
            f"AI paused for conversation {conversation.id}; "
            f"skipping auto-reply for WhatsApp message {message_id}"
        )
        return

    # ===========================================
    # REAL ESTATE PACK ROUTING (MVP)
    # ===========================================
    # Runs before n8n/legacy and only handles messages when tenant pack is enabled.
    try:
        re_result = RealEstateService(db).handle_inbound_whatsapp_message(
            tenant_id=account.tenant_id,
            bot=bot,
            conversation=conversation,
            from_number=from_number,
            contact_name=contact_name,
            text=message_content,
        )
    except Exception as exc:
        re_result = None
        logger.error("Real Estate Pack handling failed: %s", exc, exc_info=True)
        SystemEventService(db).log(
            tenant_id=str(account.tenant_id),
            source="real_estate_pack",
            level="error",
            code="RE_PACK_HANDLE_ERROR",
            message=str(exc)[:500],
            meta_json={"conversation_id": str(conversation.id), "message_id": message_id},
            correlation_id=correlation_id,
        )

    if re_result and re_result.handled:
        if re_result.response_text:
            access_token = decrypt_token(account.access_token_encrypted)
            if access_token:
                try:
                    await meta_api_service.send_text_message(
                        access_token=access_token,
                        phone_number_id=account.phone_number_id,
                        to=from_number,
                        text=re_result.response_text
                    )
                    db.add(
                        Message(
                            conversation_id=conversation.id,
                            sender=MessageSender.BOT.value,
                            content=re_result.response_text,
                        )
                    )
                    db.commit()
                except Exception as exc:
                    logger.error("Real Estate Pack response send failed: %s", exc, exc_info=True)
                    SystemEventService(db).log(
                        tenant_id=str(account.tenant_id),
                        source="real_estate_pack",
                        level="error",
                        code="RE_PACK_SEND_FAILED",
                        message=str(exc)[:500],
                        meta_json={"conversation_id": str(conversation.id), "message_id": message_id},
                        correlation_id=correlation_id,
                    )
        return
    
    # ===========================================
    # n8n WORKFLOW ROUTING (ASYNC/BACKGROUND)
    # ===========================================
    # Check if n8n should handle this message
    n8n_client = get_n8n_client(db)
    
    if n8n_client.should_use_n8n(account.tenant_id):
        logger.info(
            f"Routing message {message_id} to n8n for tenant {account.tenant_id}"
        )
        
        # Get workflow ID to validate configuration
        workflow_id = n8n_client.get_workflow_id(account.tenant_id, AutomationChannel.WHATSAPP.value)
        if not workflow_id:
            logger.warning(
                f"n8n workflow not triggered for tenant {account.tenant_id} "
                f"(no workflow configured). Falling back to legacy AI."
            )
            # Fall through to legacy handling if no workflow configured
        else:
            # Schedule n8n trigger in background with its own DB session
            # This ensures the webhook returns immediately without waiting for n8n
            if background_tasks:
                background_tasks.add_task(
                    trigger_n8n_in_background,
                    tenant_id=account.tenant_id,
                    from_number=from_number,
                    to_number=account.phone_number or "",
                    text=message_content,
                    message_id=message_id,
                    timestamp=timestamp or datetime.utcnow().isoformat(),
                    channel=AutomationChannel.WHATSAPP.value,
                    correlation_id=correlation_id,
                    contact_name=contact_name,
                    raw_payload=raw_payload,
                    extra_data={
                        "bot_id": str(bot.id),
                        "conversation_id": str(conversation.id),
                        "message_type": message_type
                    }
                )
                logger.info(f"n8n trigger scheduled in background for message {message_id}")
            else:
                # Fallback: run synchronously if no background_tasks provided
                # (shouldn't happen in normal webhook flow)
                logger.warning(
                    f"No background_tasks available, running n8n trigger synchronously "
                    f"for message {message_id}"
                )
                await trigger_n8n_in_background(
                    tenant_id=account.tenant_id,
                    from_number=from_number,
                    to_number=account.phone_number or "",
                    text=message_content,
                    message_id=message_id,
                    timestamp=timestamp or datetime.utcnow().isoformat(),
                    channel=AutomationChannel.WHATSAPP.value,
                    correlation_id=correlation_id,
                    contact_name=contact_name,
                    raw_payload=raw_payload,
                    extra_data={
                        "bot_id": str(bot.id),
                        "conversation_id": str(conversation.id),
                        "message_type": message_type
                    }
                )
            
            # When n8n is enabled, we don't generate AI response here
            # n8n workflow will call back to /api/v1/channels/whatsapp/send
            return
    
    # ===========================================
    # LEGACY AI RESPONSE FLOW
    # ===========================================
    logger.info(
        f"Using legacy AI response for message {message_id} "
        f"(n8n disabled for tenant {account.tenant_id})"
    )
    
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
                SystemEventService(db).log(
                    tenant_id=str(account.tenant_id),
                    source="whatsapp",
                    level="error",
                    code="WH_SEND_FAILED",
                    message=str(e)[:500],
                    meta_json={"message_id": message_id, "to": from_number},
                    correlation_id=correlation_id
                )
                logger.error(f"Failed to send WhatsApp message: {e}")
        else:
            SystemEventService(db).log(
                tenant_id=str(account.tenant_id),
                source="whatsapp",
                level="error",
                code="WH_NO_ACCESS_TOKEN",
                message="Missing access token for WhatsApp send",
                meta_json={"message_id": message_id, "to": from_number},
                correlation_id=correlation_id
            )
            logger.error("No access token available to send response")
    
    except Exception as e:
        SystemEventService(db).log(
            tenant_id=str(account.tenant_id),
            source="whatsapp",
            level="error",
            code="WH_AI_ERROR",
            message=str(e)[:500],
            meta_json={"message_id": message_id},
            correlation_id=correlation_id
        )
        logger.error(f"Error generating AI response: {e}", exc_info=True)
