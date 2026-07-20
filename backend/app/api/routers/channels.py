"""
Channel endpoints for n8n workflow callbacks.

These endpoints are called by n8n workflows to send messages
through SvontAI's channel integrations (WhatsApp, etc.).

All requests must be authenticated using either:
- HMAC signature (X-N8N-Signature header)
- Bearer token (Authorization: Bearer <token>)
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.n8n_security import verify_n8n_request_dependency, verify_n8n_bearer_token
from app.services.n8n_client import get_n8n_client
from app.services.whatsapp_gateway_service import whatsapp_gateway_service
from app.services.subscription_service import SubscriptionService
from app.services.usage_counter_service import UsageCounterService
from app.services.push_notification_service import send_tenant_push_notification
from app.models.whatsapp_account import WhatsAppAccount
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationSource
from app.models.message import Message, MessageSender
from app.models.automation import AutomationRun, AutomationRunStatus
from app.services.assistant_media_service import AssistantMediaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/channels", tags=["Channels (n8n)"])


# ===========================================
# Request/Response Models
# ===========================================

class WhatsAppSendRequest(BaseModel):
    """Request body for sending WhatsApp messages from n8n."""
    model_config = ConfigDict(populate_by_name=True)
    
    tenant_id: str = Field(..., alias="tenantId", description="Tenant UUID")
    to: str = Field(..., description="Recipient phone number (with country code)")
    text: str = Field(..., description="Message text to send")
    
    # Optional metadata for tracking
    meta: Optional[dict] = Field(default=None, description="Metadata (runId, n8nExecutionId)")
    
    # Optional: specify which bot/account to use
    bot_id: Optional[str] = Field(default=None, alias="botId")
    phone_number_id: Optional[str] = Field(default=None, alias="phoneNumberId")
    

class WhatsAppSendResponse(BaseModel):
    """Response for WhatsApp send endpoint."""
    
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    run_id: Optional[str] = None


class WhatsAppTemplateSendRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId", description="Tenant UUID")
    to: str
    template_name: str = Field(..., alias="templateName")
    language_code: str = Field(default="tr", alias="languageCode")
    components: Optional[list[dict]] = None
    meta: Optional[dict] = None
    bot_id: Optional[str] = Field(default=None, alias="botId")
    phone_number_id: Optional[str] = Field(default=None, alias="phoneNumberId")


class WhatsAppDocumentSendRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId", description="Tenant UUID")
    to: str
    link: Optional[str] = None
    media_id: Optional[str] = Field(default=None, alias="mediaId")
    filename: Optional[str] = None
    caption: Optional[str] = None
    meta: Optional[dict] = None
    bot_id: Optional[str] = Field(default=None, alias="botId")
    phone_number_id: Optional[str] = Field(default=None, alias="phoneNumberId")


class WhatsAppMediaSendRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId", description="Tenant UUID")
    to: str
    asset_id: str = Field(..., alias="assetId")
    caption: Optional[str] = Field(default=None, max_length=1024)
    meta: Optional[dict] = None
    bot_id: Optional[str] = Field(default=None, alias="botId")
    phone_number_id: Optional[str] = Field(default=None, alias="phoneNumberId")


class AutomationStatusUpdateRequest(BaseModel):
    """Request to update automation run status."""
    model_config = ConfigDict(populate_by_name=True)
    
    run_id: str = Field(..., alias="runId")
    status: str = Field(..., description="New status: success, failed")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")
    response_data: Optional[dict] = Field(default=None, alias="responseData")
    

# ===========================================
# WhatsApp Channel Endpoints
# ===========================================

@router.post("/whatsapp/send", response_model=WhatsAppSendResponse)
async def send_whatsapp_message(
    request: Request,
    body: WhatsAppSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Send a WhatsApp message via SvontAI.
    
    This endpoint is called by n8n workflows to send messages.
    Authentication is via Bearer token (included in the callback payload).
    
    Flow:
    1. Verify authentication (Bearer token from n8n)
    2. Find WhatsApp account for tenant
    3. Send message via Meta API
    4. Update automation run status (if runId provided)
    5. Store message in conversation history
    
    Returns:
        WhatsAppSendResponse with success status and message ID
    """
    # Verify authentication
    try:
        auth_result = await verify_n8n_bearer_token(request)
        verified_tenant_id = auth_result.get("tenant_id")
        
        # Verify tenant_id matches
        if verified_tenant_id != body.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant ID mismatch in token"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    
    tenant_id = body.tenant_id
    run_id = body.meta.get("runId") if body.meta else None
    n8n_execution_id = body.meta.get("n8nExecutionId") if body.meta else None
    
    logger.info(
        f"WhatsApp send request: tenant={tenant_id}, to={body.to}, "
        f"run_id={run_id}"
    )
    
    try:
        # Find WhatsApp account for tenant
        account = await _get_whatsapp_account(
            db, tenant_id, body.phone_number_id, body.bot_id
        )
        
        if not account:
            error_msg = f"No WhatsApp account found for tenant {tenant_id}"
            logger.error(error_msg)
            
            # Update run status if available
            if run_id:
                _update_run_failed(db, run_id, error_msg)
            
            return WhatsAppSendResponse(
                success=False,
                error=error_msg,
                run_id=run_id
            )
        
        # Send through the tenant-selected provider.
        try:
            result = await whatsapp_gateway_service.send_text(
                account,
                to=body.to,
                text=body.text
            )
            
            wa_message_id = result.get("message_id")
            
            logger.info(
                f"WhatsApp message sent: to={body.to}, "
                f"wa_message_id={wa_message_id}"
            )
            
            # Store message in conversation if we can find it
            await _store_bot_message(
                db, tenant_id, body.to, body.text, wa_message_id
            )

            # Billing-aware metering (outbound)
            try:
                SubscriptionService(db).increment_message_count(uuid.UUID(tenant_id))
            except Exception:
                pass
            try:
                UsageCounterService(db).increment_message_count(uuid.UUID(tenant_id), 1)
            except Exception:
                pass
            
            # Update automation run status
            if run_id:
                _update_run_success(
                    db, run_id, 
                    {"wa_message_id": wa_message_id, "n8n_execution_id": n8n_execution_id}
                )

            background_tasks.add_task(
                send_tenant_push_notification,
                tenant_id=uuid.UUID(tenant_id),
                event_type="ai_reply",
                title="SvontAI çalışıyor",
                body="Yeni müşteri mesajı otomatik olarak yanıtlandı.",
                url="/dashboard/conversations",
                tag="svontai-ai-activity",
                extra={"message_id": wa_message_id, "run_id": run_id},
            )
            
            return WhatsAppSendResponse(
                success=True,
                message_id=wa_message_id,
                run_id=run_id
            )
        
        except Exception as e:
            error_msg = f"Failed to send WhatsApp message: {e}"
            logger.error(error_msg)
            
            if run_id:
                _update_run_failed(db, run_id, error_msg)
            
            return WhatsAppSendResponse(
                success=False,
                error=error_msg,
                run_id=run_id
            )
    
    except Exception as e:
        logger.error(f"Unexpected error in WhatsApp send: {e}", exc_info=True)
        return WhatsAppSendResponse(
            success=False,
            error=str(e),
            run_id=run_id
        )


