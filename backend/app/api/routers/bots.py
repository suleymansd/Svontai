"""
Bot management router.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.user import User
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.schemas.bot import BotCreate, BotResponse, BotUpdate
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/bots", tags=["Bots"])


@router.get("", response_model=list[BotResponse])
async def list_bots(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[Bot]:
    """
    List all bots for the current tenant.
    
    Args:
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        List of bots.
    """
    bots = (
        db.query(Bot)
        .filter(Bot.tenant_id == current_tenant.id)
        .order_by(Bot.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return bots


@router.post("", response_model=BotResponse, status_code=status.HTTP_201_CREATED)
async def create_bot(
    bot_data: BotCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["tools:install"]))
) -> Bot:
    """
    Create a new bot.
    
    Args:
        bot_data: Bot creation data.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The created bot.
    """
    bot = Bot(
        tenant_id=current_tenant.id,
        name=bot_data.name,
        description=bot_data.description,
        welcome_message=bot_data.welcome_message,
        language=bot_data.language,
        primary_color=bot_data.primary_color,
        widget_position=bot_data.widget_position.value
    )
    
    db.add(bot)
    db.commit()
    db.refresh(bot)

    AuditLogService(db).log(
        action="bot.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="bot",
        resource_id=str(bot.id),
        payload={"name": bot.name},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    
    return bot


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(
    bot_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> Bot:
    """
    Get a specific bot by ID.
    
    Args:
        bot_id: The bot ID.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The bot.
    """
    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        Bot.tenant_id == current_tenant.id
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot bulunamadı"
        )
    
    return bot


@router.put("/{bot_id}", response_model=BotResponse)
async def update_bot(
    bot_id: UUID,
    bot_update: BotUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["tools:install"]))
) -> Bot:
    """
    Update a bot.
    
    Args:
        bot_id: The bot ID.
        bot_update: Fields to update.
        current_tenant: The user's tenant.
        db: Database session.
    
    Returns:
        The updated bot.
    """
    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        Bot.tenant_id == current_tenant.id
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot bulunamadı"
        )
    
    update_data = bot_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "widget_position" and value is not None:
            value = value.value
        setattr(bot, field, value)
    
    db.commit()
    db.refresh(bot)

    AuditLogService(db).log(
        action="bot.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="bot",
        resource_id=str(bot.id),
        payload=bot_update.model_dump(exclude_unset=True),
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    
    return bot


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(
    bot_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["tools:install"]))
) -> None:
    """
    Delete a bot.
    
    Args:
        bot_id: The bot ID.
        current_tenant: The user's tenant.
        db: Database session.
    """
    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        Bot.tenant_id == current_tenant.id
    ).first()
    
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot bulunamadı"
        )
    
    db.delete(bot)
    db.commit()

    AuditLogService(db).log(
        action="bot.delete",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="bot",
        resource_id=str(bot.id),
        payload={"name": bot.name},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
