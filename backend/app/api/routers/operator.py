"""
Operator API router for human takeover functionality.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.user import User
from app.models.tenant import Tenant
from app.models.conversation import Conversation, ConversationStatus, ConversationSource
from app.models.message import Message
from app.models.bot import Bot
from app.models.whatsapp_account import WhatsAppAccount
from app.core.encryption import decrypt_token
from app.services.meta_api import meta_api_service
from app.services.subscription_service import SubscriptionService


router = APIRouter(prefix="/operator", tags=["operator"])


# Schemas
class TakeoverRequest(BaseModel):
    conversation_id: UUID


class SendMessageRequest(BaseModel):
    conversation_id: UUID
    content: str


class ConversationWithStatus(BaseModel):
    id: str
    external_user_id: str
    source: str
    status: str
    is_ai_paused: bool
    has_lead: bool
    lead_score: int
    summary: Optional[str]
    tags: list
    created_at: str
    updated_at: str
    last_message: Optional[str]
    message_count: int


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
        .order_by(Conversation.updated_at.desc())
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
            has_lead=conv.has_lead,
            lead_score=conv.lead_score,
            summary=conv.summary,
            tags=conv.tags or [],
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            last_message=last_message,
            message_count=message_count or 0
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
    conversation.takeover_at = datetime.utcnow()
    
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
    """
    Send a message as operator.
    
    NOTE: This is a stub for actual message sending.
    In production, this would:
    1. Send message via WhatsApp API if source is whatsapp
    2. Send via WebSocket if source is widget
    """
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
    
    # Create message record
    message = Message(
        conversation_id=conversation.id,
        sender="operator",
        content=request.content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    delivered = True
    delivery_note = None
    
    if conversation.source == ConversationSource.WHATSAPP.value:
        account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant.id,
            WhatsAppAccount.is_active == True
        ).first()
        
        access_token = decrypt_token(account.access_token_encrypted) if account else None
        
        if not account or not access_token or not account.phone_number_id:
            delivered = False
            delivery_note = "WhatsApp hesabı bağlı değil veya erişim anahtarı bulunamadı."
        else:
            try:
                await meta_api_service.send_text_message(
                    access_token=access_token,
                    phone_number_id=account.phone_number_id,
                    to=conversation.external_user_id,
                    text=request.content
                )
            except Exception as e:
                delivered = False
                delivery_note = f"WhatsApp gönderimi başarısız: {str(e)}"
    
    return {
        "success": True,
        "message_id": str(message.id),
        "sent_at": message.created_at.isoformat(),
        "delivered": delivered,
        "note": delivery_note
    }


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: UUID,
    skip: int = 0,
    limit: int = 50,
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
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).offset(skip).limit(limit).all()
    
    return [
        {
            "id": str(msg.id),
            "sender": msg.sender,
            "content": msg.content,
            "created_at": msg.created_at.isoformat()
        }
        for msg in messages
    ]