@router.post("/whatsapp/send-template", response_model=WhatsAppSendResponse)
async def send_whatsapp_template(
    request: Request,
    body: WhatsAppTemplateSendRequest,
    db: Session = Depends(get_db),
):
    try:
        auth_result = await verify_n8n_bearer_token(request)
        verified_tenant_id = auth_result.get("tenant_id")
        if verified_tenant_id != body.tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant ID mismatch in token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")

    tenant_id = body.tenant_id
    run_id = body.meta.get("runId") if body.meta else None

    account = await _get_whatsapp_account(db, tenant_id, body.phone_number_id, body.bot_id)
    if not account:
        error_msg = f"No WhatsApp account found for tenant {tenant_id}"
        if run_id:
            _update_run_failed(db, run_id, error_msg)
        return WhatsAppSendResponse(success=False, error=error_msg, run_id=run_id)

    try:
        result = await whatsapp_gateway_service.send_template(
            account,
            to=body.to,
            template_name=body.template_name,
            language_code=body.language_code,
            components=body.components,
        )
        wa_message_id = result.get("message_id")
        await _store_bot_message(db, tenant_id, body.to, f"[template:{body.template_name}]", wa_message_id)

        # Billing-aware metering (outbound)
        try:
            SubscriptionService(db).increment_message_count(uuid.UUID(tenant_id))
        except Exception:
            pass
        try:
            UsageCounterService(db).increment_message_count(uuid.UUID(tenant_id), 1)
        except Exception:
            pass

        if run_id:
            _update_run_success(db, run_id, {"wa_message_id": wa_message_id, "template": body.template_name})
        return WhatsAppSendResponse(success=True, message_id=wa_message_id, run_id=run_id)
    except Exception as e:
        error_msg = f"Failed to send WhatsApp template: {e}"
        if run_id:
            _update_run_failed(db, run_id, error_msg)
        return WhatsAppSendResponse(success=False, error=error_msg, run_id=run_id)


