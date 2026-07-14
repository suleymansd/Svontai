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
from app.core.time import utc_now_naive

from fastapi import APIRouter, Request, Response, HTTPException, status, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError

from app.db.session import get_db
from app.services.onboarding_service import OnboardingService
from app.services.meta_api import meta_api_service
from app.services.system_event_service import SystemEventService
from app.services.subscription_service import SubscriptionService
from app.services.usage_counter_service import UsageCounterService
from app.core.encryption import decrypt_token
from app.core.config import settings
from app.core.rate_limit import rate_limit_key, require_rate_limit, webhook_rate_limiter
from app.models.whatsapp_account import WhatsAppAccount
from app.models.conversation import Conversation, ConversationSource, ConversationStatus
from app.models.message import Message, MessageSender
from app.models.bot import Bot
from app.models.knowledge import BotKnowledgeItem
from app.services.ai_service import ai_service
from app.services.n8n_client import get_n8n_client, trigger_n8n_in_background
from app.services.real_estate_service import RealEstateService
from app.models.automation import AutomationChannel, AutomationRunStatus


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
    require_rate_limit(
        webhook_rate_limiter,
        rate_limit_key(request, "whatsapp-webhook"),
        "Webhook rate limit exceeded.",
    )

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature (if available)
    signature = request.headers.get("X-Hub-Signature-256")
    if signature:
        if not meta_api_service.verify_webhook_signature(body, signature):
            logger.warning("Invalid webhook signature")
            if settings.ENVIRONMENT == "prod":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature")
    elif settings.ENVIRONMENT == "prod":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing webhook signature")

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
    background_tasks: Optional[BackgroundTasks] = None,
) -> None:
    try:
        metadata = value.get("metadata", {}) or {}
        phone_number_id = metadata.get("phone_number_id")
        display_phone_number = metadata.get("display_phone_number")

        if not phone_number_id:
            logger.warning("whatsapp.message_event_missing_phone_number_id waba_id=%s", waba_id)
            return

        if not rate_limit_check(phone_number_id):
            logger.warning("Rate limit exceeded for %s", phone_number_id)
            return

        account_row = (
            db.query(
                WhatsAppAccount.tenant_id,
                WhatsAppAccount.phone_number_id,
                WhatsAppAccount.display_phone_number,
                WhatsAppAccount.access_token_encrypted,
            )
            .filter(WhatsAppAccount.phone_number_id == phone_number_id)
            .first()
        )

        if not account_row:
            logger.warning("whatsapp.account_not_found phone_number_id=%s", phone_number_id)
            return

        tenant_id_str = str(account_row[0])
        account_phone_number_id = account_row[1] or phone_number_id
        account_display_phone_number = account_row[2] or display_phone_number or ""
        access_token_encrypted = account_row[3] or ""

        contacts = value.get("contacts", []) or []
        contact_name_by_wa_id: dict[str, str] = {}
        for contact in contacts:
            wa_id = contact.get("wa_id")
            profile = contact.get("profile", {}) or {}
            profile_name = profile.get("name")
            if wa_id and profile_name:
                contact_name_by_wa_id[wa_id] = profile_name

        messages = value.get("messages", []) or []
        for message in messages:
            try:
                message_id = message.get("id") or str(uuid.uuid4())
                correlation_id = str(uuid.uuid4())
                from_number = message.get("from")
                timestamp = message.get("timestamp")
                message_type = (message.get("type") or "unknown").lower()
                contact_name = contact_name_by_wa_id.get(from_number) if from_number else None

                if not from_number:
                    logger.warning("Message skipped, missing sender: id=%s tenant_id=%s", message_id, tenant_id_str)
                    continue

                logger.info(
                    "Message received: id=%s, from=%s, type=%s, contact=%s",
                    message_id,
                    from_number,
                    message_type,
                    contact_name,
                )

                content: Optional[str] = None

                if message_type == "text":
                    content = (message.get("text", {}) or {}).get("body")
                elif message_type == "image":
                    image_obj = message.get("image", {}) or {}
                    content = image_obj.get("caption") or "[Image received]"
                elif message_type == "audio":
                    content = "[Audio received]"
                elif message_type == "video":
                    video_obj = message.get("video", {}) or {}
                    content = video_obj.get("caption") or "[Video received]"
                elif message_type == "document":
                    document_obj = message.get("document", {}) or {}
                    filename = document_obj.get("filename")
                    content = f"[Document received: {filename}]" if filename else "[Document received]"
                elif message_type == "location":
                    location_obj = message.get("location", {}) or {}
                    lat = location_obj.get("latitude")
                    lng = location_obj.get("longitude")
                    content = f"[Location received] lat={lat}, lng={lng}" if lat is not None and lng is not None else "[Location received]"
                elif message_type == "contacts":
                    contacts_payload = message.get("contacts", []) or []
                    if contacts_payload:
                        names: list[str] = []
                        for c in contacts_payload:
                            name_obj = c.get("name", {}) or {}
                            formatted_name = name_obj.get("formatted_name")
                            if formatted_name:
                                names.append(formatted_name)
                        content = f"[Contacts received] {', '.join(names)}" if names else "[Contacts received]"
                    else:
                        content = "[Contacts received]"
                elif message_type == "interactive":
                    interactive_obj = message.get("interactive", {}) or {}
                    button_reply = interactive_obj.get("button_reply", {}) or {}
                    list_reply = interactive_obj.get("list_reply", {}) or {}
                    if button_reply:
                        content = button_reply.get("title") or button_reply.get("id") or "[Interactive button reply]"
                    elif list_reply:
                        content = list_reply.get("title") or list_reply.get("id") or "[Interactive list reply]"
                    else:
                        content = "[Interactive received]"
                else:
                    content = f"[{message_type} received]"

                if not content:
                    content = f"[{message_type} received]"

                logger.info("Message content: %s", content)

                await handle_incoming_message(
                    tenant_id_str=tenant_id_str,
                    account_phone_number_id=account_phone_number_id,
                    account_display_phone_number=account_display_phone_number,
                    access_token_encrypted=access_token_encrypted,
                    from_number=from_number,
                    contact_name=contact_name,
                    message_content=content,
                    message_type=message_type,
                    message_id=message_id,
                    correlation_id=correlation_id,
                    db=db,
                    timestamp=timestamp,
                    raw_payload=value,
                    background_tasks=background_tasks,
                )
            except Exception as message_exc:
                logger.error(
                    "Error processing message item tenant_id=%s error=%s",
                    tenant_id_str,
                    message_exc,
                    exc_info=True,
                )

        statuses = value.get("statuses", []) or []
        for status_update in statuses:
            try:
                status_value = status_update.get("status")
                recipient_id = status_update.get("recipient_id")
                status_message_id = status_update.get("id")
                logger.info(
                    "Message status: id=%s, recipient=%s, status=%s",
                    status_message_id,
                    recipient_id,
                    status_value,
                )
            except Exception as status_exc:
                logger.error("Error processing message status update: %s", status_exc, exc_info=True)

    except Exception as exc:
        logger.error("Error processing webhook message event: %s", exc, exc_info=True)


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

    # No need to use primitive variables here, as `account` is only used for tenant_id in the query
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
    tenant_id_str: str,
    account_phone_number_id: str,
    account_display_phone_number: str,
    access_token_encrypted: str,
    from_number: str,
    contact_name: Optional[str],
    message_content: str,
    message_type: str,
    message_id: str,
    correlation_id: Optional[str],
    db: Session,
    timestamp: Optional[str] = None,
    raw_payload: Optional[dict] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> None:
    try:
        correlation_id = correlation_id or str(uuid.uuid4())
        tenant_uuid = uuid.UUID(tenant_id_str)

        bot_row = (
            db.query(Bot.id)
            .filter(Bot.tenant_id == tenant_uuid, Bot.is_active.is_(True))
            .order_by(Bot.created_at.asc())
            .first()
        )
        if not bot_row:
            logger.warning("whatsapp.no_active_bot tenant_id=%s message_id=%s", tenant_id_str, message_id)
            return

        bot_id = bot_row[0]
        bot_id_str = str(bot_id)

        conversation_row = (
            db.query(
                Conversation.id,
                Conversation.is_ai_paused,
                Conversation.status,
                Conversation.extra_data,
            )
            .filter(
                Conversation.bot_id == bot_id,
                Conversation.external_user_id == from_number,
                Conversation.source == ConversationSource.WHATSAPP.value,
            )
            .first()
        )

        if conversation_row:
            conversation_id = conversation_row[0]
            conversation_id_str = str(conversation_id)
            conversation_is_ai_paused = bool(conversation_row[1])
            conversation_status = conversation_row[2] or ConversationStatus.AI_ACTIVE.value
            existing_extra_data = dict(conversation_row[3] or {})
            if contact_name and not existing_extra_data.get("contact_name"):
                updated_extra_data = {**existing_extra_data, "contact_name": contact_name}
                db.query(Conversation).filter(Conversation.id == conversation_id).update(
                    {Conversation.extra_data: updated_extra_data},
                    synchronize_session=False,
                )
                db.commit()
        else:
            conversation_id = uuid.uuid4()
            conversation_id_str = str(conversation_id)
            conversation_is_ai_paused = False
            conversation_status = ConversationStatus.AI_ACTIVE.value

            new_conversation = Conversation(
                id=conversation_id,
                bot_id=bot_id,
                external_user_id=from_number,
                source=ConversationSource.WHATSAPP.value,
                status=ConversationStatus.AI_ACTIVE.value,
                is_ai_paused=False,
                extra_data={
                    "contact_name": contact_name,
                    "phone_number": from_number,
                },
            )
            db.add(new_conversation)
            db.commit()

        incoming_message = Message(
            conversation_id=conversation_id,
            sender=MessageSender.USER.value,
            content=message_content,
            external_id=message_id,
            raw_payload={
                "message_type": message_type,
                "from": from_number,
                "timestamp": timestamp,
                "meta": {
                    "phone_number_id": account_phone_number_id,
                    "display_phone_number": account_display_phone_number,
                    "access_token_present": bool(access_token_encrypted),
                },
            },
        )
        db.add(incoming_message)
        db.commit()

        try:
            SubscriptionService(db).increment_message_count(tenant_uuid)
        except Exception as meter_exc:
            logger.warning("Subscription usage increment failed tenant_id=%s error=%s", tenant_id_str, meter_exc)

        try:
            UsageCounterService(db).increment_message_count(tenant_uuid, 1)
        except Exception as meter_exc:
            logger.warning("Usage counter increment failed tenant_id=%s error=%s", tenant_id_str, meter_exc)

        try:
            from app.services.voice_automation_service import VoiceAutomationService

            VoiceAutomationService(db).evaluate_whatsapp_message(
                tenant_id=tenant_uuid,
                bot_id=bot_id,
                conversation_id=conversation_id,
                customer_phone=from_number,
                customer_name=contact_name,
                message_content=message_content,
                external_message_id=message_id,
                correlation_id=correlation_id,
            )
        except Exception as voice_exc:
            logger.warning(
                "Voice automation evaluation failed tenant_id=%s message_id=%s error=%s",
                tenant_id_str,
                message_id,
                voice_exc,
                exc_info=True,
            )

        if conversation_is_ai_paused or conversation_status == ConversationStatus.HUMAN_TAKEOVER.value:
            logger.info("Legacy AI branch skipped for message %s", message_id)
            return

        n8n_client = get_n8n_client(db)
        logger.info("Settings.USE_N8N: %s", settings.USE_N8N)
        should_route_n8n = bool(n8n_client.should_use_n8n(tenant_id_str))
        logger.info("should_use_n8n(%s): %s", tenant_id_str, should_route_n8n)

        if should_route_n8n:
            workflow_id = n8n_client.get_workflow_id(
                tenant_uuid,
                AutomationChannel.WHATSAPP.value,
            )
            if not workflow_id:
                logger.error("No WhatsApp n8n workflow configured for tenant %s", tenant_id_str)
                return
            logger.info("resolved workflow_id: %s", workflow_id)
            logger.info(
                "Routing message %s to n8n for tenant %s with workflow %s",
                message_id,
                tenant_id_str,
                workflow_id,
            )

            trigger_kwargs = {
                "tenant_id": tenant_uuid,
                "from_number": from_number,
                "to_number": account_display_phone_number or account_phone_number_id,
                "text": message_content,
                "message_id": message_id,
                "timestamp": timestamp or utc_now_naive().isoformat(),
                "channel": AutomationChannel.WHATSAPP.value,
                "correlation_id": correlation_id,
                "contact_name": contact_name,
                "raw_payload": raw_payload,
                "extra_data": {
                    "bot_id": bot_id_str,
                    "conversation_id": conversation_id_str,
                    "message_type": message_type,
                    "tenant_id": tenant_id_str,
                },
                "n8n_workflow_id": workflow_id,
            }

            if background_tasks:
                background_tasks.add_task(trigger_n8n_in_background, **trigger_kwargs)
                logger.info("n8n trigger scheduled in background for message %s", message_id)
            else:
                await trigger_n8n_in_background(**trigger_kwargs)
                logger.info("n8n trigger scheduled in background for message %s", message_id)

            return

        logger.info("resolved workflow_id: %s", None)
        logger.info("Legacy AI branch skipped for message %s", message_id)

    except Exception as exc:
        logger.error(
            "Error handling incoming WhatsApp message message_id=%s tenant_id=%s error=%s",
            message_id,
            tenant_id_str,
            exc,
            exc_info=True,
        )
