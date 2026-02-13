"""
Conversation management router.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationResponse, ConversationWithMessages
from app.schemas.message import MessageResponse

router = APIRouter(tags=["Conversations"])


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_all_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[Conversation]:
    """
    List all conversations for the tenant's bots.
    
    Args:
        skip: Number of records to skip.
        limit: Maximum number of records to return.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        List of conversations.
    """
    conversations = db.query(Conversation).join(Bot).filter(
        Bot.tenant_id == current_tenant.id
    ).order_by(
        Conversation.updated_at.desc()
    ).offset(skip).limit(limit).all()
    
    return conversations


@router.get("/bots/{bot_id}/conversations", response_model=list[ConversationResponse])
async def list_bot_conversations(
    bot_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[Conversation]:
    """
    List conversations for a specific bot.
    
    Args:
        bot_id: The bot ID.
        skip: Number of records to skip.
        limit: Maximum number of records to return.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        List of conversations.
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
    
    conversations = db.query(Conversation).filter(
        Conversation.bot_id == bot_id
    ).order_by(
        Conversation.updated_at.desc()
    ).offset(skip).limit(limit).all()
    
    return conversations


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> Conversation:
    """
    Get a specific conversation with messages.
    
    Args:
        conversation_id: The conversation ID.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The conversation with messages.
    """
    conversation = db.query(Conversation).join(Bot).filter(
        Conversation.id == conversation_id,
        Bot.tenant_id == current_tenant.id
    ).first()
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    
    return conversation


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[Message]:
    """
    Get messages for a specific conversation.
    
    Args:
        conversation_id: The conversation ID.
        skip: Number of records to skip.
        limit: Maximum number of records to return.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        List of messages.
    """
    # Verify conversation belongs to tenant
    conversation = db.query(Conversation).join(Bot).filter(
        Conversation.id == conversation_id,
        Bot.tenant_id == current_tenant.id
    ).first()
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(
        Message.created_at.asc()
    ).offset(skip).limit(limit).all()
    
    return messages