@router.post("/whatsapp/send-document", response_model=WhatsAppSendResponse)
async def send_whatsapp_document(
    request: Request,
    body: WhatsAppDocumentSendRequest,
    db: Session = Depends(get_db),
):
    try:
        auth_result = await verify_n8n_bearer_token(request)
        verified_tenant_id = auth_result.get("tenant_id")
        if verified_tenant_id != body.tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant ID mismatch in token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")

    tenant_id = body.tenant_id
    run_id = body.meta.get("runId") if body.meta else None

    if not body.link and not body.media_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="link or mediaId is required")

    account = await _get_whatsapp_account(db, tenant_id, body.phone_number_id, body.bot_id)
    if not account:
        error_msg = f"No WhatsApp account found for tenant {tenant_id}"
        if run_id:
            _update_run_failed(db, run_id, error_msg)
        return WhatsAppSendResponse(success=False, error=error_msg, run_id=run_id)

    try:
        result = await whatsapp_gateway_service.send_document(
            account,
            to=body.to,
            media_id=body.media_id,
            link=body.link,
            filename=body.filename,
            caption=body.caption,
        )
        wa_message_id = result.get("message_id")
        await _store_bot_message(db, tenant_id, body.to, f"[document:{body.filename or ''}]", wa_message_id)

        try:
            SubscriptionService(db).increment_message_count(uuid.UUID(tenant_id))
            UsageCounterService(db).increment_message_count(uuid.UUID(tenant_id), 1)
        except Exception:
            pass

        if run_id:
            _update_run_success(db, run_id, {"wa_message_id": wa_message_id, "document": True})
        return WhatsAppSendResponse(success=True, message_id=wa_message_id, run_id=run_id)
    except Exception as e:
        error_msg = f"Failed to send WhatsApp document: {e}"
        if run_id:
            _update_run_failed(db, run_id, error_msg)
        return WhatsAppSendResponse(success=False, error=error_msg, run_id=run_id)


@router.post("/whatsapp/send-media", response_model=WhatsAppSendResponse)
async def send_whatsapp_media(
    request: Request,
    body: WhatsAppMediaSendRequest,
    db: Session = Depends(get_db),
):
    try:
        auth_result = await verify_n8n_bearer_token(request)
        if auth_result.get("tenant_id") != body.tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant ID mismatch in token")
        tenant_id = uuid.UUID(body.tenant_id)
        asset_id = uuid.UUID(body.asset_id)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant or asset ID") from exc

    run_id = body.meta.get("runId") if body.meta else None
    service = AssistantMediaService(db)
    asset = service.get(tenant_id, asset_id)
    if asset is None or not asset.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active media asset not found")
    account = await _get_whatsapp_account(db, body.tenant_id, body.phone_number_id, body.bot_id)
    if not account:
        return WhatsAppSendResponse(success=False, error="No WhatsApp account found for tenant", run_id=run_id)

    try:
        artifact = service.artifact_for(asset)
        content = service.artifacts.read_artifact_bytes(artifact)
        result = await whatsapp_gateway_service.send_media(
            account,
            to=body.to,
            media_type=asset.media_type,
            content_bytes=content,
            mime_type=asset.mime_type,
            filename=artifact.name,
            caption=body.caption,
        )
        message_id = result.get("message_id")
        await _store_bot_message(
            db,
            body.tenant_id,
            body.to,
            f"[{asset.media_type}:{asset.title}]",
            message_id,
            raw_payload={
                "provider": result.get("provider"),
                "media_asset_id": str(asset.id),
                "media_type": asset.media_type,
            },
        )
        service.mark_sent(asset)
        try:
            SubscriptionService(db).increment_message_count(tenant_id)
            UsageCounterService(db).increment_message_count(tenant_id, 1)
        except Exception:
            pass
        if run_id:
            _update_run_success(db, run_id, {"wa_message_id": message_id, "media_asset_id": str(asset.id)})
        return WhatsAppSendResponse(success=True, message_id=message_id, run_id=run_id)
    except Exception as exc:
        logger.error("WhatsApp media send failed: %s", exc, exc_info=True)
        if run_id:
            _update_run_failed(db, run_id, str(exc))
        return WhatsAppSendResponse(success=False, error="Media send failed", run_id=run_id)

