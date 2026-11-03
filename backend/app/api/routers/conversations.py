"""
Conversation management router.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, load_only
from sqlalchemy import and_, func, or_, select

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


class ConversationAIReplyPolicyUpdate(BaseModel):
    enabled: bool


def _serialize_previews(db: Session, conversations: list[Conversation]) -> list[dict]:
    """Fetch indexed last-message projections, not entire chat histories."""
    if not conversations:
        return []
    def latest(column):
        return select(column).where(Message.conversation_id == Conversation.id).order_by(
            Message.created_at.desc(), Message.id.desc(),
        ).limit(1).correlate(Conversation).scalar_subquery()
    previews = {
        row.id: (row.content, row.sent_at)
        for row in db.query(
            Conversation.id, latest(func.substr(Message.content, 1, 500)).label("content"),
            latest(Message.created_at).label("sent_at"),
        ).filter(Conversation.id.in_([item.id for item in conversations])).all()
    }
    return [{
        **{name: getattr(item, name) for name in ConversationResponse.model_fields if name not in {"last_message", "last_message_at"}},
        "last_message": previews[item.id][0], "last_message_at": previews[item.id][1],
    } for item in conversations]


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_all_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[dict]:
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
    
    return _serialize_previews(db, conversations)


@router.get("/bots/{bot_id}/conversations", response_model=list[ConversationResponse])
async def list_bot_conversations(
    bot_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[dict]:
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
    
    return _serialize_previews(db, conversations)


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: UUID,
    before_message_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=200),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> dict:
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
    
    query = db.query(Message).options(load_only(
        Message.id, Message.conversation_id, Message.sender, Message.content, Message.created_at,
    )).filter(Message.conversation_id == conversation_id)
    if before_message_id is not None:
        cursor = db.query(Message).filter(
            Message.id == before_message_id,
            Message.conversation_id == conversation_id,
        ).first()
        if cursor is None:
            raise HTTPException(status_code=404, detail="Mesaj bulunamadı")
        query = query.filter(or_(
            Message.created_at < cursor.created_at,
            and_(Message.created_at == cursor.created_at, Message.id < cursor.id),
        ))
    rows = query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    messages = list(reversed(rows[:limit]))
    return {
        **_serialize_previews(db, [conversation])[0],
        "messages": messages,
        "has_more_messages": has_more,
        "next_message_cursor": messages[0].id if has_more else None,
    }


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
        Message.created_at.asc(), Message.id.asc()
    ).offset(skip).limit(limit).all()
    
    return messages


@router.patch("/conversations/{conversation_id}/ai-reply", response_model=ConversationResponse)
async def update_conversation_ai_reply_policy(
    conversation_id: UUID,
    body: ConversationAIReplyPolicyUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"])),
) -> dict:
    """Enable or disable all automated replies for one tenant contact."""
    conversation = db.query(Conversation).join(Bot).filter(
        Conversation.id == conversation_id,
        Bot.tenant_id == current_tenant.id,
    ).first()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı",
        )

    conversation.ai_reply_enabled = body.enabled
    tags = [tag for tag in (conversation.tags or []) if tag != "ai_reply_excluded"]
    if not body.enabled:
        tags.append("ai_reply_excluded")
    conversation.tags = tags
    db.commit()
    db.refresh(conversation)
    return _serialize_previews(db, [conversation])[0]
