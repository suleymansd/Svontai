"""
Operator API router for human takeover functionality.
"""

from uuid import UUID, uuid4
from datetime import datetime, timedelta
from app.core.time import utc_now_naive
from typing import Annotated, Literal, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from pydantic import BaseModel, Field, StringConstraints

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.user import User
from app.models.tenant import Tenant
from app.models.conversation import Conversation, ConversationStatus, ConversationSource
from app.models.message import Message
from app.models.bot import Bot
from app.models.whatsapp_account import WhatsAppAccount
from app.services.subscription_service import SubscriptionService
from app.services.whatsapp_gateway_service import whatsapp_gateway_service
from app.models.operator_delivery import OperatorDelivery
from app.models.onboarding import AuditLog
from app.services.operator_delivery_service import enqueue_operator_message, dispatch_operator_message, delivery_result
from app.services.reply_delivery_guard import can_reconcile_reply


router = APIRouter(prefix="/operator", tags=["operator"])
logger = logging.getLogger(__name__)


# Schemas
class TakeoverRequest(BaseModel):
    conversation_id: UUID


class SendMessageRequest(BaseModel):
    conversation_id: UUID
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    request_id: UUID = Field(default_factory=uuid4)


class DeliveryResolution(BaseModel):
    outcome: Literal["sent", "not_sent"]
    checked_whatsapp: Literal[True]
    kind: Literal["operator", "ai"] = "operator"


class ConversationWithStatus(BaseModel):
    id: str
    external_user_id: str
    source: str
    status: str
    is_ai_paused: bool
    ai_reply_enabled: bool
    has_lead: bool
    lead_score: int
    summary: Optional[str]
    tags: list
    created_at: str
    updated_at: str
    last_message: Optional[str]
    message_count: int
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    handoff_reason: list[str] = Field(default_factory=list)


