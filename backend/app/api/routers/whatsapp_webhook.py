"""
WhatsApp Webhook endpoint for receiving messages and events from Meta.

This module handles all incoming WhatsApp webhook events. When n8n integration
is enabled (USE_N8N=true and tenant.use_n8n=true), messages are forwarded to
n8n for workflow processing. Otherwise, the legacy AI response flow is used.
"""

import json
import logging
import re
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
from app.core.rate_limit import (
    openwa_webhook_rate_limiter,
    rate_limit_key,
    require_rate_limit,
    webhook_rate_limiter,
)
from app.models.whatsapp_account import WhatsAppAccount
from app.models.conversation import Conversation, ConversationSource, ConversationStatus
from app.models.message import Message, MessageSender
from app.models.bot import Bot
from app.models.knowledge import BotKnowledgeItem
from app.models.tenant import Tenant
from app.services.ai_service import ai_service
from app.services.appointment_availability_service import AppointmentAvailabilityService
from app.services.assistant_profile_service import AssistantProfileService
from app.services.assistant_media_service import AssistantMediaService
from app.services.n8n_client import get_n8n_client, trigger_n8n_in_background
from app.services.real_estate_service import RealEstateService
from app.models.automation import AutomationChannel, AutomationRunStatus
from app.services.openwa_client import OpenWAClient, OpenWAError, openwa_client
from app.services.whatsapp_gateway_service import whatsapp_gateway_service
from app.services.push_notification_service import send_tenant_push_notification


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Webhook"])


# Rate limiting state (in production, use Redis)
_webhook_requests = {}

_CONTACT_NAME_SOURCE_PRIORITY = {
    "profile": 10,
    "business": 20,
    "phonebook": 30,
}


def _clean_contact_name(value: object, phone_number: str) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())[:255]
    if not cleaned or cleaned.casefold() in {"unknown", "bilinmeyen", "null", "none"}:
        return None
    phone_digits = re.sub(r"\D", "", phone_number)
    name_digits = re.sub(r"\D", "", cleaned)
    if phone_digits and name_digits == phone_digits and not any(char.isalpha() for char in cleaned):
        return None
    return cleaned


def _contact_name_candidate(
    payload: dict,
    phone_number: str,
) -> tuple[str | None, str | None]:
    candidates = (
        (payload.get("name"), "phonebook"),
        (payload.get("verifiedName"), "business"),
        (payload.get("shortName"), "phonebook"),
        (payload.get("pushName"), "profile"),
        (payload.get("notifyName"), "profile"),
        (payload.get("senderName"), "profile"),
    )
    for value, source in candidates:
        cleaned = _clean_contact_name(value, phone_number)
        if cleaned:
            return cleaned, source
    return None, None


async def _resolve_openwa_contact_name(
    *,
    db: Session,
    tenant_id: uuid.UUID,
    session_id: str,
    sender_jid: str,
    phone_number: str,
    data: dict,
) -> tuple[str | None, str | None]:
    contact = data.get("contact") if isinstance(data.get("contact"), dict) else {}
    payload_name, payload_source = _contact_name_candidate(contact, phone_number)
    if not payload_name:
        payload_name, payload_source = _contact_name_candidate(data, phone_number)

    existing = (
        db.query(Conversation.extra_data)
        .join(Bot, Conversation.bot_id == Bot.id)
        .filter(
            Bot.tenant_id == tenant_id,
            Conversation.external_user_id == phone_number,
            Conversation.source == ConversationSource.WHATSAPP.value,
        )
        .order_by(Conversation.updated_at.desc())
        .first()
    )
    existing_data = dict(existing[0] or {}) if existing else {}
    existing_name = _clean_contact_name(existing_data.get("contact_name"), phone_number)
    existing_source = (
        str(existing_data.get("contact_name_source") or "legacy")
        if existing_name
        else None
    )

    best_name, best_source = payload_name, payload_source
    if (
        existing_name
        and _CONTACT_NAME_SOURCE_PRIORITY.get(existing_source or "", 0)
        >= _CONTACT_NAME_SOURCE_PRIORITY.get(payload_source or "", 0)
    ):
        return existing_name, existing_source

    if (
        _CONTACT_NAME_SOURCE_PRIORITY.get(best_source or "", 0)
        >= _CONTACT_NAME_SOURCE_PRIORITY["phonebook"]
    ):
        return best_name, best_source

    try:
        remote_contact = await openwa_client.get_contact(session_id, sender_jid)
    except OpenWAError as exc:
        logger.info(
            "openwa.contact_lookup_unavailable session_id=%s status=%s",
            session_id,
            exc.status_code,
        )
        return best_name, best_source

    remote_name, remote_source = _contact_name_candidate(remote_contact, phone_number)
    if (
        _CONTACT_NAME_SOURCE_PRIORITY.get(remote_source or "", 0)
        > _CONTACT_NAME_SOURCE_PRIORITY.get(best_source or "", 0)
    ):
        return remote_name, remote_source
    return best_name, best_source


