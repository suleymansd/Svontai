"""
Knowledge base management router.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.knowledge import BotKnowledgeItem
from app.schemas.knowledge import (
    KnowledgeItemCreate,
    KnowledgeItemResponse,
    KnowledgeItemUpdate
)

router = APIRouter(prefix="/bots/{bot_id}/knowledge", tags=["Knowledge Base"])


def get_bot_for_tenant(bot_id: UUID, tenant: Tenant, db: Session) -> Bot:
    """Helper to get a bot and verify tenant ownership."""
    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        Bot.tenant_id == tenant.id
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot bulunamadı"
        )
    
    return bot


@router.get("", response_model=list[KnowledgeItemResponse])
async def list_knowledge_items(
    bot_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[BotKnowledgeItem]:
    """
    List all knowledge items for a bot.
    
    Args:
        bot_id: The bot ID.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        List of knowledge items.
    """
    get_bot_for_tenant(bot_id, current_tenant, db)
    
    items = (
        db.query(BotKnowledgeItem)
        .filter(BotKnowledgeItem.bot_id == bot_id)
        .order_by(BotKnowledgeItem.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return items


@router.post("", response_model=KnowledgeItemResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_item(
    bot_id: UUID,
    item_data: KnowledgeItemCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"]))
) -> BotKnowledgeItem:
    """
    Create a new knowledge item.
    
    Args:
        bot_id: The bot ID.
        item_data: Knowledge item data.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The created knowledge item.
    """
    get_bot_for_tenant(bot_id, current_tenant, db)
    
    item = BotKnowledgeItem(
        bot_id=bot_id,
        title=item_data.title,
        question=item_data.question,
        answer=item_data.answer
    )
    
    db.add(item)
    db.commit()
    db.refresh(item)
    
    return item


@router.put("/{item_id}", response_model=KnowledgeItemResponse)
async def update_knowledge_item(
    bot_id: UUID,
    item_id: UUID,
    item_update: KnowledgeItemUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"]))
) -> BotKnowledgeItem:
    """
    Update a knowledge item.
    
    Args:
        bot_id: The bot ID.
        item_id: The knowledge item ID.
        item_update: Fields to update.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The updated knowledge item.
    """
    get_bot_for_tenant(bot_id, current_tenant, db)
    
    item = db.query(BotKnowledgeItem).filter(
        BotKnowledgeItem.id == item_id,
        BotKnowledgeItem.bot_id == bot_id
    ).first()
    
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bilgi öğesi bulunamadı"
        )
    
    update_data = item_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(item, field, value)
    
    db.commit()
    db.refresh(item)
    
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_item(
    bot_id: UUID,
    item_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"]))
) -> None:
    """
    Delete a knowledge item.
    
    Args:
        bot_id: The bot ID.
        item_id: The knowledge item ID.
        current_tenant: The user's tenant.
        db: Database session.
    """
    get_bot_for_tenant(bot_id, current_tenant, db)
    
    item = db.query(BotKnowledgeItem).filter(
        BotKnowledgeItem.id == item_id,
        BotKnowledgeItem.bot_id == bot_id
    ).first()
    
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bilgi öğesi bulunamadı"
        )
    
    db.delete(item)
    db.commit()
