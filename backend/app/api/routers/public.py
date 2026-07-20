"""
Public chat endpoints for the web widget.
No authentication required.
"""

import secrets
from datetime import datetime, timedelta
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationSource, ConversationStatus
from app.models.message import Message, MessageSender
from app.models.knowledge import BotKnowledgeItem
from app.models.lead import Lead
from app.models.sales_inquiry import SalesInquiry
from app.models.tenant import Tenant
from app.schemas.public import (
    ChatInitRequest,
    ChatInitResponse,
    ChatSendRequest,
    ChatSendResponse,
    ChatMessagesResponse,
    ChatMessage
)
from app.schemas.bot import BotPublicInfo
from app.schemas.lead import LeadPublicCreate, LeadResponse
from app.services.ai_service import ai_service
from app.services.appointment_availability_service import AppointmentAvailabilityService
from app.services.email_service import EmailService
from app.services.system_event_service import SystemEventService
from app.core.config import settings
from app.core.time import utc_now_naive
from app.core.rate_limit import (
    public_chat_init_rate_limiter,
    public_chat_send_rate_limiter,
    public_lead_rate_limiter,
    public_contact_rate_limiter,
    rate_limit_key,
    require_rate_limit,
)

router = APIRouter(prefix="/public", tags=["Public Chat"])
logger = logging.getLogger(__name__)


class SalesInquiryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    company: str | None = Field(default=None, max_length=180)
    phone: str | None = Field(default=None, max_length=40)
    plan: str | None = Field(default=None, max_length=30)
    interval: str | None = Field(default=None, max_length=20)
    message: str = Field(min_length=5, max_length=3000)
    website: str | None = Field(default=None, max_length=200)


class SalesInquiryAccepted(BaseModel):
    accepted: bool
    inquiry_id: str | None = None
    duplicate: bool = False
    message: str


def generate_external_user_id() -> str:
    """Generate a unique external user ID for anonymous users."""
    return f"web_{secrets.token_urlsafe(16)}"


