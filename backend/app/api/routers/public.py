"""
Public chat endpoints for the web widget.
No authentication required.
"""

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationSource
from app.models.message import Message, MessageSender
from app.models.knowledge import BotKnowledgeItem
from app.models.lead import Lead
from app.schemas.public import (
    ChatInitRequest,
    ChatInitResponse,
    ChatSendRequest,
    ChatSendResponse
)
from app.schemas.bot import BotPublicInfo
from app.schemas.lead import LeadPublicCreate, LeadResponse
from app.services.ai_service import ai_service

router = APIRouter(prefix="/public", tags=["Public Chat"])


def generate_external_user_id() -> str:
    """Generate a unique external user ID for anonymous users."""
    return f"web_{secrets.token_urlsafe(16)}"


@router.post("/chat/init", response_model=ChatInitResponse)
async def init_chat(
    request: ChatInitRequest,
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
        welcome_message=bot.welcome_message
    )


@router.post("/chat/send", response_model=ChatSendResponse)
async def send_chat_message(
    request: ChatSendRequest,
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
    # Get conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id
    ).first()
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
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
    
    # Get knowledge items
    knowledge_items = db.query(BotKnowledgeItem).filter(
        BotKnowledgeItem.bot_id == bot.id
    ).all()
    
    # Refresh conversation to get latest messages
    db.refresh(conversation, ["messages"])
    
    # Generate AI response
    ai_response = await ai_service.generate_reply(
        bot=bot,
        knowledge_items=knowledge_items,
        conversation=conversation,
        last_user_message=request.message
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
        message_id=bot_message.id,
        reply=ai_response
    )


@router.post("/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_public_lead(
    lead_data: LeadPublicCreate,
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

