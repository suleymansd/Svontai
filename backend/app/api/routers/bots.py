"""
Bot management router.
"""

from time import perf_counter
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.user import User
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.bot_settings import BotSettings
from app.models.conversation import Conversation, ConversationSource
from app.models.knowledge import BotKnowledgeItem
from app.models.message import Message, MessageSender
from app.schemas.bot import (
    AssistantCapabilityUpdate,
    AssistantProfileResponse,
    AssistantTrainingUpdate,
    AssistantSimulationRequest,
    AssistantSimulationResponse,
    BotCreate,
    BotResponse,
    BotUpdate,
)
from app.services.audit_log_service import AuditLogService
from app.services.assistant_profile_service import AssistantProfileService
from app.services.ai_service import ai_service
from app.core.rate_limit import (
    assistant_rate_limiter,
    rate_limit_key,
    require_rate_limit,
)

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
        widget_position=bot_data.widget_position.value,
        assistant_type="specialist",
        specialist_key="custom",
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


@router.get("/assistant-profile", response_model=AssistantProfileResponse)
async def get_assistant_profile(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> dict:
    """Return the tenant's single primary assistant and guided configuration."""
    return AssistantProfileService(db).get_profile(current_tenant)


@router.post("/{bot_id}/simulate", response_model=AssistantSimulationResponse)
async def simulate_assistant_reply(
    bot_id: UUID,
    payload: AssistantSimulationRequest,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> AssistantSimulationResponse:
    """Preview a reply without writing conversations or triggering business actions."""
    require_rate_limit(
        assistant_rate_limiter,
        rate_limit_key(request, "assistant-simulator", current_tenant.id, current_user.id),
        "Çok fazla simülasyon isteği. Lütfen kısa bir süre sonra tekrar deneyin.",
    )
    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        Bot.tenant_id == current_tenant.id,
    ).first()
    if bot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot bulunamadı")

    knowledge_items = db.query(BotKnowledgeItem).filter(
        BotKnowledgeItem.bot_id == bot.id,
    ).all()
    bot_settings = db.query(BotSettings).filter(BotSettings.bot_id == bot.id).first()
    conversation = Conversation(
        id=uuid4(),
        bot_id=bot.id,
        external_user_id="simulator",
        source=ConversationSource.WEB_WIDGET.value,
    )
    conversation.messages = [
        Message(
            conversation_id=conversation.id,
            sender=MessageSender.USER.value if turn.role == "customer" else MessageSender.BOT.value,
            content=turn.content,
        )
        for turn in payload.history
    ]
    started_at = perf_counter()
    reply = await ai_service.generate_reply(
        bot=bot,
        knowledge_items=knowledge_items,
        conversation=conversation,
        last_user_message=payload.message,
        bot_settings=bot_settings,
        runtime_context="""
### SIMULASYON MODU
Bu konuşma yayın öncesi güvenli önizlemedir. Dış sisteme mesaj gönderme, lead veya randevu
oluşturma ve işlem yapılmış gibi konuşma. Gerçek işlem gerektiren talepte müşteriye canlı
ortamda izleyeceğin doğal yanıtı göster, ancak işlemin bu önizlemede kaydedilmediğini belirtme.
""",
    )
    return AssistantSimulationResponse(
        reply=reply,
        history_count=len(payload.history) + 2,
        latency_ms=max(0, int((perf_counter() - started_at) * 1000)),
    )


@router.put("/assistant-profile/training", response_model=AssistantProfileResponse)
async def update_assistant_training(
    payload: AssistantTrainingUpdate,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"])),
) -> dict:
    require_rate_limit(
        assistant_rate_limiter,
        rate_limit_key(request, "assistant-training", current_tenant.id, current_user.id),
        "Çok fazla asistan güncelleme isteği. Lütfen daha sonra tekrar deneyin.",
    )
    result = AssistantProfileService(db).update_training(current_tenant, payload)
    AuditLogService(db).log(
        action="assistant.training.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="bot",
        resource_id=str(result["assistant"].id),
        payload=payload.model_dump(exclude={"business_summary"}),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return result


@router.patch("/assistant-profile/capabilities/{capability_key}", response_model=AssistantProfileResponse)
async def update_assistant_capability(
    capability_key: str,
    payload: AssistantCapabilityUpdate,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"])),
) -> dict:
    require_rate_limit(
        assistant_rate_limiter,
        rate_limit_key(request, "assistant-capability", current_tenant.id, current_user.id),
        "Çok fazla yetenek güncelleme isteği. Lütfen daha sonra tekrar deneyin.",
    )
    try:
        result = AssistantProfileService(db).update_capability(
            current_tenant,
            capability_key,
            enabled=payload.enabled,
            config=payload.config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    AuditLogService(db).log(
        action="assistant.capability.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="assistant_capability",
        resource_id=capability_key,
        payload={"enabled": payload.enabled},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return result


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

    bot_settings = db.query(BotSettings).filter(BotSettings.bot_id == bot.id).first()
    if bot_settings:
        bot_settings.extra_settings = {
            **(bot_settings.extra_settings or {}),
            "managed_by_autopilot": False,
        }
    
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

    if bot.assistant_type == "primary":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ana asistan silinemez. İsterseniz geçici olarak pasife alabilirsiniz.",
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