@router.post("/automation/status")
async def update_automation_status(
    request: Request,
    body: AutomationStatusUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update automation run status from n8n.
    
    Called by n8n error handlers or completion workflows to report
    the final status of a workflow execution.
    """
    # Verify authentication
    try:
        auth_result = await verify_n8n_bearer_token(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    
    run = db.query(AutomationRun).filter(
        AutomationRun.id == body.run_id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Automation run {body.run_id} not found"
        )

    if auth_result.get("tenant_id") and run.tenant_id != auth_result["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch for automation run"
        )
    
    if body.status == "success":
        run.mark_success(body.response_data)
    elif body.status == "failed":
        run.mark_failed(body.error_message or "Unknown error", body.response_data)
    else:
        run.status = body.status
    
    db.commit()
    
    logger.info(f"Automation run {body.run_id} status updated to {body.status}")
    
    return {"success": True, "run_id": body.run_id, "status": run.status}


# ===========================================
# Helper Functions
# ===========================================

async def _get_whatsapp_account(
    db: Session,
    tenant_id: str,
    phone_number_id: Optional[str] = None,
    bot_id: Optional[str] = None
) -> Optional[WhatsAppAccount]:
    """Find WhatsApp account for tenant."""
    
    query = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.tenant_id == tenant_id,
        WhatsAppAccount.is_active == True
    )
    
    if phone_number_id:
        query = query.filter(
            or_(
                WhatsAppAccount.phone_number_id == phone_number_id,
                WhatsAppAccount.provider_session_id == phone_number_id,
            )
        )
    
    return query.first()


async def _store_bot_message(
    db: Session,
    tenant_id: str,
    to_number: str,
    text: str,
    external_id: Optional[str] = None,
    raw_payload: Optional[dict] = None,
):
    """Store bot message in conversation history."""
    try:
        # Find bot for tenant
        bot = db.query(Bot).filter(
            Bot.tenant_id == tenant_id,
            Bot.is_active == True
        ).first()
        
        if not bot:
            return
        
        # Find conversation
        conversation = db.query(Conversation).filter(
            Conversation.bot_id == bot.id,
            Conversation.external_user_id == to_number,
            Conversation.source == ConversationSource.WHATSAPP.value
        ).first()
        
        if not conversation:
            return
        
        # Save bot message
        message = Message(
            conversation_id=conversation.id,
            sender=MessageSender.BOT.value,
            content=text,
            external_id=external_id,
            raw_payload=raw_payload,
        )
        db.add(message)
        db.commit()
        
        logger.debug(f"Stored bot message for conversation {conversation.id}")
    
    except Exception as e:
        logger.error(f"Failed to store bot message: {e}")


def _update_run_success(db: Session, run_id: str, response_data: dict):
    """Update automation run as successful."""
    try:
        run = db.query(AutomationRun).filter(AutomationRun.id == run_id).first()
        if run:
            run.mark_success(response_data)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update run {run_id} status: {e}")


def _update_run_failed(db: Session, run_id: str, error_message: str):
    """Update automation run as failed."""
    try:
        run = db.query(AutomationRun).filter(AutomationRun.id == run_id).first()
        if run:
            run.mark_failed(error_message)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update run {run_id} status: {e}")