# Endpoints
@router.get("/conversations")
async def list_operator_conversations(
    status_filter: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
):
    """List conversations for operator view."""
    # Check operator takeover feature
    subscription_service = SubscriptionService(db)
    if not subscription_service.check_feature(tenant.id, "operator_takeover"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operatör devralma özelliği için planınızı yükseltin"
        )
    
    # Get all bots for tenant
    bots = db.query(Bot).filter(Bot.tenant_id == tenant.id).all()
    bot_ids = [bot.id for bot in bots]
    
    # Query conversations
    query = db.query(Conversation).filter(Conversation.bot_id.in_(bot_ids))
    
    if status_filter:
        query = query.filter(Conversation.status == status_filter)
    
    last_message_subq = (
        db.query(Message.content)
        .filter(Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )
    message_count_subq = (
        db.query(func.count(Message.id))
        .filter(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )

    rows = (
        query.with_entities(
            Conversation,
            last_message_subq.label("last_message"),
            message_count_subq.label("message_count")
        )
        .order_by(
            Conversation.status.in_([ConversationStatus.WAITING.value, ConversationStatus.HUMAN_TAKEOVER.value]).desc(),
            Conversation.updated_at.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        ConversationWithStatus(
            id=str(conv.id),
            external_user_id=conv.external_user_id,
            source=conv.source,
            status=conv.status,
            is_ai_paused=conv.is_ai_paused,
            ai_reply_enabled=conv.ai_reply_enabled,
            has_lead=conv.has_lead,
            lead_score=conv.lead_score,
            summary=conv.summary,
            tags=conv.tags or [],
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            last_message=last_message,
            message_count=message_count or 0,
            customer_name=conv.customer_name,
            customer_phone=conv.customer_phone,
            handoff_reason=list((conv.extra_data or {}).get("handoff_reason") or []),
        )
        for conv, last_message, message_count in rows
    ]


@router.post("/takeover")
async def takeover_conversation(
    request: TakeoverRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    """Operator takes over a conversation (pauses AI)."""
    # Check feature
    subscription_service = SubscriptionService(db)
    if not subscription_service.check_feature(tenant.id, "operator_takeover"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operatör devralma özelliği için planınızı yükseltin"
        )
    
    # Get conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    
    # Verify conversation belongs to tenant's bot
    bot = db.query(Bot).filter(Bot.id == conversation.bot_id).first()
    if not bot or bot.tenant_id != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu konuşmaya erişim izniniz yok"
        )
    
    # Takeover
    conversation.status = ConversationStatus.HUMAN_TAKEOVER.value
    conversation.is_ai_paused = True
    conversation.operator_id = current_user.id
    conversation.takeover_at = utc_now_naive()
    
    db.commit()
    
    return {
        "success": True,
        "message": "Konuşma devralındı. AI yanıtları duraklatıldı.",
        "conversation_id": str(conversation.id)
    }


@router.post("/release")
async def release_conversation(
    request: TakeoverRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    """Release conversation back to AI."""
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    
    # Verify access
    bot = db.query(Bot).filter(Bot.id == conversation.bot_id).first()
    if not bot or bot.tenant_id != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu konuşmaya erişim izniniz yok"
        )
    
    # Release
    conversation.status = ConversationStatus.AI_ACTIVE.value
    conversation.is_ai_paused = False
    conversation.operator_id = None
    
    db.commit()
    
    return {
        "success": True,
        "message": "Konuşma AI'ya devredildi.",
        "conversation_id": str(conversation.id)
    }


@router.post("/send-message")
async def send_operator_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    """Record an operator message and attempt delivery through the tenant gateway."""
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    
    # Verify access
    bot = db.query(Bot).filter(Bot.id == conversation.bot_id).first()
    if not bot or bot.tenant_id != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu konuşmaya erişim izniniz yok"
        )
    
    message_id = enqueue_operator_message(db, tenant.id, conversation, request.content, request.request_id)
    db.commit()
    await dispatch_operator_message(message_id)
    db.expire_all()
    return delivery_result(db, message_id)


@router.get("/deliveries")
async def list_deliveries(
    conversation_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    rows = db.query(OperatorDelivery).join(Message).filter(
        OperatorDelivery.tenant_id == tenant.id, Message.conversation_id == conversation_id,
        OperatorDelivery.status.in_(["queued", "dispatching", "uncertain", "failed"]),
    ).order_by(OperatorDelivery.updated_at.desc()).limit(50).all()
    items = [{**delivery_result(db, row.message_id), "kind": "operator", "content": db.get(Message, row.message_id).content} for row in rows]
    pending_ai = db.query(Message).join(Conversation).join(Bot).filter(
        Bot.tenant_id == tenant.id, Message.conversation_id == conversation_id, Message.sender == "user",
        Message.raw_payload["reply_delivery"]["status"].as_string().in_(["dispatching", "uncertain"]),
        Message.created_at < utc_now_naive() - timedelta(minutes=5),
    ).order_by(Message.created_at.desc()).limit(50).all()
    for message in pending_ai:
        if not can_reconcile_reply(message):
            continue
        prepared = (message.raw_payload or {}).get("reply_delivery", {}).get("prepared_reply", {})
        items.append({"message_id": str(message.id), "kind": "ai", "delivery_status": "uncertain",
                      "content": prepared.get("text") or message.content,
                      "note": "AI yanitinin teslimati belirsiz. WhatsApp konusmasindan kontrol edin."})
    return items


@router.post("/deliveries/{message_id}/resolve")
async def resolve_delivery(
    message_id: UUID, body: DeliveryResolution,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"])),
):
    if body.kind == "ai":
        from app.services.reply_quota_service import lock_subscription, release_reply
        from app.services.reply_usage_service import record_delivered_reply
        lock_subscription(db, tenant.id)
        message = db.query(Message).join(Conversation).join(Bot).filter(
            Message.id == message_id, Message.sender == "user", Bot.tenant_id == tenant.id,
        ).with_for_update(of=Message).first()
        if message is None:
            raise HTTPException(status_code=404, detail="Gonderim bulunamadi.")
        payload = dict(message.raw_payload or {})
        state = payload.get("reply_delivery", {})
        if not can_reconcile_reply(message):
            raise HTTPException(status_code=409, detail="Gonderim henuz uzlastirmaya uygun degil.")
        if body.outcome == "sent" and not payload.get("reply_usage"):
            prepared = state.get("prepared_reply") or {}
            reply = Message(conversation_id=message.conversation_id, sender="bot",
                            content=prepared.get("text") or "Teslimat işletme tarafından doğrulandı.",
                            reply_to_external_id=message.external_id,
                            raw_payload={"delivery_confirmed_by_operator": str(current_user.id)})
            db.add(reply)
            record_delivered_reply(db, tenant.id, reply, source_message_id=message_id)
            payload = dict(message.raw_payload or {})
        elif body.outcome == "not_sent":
            release_reply(db, tenant.id, message_id)
            message.conversation.is_ai_paused = True
            message.conversation.status = ConversationStatus.HUMAN_TAKEOVER.value
        payload["reply_delivery"] = {**state, "status": "completed", "owner": None,
                                     "updated_at": utc_now_naive().isoformat(),
                                     "resolved_by": str(current_user.id), "resolution": body.outcome}
        message.raw_payload = payload
        db.add(AuditLog(tenant_id=tenant.id, user_id=current_user.id, action="ai.delivery_resolved",
                        resource_type="message", resource_id=str(message_id), payload_json={"outcome": body.outcome}))
        db.commit()
        return {"success": True, "delivered": body.outcome == "sent", "message_id": str(message_id)}
    row = db.query(OperatorDelivery).filter_by(message_id=message_id, tenant_id=tenant.id).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Gonderim bulunamadi.")
    if row.status != "uncertain":
        raise HTTPException(status_code=409, detail="Yalnizca belirsiz gonderimler uzlastirilabilir.")
    row.status = "sent" if body.outcome == "sent" else "failed"
    row.attempt_token = None
    row.updated_at = utc_now_naive()
    db.add(AuditLog(tenant_id=tenant.id, user_id=current_user.id, action="operator.delivery_resolved",
                    resource_type="message", resource_id=str(message_id), payload_json={"outcome": body.outcome}))
    db.commit()
    return delivery_result(db, message_id)


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    newest: bool = True,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
):
    """Get messages for a conversation."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    
    # Verify access
    bot = db.query(Bot).filter(Bot.id == conversation.bot_id).first()
    if not bot or bot.tenant_id != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu konuşmaya erişim izniniz yok"
        )
    
    query = db.query(Message).filter(
        Message.conversation_id == conversation_id
    )
    order = (Message.created_at.desc(), Message.id.desc()) if newest else (Message.created_at.asc(), Message.id.asc())
    messages = query.order_by(*order).offset(skip).limit(limit).all()
    if newest:
        messages.reverse()
    
    return [
        {
            "id": str(msg.id),
            "sender": msg.sender,
            "content": msg.content,
            "created_at": msg.created_at.isoformat()
        }
        for msg in messages
    ]