@router.post("/contact", response_model=SalesInquiryAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_sales_inquiry(
    payload: SalesInquiryCreate,
    http_request: Request,
    db: Session = Depends(get_db),
) -> SalesInquiryAccepted:
    require_rate_limit(
        public_contact_rate_limiter,
        rate_limit_key(http_request, "public-contact"),
        "Çok fazla iletişim talebi gönderdiniz. Lütfen daha sonra tekrar deneyin.",
    )

    # Honeypot submissions receive a normal response without entering the sales queue.
    if payload.website and payload.website.strip():
        return SalesInquiryAccepted(
            accepted=True,
            message="Talebiniz alındı. Ekibimiz sizinle iletişime geçecek.",
        )

    normalized_email = str(payload.email).strip().lower()
    cutoff = utc_now_naive() - timedelta(hours=6)
    existing = db.query(SalesInquiry).filter(
        SalesInquiry.email == normalized_email,
        SalesInquiry.status.in_(["new", "contacted"]),
        SalesInquiry.created_at >= cutoff,
    ).order_by(SalesInquiry.created_at.desc()).first()
    if existing:
        return SalesInquiryAccepted(
            accepted=True,
            inquiry_id=str(existing.id),
            duplicate=True,
            message="Açık talebiniz bulunuyor. Ekibimiz sizinle iletişime geçecek.",
        )

    inquiry = SalesInquiry(
        name=payload.name.strip(),
        email=normalized_email,
        company=(payload.company or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
        plan=(payload.plan or "").strip().lower() or None,
        interval=(payload.interval or "").strip().lower() or None,
        message=payload.message.strip(),
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    email_delivered = EmailService.send_email(
        settings.SALES_CONTACT_EMAIL,
        f"Yeni SvontAI satış talebi: {inquiry.name}",
        (
            f"Ad Soyad: {inquiry.name}\n"
            f"E-posta: {inquiry.email}\n"
            f"Telefon: {inquiry.phone or '-'}\n"
            f"İşletme / Marka: {inquiry.company or '-'}\n"
            f"Plan: {inquiry.plan or '-'}\n"
            f"Dönem: {inquiry.interval or '-'}\n\n"
            f"Mesaj:\n{inquiry.message}\n\n"
            f"Talep ID: {inquiry.id}"
        ),
    )
    inquiry.email_delivered = email_delivered
    db.commit()

    SystemEventService(db).log(
        tenant_id=None,
        source="sales",
        level="info" if email_delivered else "warn",
        code="SALES_INQUIRY_CREATED",
        message="Yeni satış ve kurulum talebi oluşturuldu.",
        meta_json={"inquiry_id": str(inquiry.id), "email_delivered": email_delivered},
    )
    return SalesInquiryAccepted(
        accepted=True,
        inquiry_id=str(inquiry.id),
        message="Talebiniz alındı. Ekibimiz sizinle iletişime geçecek.",
    )


@router.post("/chat/init", response_model=ChatInitResponse)
async def init_chat(
    request: ChatInitRequest,
    http_request: Request,
    db: Session = Depends(get_db)
) -> ChatInitResponse:
    """
    Initialize a chat session with a bot.
    
    Args:
        request: Chat initialization request with bot public key.
        db: Database session.
    
    Returns:
        Chat session information including conversation ID.
    """
    require_rate_limit(
        public_chat_init_rate_limiter,
        rate_limit_key(http_request, "public-chat-init", request.bot_public_key),
        "Çok fazla sohbet başlatma isteği. Lütfen daha sonra tekrar deneyin.",
    )

    # Find bot by public key
    bot = db.query(Bot).filter(
        Bot.public_key == request.bot_public_key,
        Bot.is_active == True
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot bulunamadı veya aktif değil"
        )
    
    # Use provided external_user_id or generate new one
    external_user_id = request.external_user_id or generate_external_user_id()
    
    # Find or create conversation
    conversation = db.query(Conversation).filter(
        Conversation.bot_id == bot.id,
        Conversation.external_user_id == external_user_id,
        Conversation.source == ConversationSource.WEB_WIDGET.value
    ).first()
    
    if conversation is None:
        conversation = Conversation(
            bot_id=bot.id,
            external_user_id=external_user_id,
            source=ConversationSource.WEB_WIDGET.value
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    return ChatInitResponse(
        conversation_id=conversation.id,
        external_user_id=external_user_id,
        bot=BotPublicInfo(
            name=bot.name,
            welcome_message=bot.welcome_message,
            primary_color=bot.primary_color,
            widget_position=bot.widget_position
        ),
        welcome_message=bot.welcome_message,
        conversation_status=conversation.status,
        is_ai_paused=conversation.is_ai_paused
    )


@router.post("/chat/send", response_model=ChatSendResponse)
async def send_chat_message(
    request: ChatSendRequest,
    http_request: Request,
    db: Session = Depends(get_db)
) -> ChatSendResponse:
    """
    Send a message and get AI response.
    
    Args:
        request: Chat message request.
        db: Database session.
    
    Returns:
        AI-generated response.
    """
    require_rate_limit(
        public_chat_send_rate_limiter,
        rate_limit_key(http_request, "public-chat-send", request.conversation_id),
        "Çok fazla mesaj isteği. Lütfen daha sonra tekrar deneyin.",
    )

    # Get conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id
    ).first()
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    
    if request.external_user_id and request.external_user_id != conversation.external_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu konuşmaya erişim izniniz yok"
        )

    if request.external_user_id is None:
        logger.warning(
            "Public chat send without external_user_id for conversation %s",
            request.conversation_id
        )

    # Get bot
    bot = db.query(Bot).filter(
        Bot.id == conversation.bot_id,
        Bot.is_active == True
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot aktif değil"
        )
    
    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        sender=MessageSender.USER.value,
        content=request.message
    )
    db.add(user_message)
    db.commit()
    
    if conversation.is_ai_paused or conversation.status == ConversationStatus.HUMAN_TAKEOVER.value:
        return ChatSendResponse(
            user_message_id=user_message.id,
            reply_message_id=None,
            reply=None,
            user_created_at=user_message.created_at,
            reply_created_at=None,
            conversation_status=conversation.status,
            is_ai_paused=conversation.is_ai_paused
        )
    
    # Get knowledge items
    knowledge_items = db.query(BotKnowledgeItem).filter(
        BotKnowledgeItem.bot_id == bot.id
    ).all()
    
    # Refresh conversation to get latest messages
    db.refresh(conversation, ["messages"])
    
    # Generate AI response
    tenant = db.query(Tenant).filter(Tenant.id == bot.tenant_id).first()
    appointment_service = AppointmentAvailabilityService(db)
    ai_response = await ai_service.generate_reply(
        bot=bot,
        knowledge_items=knowledge_items,
        conversation=conversation,
        last_user_message=request.message,
        bot_settings=bot.settings,
        runtime_context=appointment_service.build_ai_context(tenant) if tenant else None,
    )
    if tenant:
        ai_response, _ = appointment_service.apply_ai_action(
            tenant=tenant,
            conversation=conversation,
            reply=ai_response,
        )
    
    # Save bot message
    bot_message = Message(
        conversation_id=conversation.id,
        sender=MessageSender.BOT.value,
        content=ai_response
    )
    db.add(bot_message)
    db.commit()
    db.refresh(bot_message)
    
    return ChatSendResponse(
        user_message_id=user_message.id,
        reply_message_id=bot_message.id,
        reply=ai_response,
        user_created_at=user_message.created_at,
        reply_created_at=bot_message.created_at,
        conversation_status=conversation.status,
        is_ai_paused=conversation.is_ai_paused
    )


@router.get("/chat/messages", response_model=ChatMessagesResponse)
async def list_chat_messages(
    conversation_id: UUID,
    external_user_id: str,
    since: datetime | None = None,
    limit: int = 50,
    db: Session = Depends(get_db)
) -> ChatMessagesResponse:
    """
    List messages for a public chat conversation.
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.external_user_id == external_user_id,
        Conversation.source == ConversationSource.WEB_WIDGET.value
    ).first()
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    
    query = db.query(Message).filter(
        Message.conversation_id == conversation.id
    )
    
    if since is not None:
        query = query.filter(Message.created_at > since)
    
    messages = query.order_by(Message.created_at.asc()).limit(limit).all()
    
    return ChatMessagesResponse(
        messages=[
            ChatMessage(
                id=message.id,
                sender=message.sender,
                content=message.content,
                created_at=message.created_at
            )
            for message in messages
        ],
        conversation_status=conversation.status,
        is_ai_paused=conversation.is_ai_paused
    )


@router.post("/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_public_lead(
    lead_data: LeadPublicCreate,
    http_request: Request,
    db: Session = Depends(get_db)
) -> Lead:
    """
    Create a lead from the public widget.
    
    Args:
        lead_data: Lead information.
        db: Database session.
    
    Returns:
        The created lead.
    """
    require_rate_limit(
        public_lead_rate_limiter,
        rate_limit_key(http_request, "public-lead", lead_data.bot_public_key),
        "Çok fazla lead oluşturma isteği. Lütfen daha sonra tekrar deneyin.",
    )

    # Find bot by public key
    bot = db.query(Bot).filter(
        Bot.public_key == lead_data.bot_public_key,
        Bot.is_active == True
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot bulunamadı"
        )
    
    # Validate conversation if provided
    if lead_data.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == lead_data.conversation_id,
            Conversation.bot_id == bot.id
        ).first()
        
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Geçersiz konuşma ID"
            )
    
    lead = Lead(
        tenant_id=bot.tenant_id,
        bot_id=bot.id,
        conversation_id=lead_data.conversation_id,
        name=lead_data.name,
        email=lead_data.email,
        phone=lead_data.phone,
        notes=lead_data.notes
    )
    
    db.add(lead)
    db.commit()
    db.refresh(lead)
    
    return lead