@router.post("/openwa/webhook")
async def openwa_webhook_events(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Receive HMAC-signed OpenWA session and message events."""
    require_rate_limit(
        openwa_webhook_rate_limiter,
        rate_limit_key(request, "openwa-webhook"),
        "OpenWA webhook rate limit exceeded.",
    )
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    session_id = str(payload.get("sessionId") or "")
    event = str(payload.get("event") or "")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if not session_id or not event:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OpenWA event")
    signature = request.headers.get("X-OpenWA-Signature")
    if not OpenWAClient.verify_signature(body, signature, session_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid OpenWA signature")

    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.provider == "openwa",
        WhatsAppAccount.provider_session_id == session_id,
    ).first()
    if not account:
        logger.warning("openwa.account_not_found session_id=%s", session_id)
        return {"status": "ignored"}

    service = OnboardingService(db)
    if event in {"session.authenticated", "session.disconnected", "session.status"}:
        service.sync_openwa_webhook_event(account, event, data)
    elif event == "message.received":
        background_tasks.add_task(
            process_openwa_message_event,
            str(account.tenant_id),
            session_id,
            account.display_phone_number or "",
            data,
            payload,
            db,
            background_tasks,
        )

    return {"status": "ok"}


async def process_openwa_message_event(
    tenant_id_str: str,
    session_id: str,
    display_phone_number: str,
    data: dict,
    raw_payload: dict,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None,
) -> None:
    """Normalize an OpenWA message into SmartWA's canonical inbound flow."""
    if data.get("fromMe") or data.get("isStatusBroadcast"):
        return
    if data.get("isGroup"):
        logger.info(
            "openwa.group_message_ignored session_id=%s message_id=%s",
            session_id,
            data.get("id"),
        )
        return

    sender = data.get("senderPhone") or data.get("from") or data.get("chatId")
    if data.get("isLidSender") and not data.get("senderPhone"):
        logger.warning("openwa.lid_sender_unresolved session_id=%s message_id=%s", session_id, data.get("id"))
        return
    from_number = OpenWAClient.phone_from_jid(str(sender or ""))
    if not from_number:
        return

    message_type = str(data.get("type") or "unknown").lower()
    content = str(data.get("body") or "").strip()
    if not content:
        if message_type in {"image", "video"}:
            content = f"[{message_type.capitalize()} received]"
        elif message_type in {"audio", "voice", "ptt"}:
            content = "[Audio received]"
        elif message_type == "document":
            filename = (
                (data.get("media") or {}).get("filename")
                if isinstance(data.get("media"), dict)
                else None
            )
            content = f"[Document received: {filename}]" if filename else "[Document received]"
        elif message_type == "location":
            location = data.get("location") if isinstance(data.get("location"), dict) else {}
            content = (
                f"[Location received] lat={location.get('latitude')}, lng={location.get('longitude')}"
            )
        else:
            content = f"[{message_type} received]"

    contact_name, contact_name_source = await _resolve_openwa_contact_name(
        db=db,
        tenant_id=uuid.UUID(tenant_id_str),
        session_id=session_id,
        sender_jid=str(data.get("from") or data.get("chatId") or sender or ""),
        phone_number=from_number,
        data=data,
    )
    message_id = str(data.get("id") or raw_payload.get("idempotencyKey") or uuid.uuid4())

    await handle_incoming_message(
        tenant_id_str=tenant_id_str,
        account_phone_number_id=session_id,
        account_display_phone_number=display_phone_number,
        access_token_encrypted="",
        from_number=from_number,
        contact_name=contact_name,
        contact_name_source=contact_name_source,
        message_content=content,
        message_type=message_type,
        message_id=message_id,
        correlation_id=str(uuid.uuid4()),
        db=db,
        timestamp=str(data.get("timestamp") or ""),
        raw_payload=raw_payload,
        background_tasks=None,
        provider="openwa",
    )


async def process_whatsapp_reply_in_background(
    *,
    tenant_id: uuid.UUID,
    bot_id: uuid.UUID,
    conversation_id: uuid.UUID,
    account_phone_number_id: str,
    provider: str,
    from_number: str,
    to_number: str,
    message_content: str,
    message_id: str,
    timestamp: str,
    correlation_id: str,
    contact_name: Optional[str],
    raw_payload: Optional[dict],
    use_n8n: bool,
    n8n_workflow_id: Optional[str],
) -> None:
    """Route through n8n, falling back to the tenant bot when n8n is unavailable."""
    from app.db.session import SessionLocal

    limit_db = SessionLocal()
    try:
        subscription_service = SubscriptionService(limit_db)
        if subscription_service.get_subscription(tenant_id) is None:
            subscription_service.create_subscription(tenant_id, "free")
        can_reply, limit_message = subscription_service.check_message_limit(
            tenant_id,
            current_message_already_counted=True,
        )
        if not can_reply:
            logger.warning(
                "whatsapp.reply_skipped_by_plan_limit tenant_id=%s message_id=%s reason=%s",
                tenant_id,
                message_id,
                limit_message,
            )
            limit_db.commit()
            return
    finally:
        limit_db.close()

    if use_n8n and n8n_workflow_id:
        run_status = await trigger_n8n_in_background(
            tenant_id=tenant_id,
            from_number=from_number,
            to_number=to_number,
            text=message_content,
            message_id=message_id,
            timestamp=timestamp,
            channel=AutomationChannel.WHATSAPP.value,
            correlation_id=correlation_id,
            contact_name=contact_name,
            raw_payload=raw_payload,
            extra_data={
                "bot_id": str(bot_id),
                "conversation_id": str(conversation_id),
                "tenant_id": str(tenant_id),
            },
            n8n_workflow_id=n8n_workflow_id,
        )
        if run_status and run_status not in {
            AutomationRunStatus.FAILED.value,
            AutomationRunStatus.TIMEOUT.value,
        }:
            return
        logger.warning(
            "whatsapp.n8n_fallback tenant_id=%s message_id=%s workflow_id=%s",
            tenant_id,
            message_id,
            n8n_workflow_id,
        )

    db = SessionLocal()
    try:
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.tenant_id == tenant_id,
            Bot.is_active.is_(True),
        ).first()
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.bot_id == bot_id,
        ).first()
        if bot is None or conversation is None:
            logger.warning(
                "whatsapp.direct_reply_context_missing tenant_id=%s message_id=%s",
                tenant_id,
                message_id,
            )
            return
        if conversation.is_ai_paused or conversation.status == ConversationStatus.HUMAN_TAKEOVER.value:
            return

        account_query = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant_id,
            WhatsAppAccount.provider == provider,
            WhatsAppAccount.is_active.is_(True),
        )
        if provider == "openwa":
            account_query = account_query.filter(
                WhatsAppAccount.provider_session_id == account_phone_number_id
            )
        else:
            account_query = account_query.filter(
                WhatsAppAccount.phone_number_id == account_phone_number_id
            )
        account = account_query.first()
        if account is None:
            logger.error(
                "whatsapp.direct_reply_account_missing tenant_id=%s provider=%s message_id=%s",
                tenant_id,
                provider,
                message_id,
            )
            return

        knowledge_items = db.query(BotKnowledgeItem).filter(
            BotKnowledgeItem.bot_id == bot.id
        ).all()
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant is None:
            logger.error("whatsapp.direct_reply_tenant_missing tenant_id=%s", tenant_id)
            return
        appointment_service = AppointmentAvailabilityService(db)
        assistant_profile_service = AssistantProfileService(db)
        db.refresh(conversation, ["messages"])
        reply = await ai_service.generate_reply(
            bot=bot,
            knowledge_items=knowledge_items,
            conversation=conversation,
            last_user_message=message_content,
            bot_settings=bot.settings,
            runtime_context=assistant_profile_service.build_runtime_context(tenant, bot),
        )
        appointment = None
        if assistant_profile_service.capability_enabled(bot, "appointment_management"):
            reply, appointment = appointment_service.apply_ai_action(
                tenant=tenant,
                conversation=conversation,
                reply=reply,
            )
        selected_media = None
        if assistant_profile_service.capability_enabled(bot, "media_catalog"):
            reply, selected_media = AssistantMediaService(db).extract_action(
                tenant_id=tenant.id,
                conversation=conversation,
                reply=reply,
            )
        if not reply.strip() and selected_media is None:
            logger.warning(
                "whatsapp.direct_reply_empty tenant_id=%s message_id=%s",
                tenant_id,
                message_id,
            )
            return

        send_result = {"message_id": None, "raw": None}
        if reply.strip():
            send_result = await whatsapp_gateway_service.send_text(
                account,
                to=from_number,
                text=reply,
            )
            db.add(Message(
                conversation_id=conversation.id,
                sender=MessageSender.BOT.value,
                content=reply,
                external_id=send_result.get("message_id"),
                raw_payload={
                    "provider": provider,
                    "reply_to_message_id": message_id,
                    "correlation_id": correlation_id,
                    "delivery": send_result.get("raw"),
                },
            ))
        media_message_id = None
        if selected_media is not None:
            media_service = AssistantMediaService(db)
            artifact = media_service.artifact_for(selected_media.asset)
            media_result = await whatsapp_gateway_service.send_media(
                account,
                to=from_number,
                media_type=selected_media.asset.media_type,
                content_bytes=media_service.artifacts.read_artifact_bytes(artifact),
                mime_type=selected_media.asset.mime_type,
                filename=artifact.name,
                caption=selected_media.caption,
            )
            media_message_id = media_result.get("message_id")
            db.add(Message(
                conversation_id=conversation.id,
                sender=MessageSender.BOT.value,
                content=f"[{selected_media.asset.media_type}:{selected_media.asset.title}]",
                external_id=media_message_id,
                raw_payload={
                    "provider": provider,
                    "media_asset_id": str(selected_media.asset.id),
                    "media_type": selected_media.asset.media_type,
                    "reply_to_message_id": message_id,
                    "correlation_id": correlation_id,
                },
            ))
            selected_media.asset.send_count = int(selected_media.asset.send_count or 0) + 1
            selected_media.asset.last_sent_at = utc_now_naive()
        db.commit()
        if appointment is not None:
            await send_tenant_push_notification(
                tenant_id=tenant_id,
                event_type="appointment",
                title="Yeni randevu oluşturuldu",
                body=f"{appointment.customer_name} için {appointment.subject} randevusu oluşturuldu.",
                url="/dashboard/appointments",
                tag="svontai-ai-appointment",
                extra={"appointment_id": str(appointment.id)},
            )
        SystemEventService(db).log(
            tenant_id=str(tenant_id),
            source="whatsapp",
            level="info",
            code="WHATSAPP_AI_REPLY_SENT",
            message="AI reply generated and sent through the tenant WhatsApp account",
            meta_json={
                "provider": provider,
                "conversation_id": str(conversation_id),
                "incoming_message_id": message_id,
                "outgoing_message_id": send_result.get("message_id"),
                "media_message_id": media_message_id,
                "fallback_from_n8n": bool(use_n8n),
            },
            correlation_id=correlation_id,
        )
        await send_tenant_push_notification(
            tenant_id=tenant_id,
            event_type="ai_reply",
            title="SvontAI çalışıyor",
            body="Yeni müşteri mesajı otomatik olarak yanıtlandı.",
            url="/dashboard/conversations",
            tag="svontai-ai-activity",
            extra={
                "message_id": send_result.get("message_id"),
                "conversation_id": str(conversation_id),
            },
        )
    except Exception as exc:
        db.rollback()
        logger.error(
            "whatsapp.direct_reply_failed tenant_id=%s message_id=%s error=%s",
            tenant_id,
            message_id,
            exc,
            exc_info=True,
        )
        try:
            SystemEventService(db).log(
                tenant_id=str(tenant_id),
                source="whatsapp",
                level="error",
                code="WHATSAPP_AI_REPLY_FAILED",
                message=str(exc)[:500],
                meta_json={
                    "provider": provider,
                    "conversation_id": str(conversation_id),
                    "incoming_message_id": message_id,
                },
                correlation_id=correlation_id,
            )
        except Exception:
            logger.exception("Could not persist WhatsApp AI reply failure event")
    finally:
        db.close()


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
                    contact_name_source=("profile" if contact_name else None),
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
    contact_name_source: Optional[str],
    message_content: str,
    message_type: str,
    message_id: str,
    correlation_id: Optional[str],
    db: Session,
    timestamp: Optional[str] = None,
    raw_payload: Optional[dict] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    provider: str = "meta_cloud",
) -> None:
    try:
        correlation_id = correlation_id or str(uuid.uuid4())
        tenant_uuid = uuid.UUID(tenant_id_str)

        bot_row = (
            db.query(Bot.id)
            .filter(
                Bot.tenant_id == tenant_uuid,
                Bot.assistant_type == "primary",
                Bot.is_active.is_(True),
            )
            .order_by(Bot.created_at.asc())
            .first()
        )
        if not bot_row:
            # Deployment-safe fallback for a tenant whose migration/autopilot
            # has not promoted its legacy bot yet. Migration 043 guarantees
            # the primary identity for normal production traffic.
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
        duplicate = (
            db.query(Message.id)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .join(Bot, Conversation.bot_id == Bot.id)
            .filter(
                Bot.tenant_id == tenant_uuid,
                Message.external_id == message_id,
            )
            .first()
        )
        if duplicate:
            logger.info(
                "whatsapp.duplicate_message_ignored tenant_id=%s message_id=%s provider=%s",
                tenant_id_str,
                message_id,
                provider,
            )
            return

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
            conversation_is_ai_paused = bool(conversation_row[1])
            conversation_status = conversation_row[2] or ConversationStatus.AI_ACTIVE.value
            existing_extra_data = dict(conversation_row[3] or {})
            updated_extra_data = {**existing_extra_data, "phone_number": from_number}
            existing_name = _clean_contact_name(
                existing_extra_data.get("contact_name"),
                from_number,
            )
            existing_source = str(existing_extra_data.get("contact_name_source") or "legacy")
            incoming_source = contact_name_source or "profile"
            should_update_name = bool(
                contact_name
                and (
                    not existing_name
                    or _CONTACT_NAME_SOURCE_PRIORITY.get(incoming_source, 0)
                    >= _CONTACT_NAME_SOURCE_PRIORITY.get(existing_source, 0)
                )
            )
            if should_update_name:
                updated_extra_data["contact_name"] = contact_name
                updated_extra_data["contact_name_source"] = incoming_source
            db.query(Conversation).filter(Conversation.id == conversation_id).update(
                {
                    Conversation.extra_data: updated_extra_data,
                    Conversation.updated_at: utc_now_naive(),
                },
                synchronize_session=False,
            )
            db.commit()
        else:
            conversation_id = uuid.uuid4()
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
                    "contact_name_source": contact_name_source,
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
                    "provider": provider,
                    "phone_number_id": account_phone_number_id,
                    "display_phone_number": account_display_phone_number,
                    "access_token_present": bool(access_token_encrypted),
                    "contact_name_source": contact_name_source,
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

        workflow_id = None
        if should_route_n8n:
            workflow_id = n8n_client.get_workflow_id(
                tenant_uuid,
                AutomationChannel.WHATSAPP.value,
            )
            if not workflow_id:
                logger.warning(
                    "No WhatsApp n8n workflow configured for tenant %s; using direct AI",
                    tenant_id_str,
                )
                should_route_n8n = False

        reply_kwargs = {
            "tenant_id": tenant_uuid,
            "bot_id": bot_id,
            "conversation_id": conversation_id,
            "account_phone_number_id": account_phone_number_id,
            "provider": provider,
            "from_number": from_number,
            "to_number": account_display_phone_number or account_phone_number_id,
            "message_content": message_content,
            "message_id": message_id,
            "timestamp": timestamp or utc_now_naive().isoformat(),
            "correlation_id": correlation_id,
            "contact_name": contact_name,
            "raw_payload": raw_payload,
            "use_n8n": should_route_n8n,
            "n8n_workflow_id": workflow_id,
        }
        if background_tasks:
            background_tasks.add_task(process_whatsapp_reply_in_background, **reply_kwargs)
        else:
            await process_whatsapp_reply_in_background(**reply_kwargs)
        logger.info(
            "WhatsApp reply processing scheduled message_id=%s tenant_id=%s use_n8n=%s workflow_id=%s",
            message_id,
            tenant_id_str,
            should_route_n8n,
            workflow_id,
        )

    except Exception as exc:
        logger.error(
            "Error handling incoming WhatsApp message message_id=%s tenant_id=%s error=%s",
            message_id,
            tenant_id_str,
            exc,
            exc_info=True,
        )
