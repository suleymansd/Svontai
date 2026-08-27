"""
Bot management router.
"""

import logging
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
from app.models.message import Message, MessageSender
from app.schemas.bot import (
    AssistantCapabilityUpdate,
    AssistantProfileResponse,
    AssistantTrainingUpdate,
    AssistantSimulationRequest,
    AssistantSimulationResponse,
    AssistantTrainerApplyResponse,
    AssistantTrainerMessageRequest,
    AssistantTrainerMessageResponse,
    BotCreate,
    BotResponse,
    BotUpdate,
)
from app.services.audit_log_service import AuditLogService
from app.services.assistant_knowledge_service import AssistantKnowledgeService
from app.services.assistant_profile_service import AssistantProfileService
from app.services.assistant_trainer_service import (
    AssistantTrainerService,
    AssistantTrainerUnavailableError,
)
from app.services.system_event_service import SystemEventService
from app.services.ai_service import ai_service
from app.core.rate_limit import (
    assistant_rate_limiter,
    rate_limit_key,
    require_rate_limit,
)

router = APIRouter(prefix="/bots", tags=["Bots"])
logger = logging.getLogger(__name__)


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

    knowledge_items = AssistantKnowledgeService.list_effective(db, bot)
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


@router.post(
    "/assistant-profile/trainer/message",
    response_model=AssistantTrainerMessageResponse,
)
async def train_assistant_by_chat(
    payload: AssistantTrainerMessageRequest,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"])),
) -> AssistantTrainerMessageResponse:
    """Draft a specialist through natural-language conversation without publishing it."""
    require_rate_limit(
        assistant_rate_limiter,
        rate_limit_key(request, "assistant-trainer", current_tenant.id, current_user.id),
        "Çok fazla eğitim isteği. Lütfen kısa bir süre sonra tekrar deneyin.",
    )
    try:
        session, assistant_message = await AssistantTrainerService(db).message(
            tenant=current_tenant,
            user=current_user,
            message=payload.message,
            session_id=payload.session_id,
        )
    except AssistantTrainerUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AssistantTrainerMessageResponse(
        session_id=session.id,
        status=session.status,
        assistant_message=assistant_message,
        proposal=session.proposal_json,
        specialist_bot_id=session.specialist_bot_id,
    )


@router.post(
    "/assistant-profile/trainer/{session_id}/apply",
    response_model=AssistantTrainerApplyResponse,
)
async def apply_assistant_training_draft(
    session_id: UUID,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:install"])),
) -> AssistantTrainerApplyResponse:
    """Publish a reviewed specialist proposal once; repeated calls are idempotent."""
    require_rate_limit(
        assistant_rate_limiter,
        rate_limit_key(request, "assistant-trainer-apply", current_tenant.id, current_user.id),
        "Çok fazla etkinleştirme isteği. Lütfen kısa bir süre sonra tekrar deneyin.",
    )
    try:
        session, bot, knowledge_count = AssistantTrainerService(db).apply(
            tenant=current_tenant,
            user=current_user,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if knowledge_count:
        AuditLogService(db).log(
            action="assistant.specialist.create_by_chat",
            tenant_id=str(current_tenant.id),
            user_id=str(current_user.id),
            resource_type="bot",
            resource_id=str(bot.id),
            payload={"session_id": str(session.id), "knowledge_items_created": knowledge_count},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
        try:
            SystemEventService(db).log(
                tenant_id=str(current_tenant.id),
                source="assistant_trainer",
                level="info",
                code="assistant.specialist.activated",
                message=f"{bot.name} sohbetle oluşturuldu ve Ana Asistana bağlandı.",
                meta_json={"bot_id": str(bot.id), "session_id": str(session.id)},
                correlation_id=request.headers.get("X-Correlation-Id"),
            )
        except Exception:
            logger.exception("assistant specialist system event could not be written")
    return AssistantTrainerApplyResponse(
        session_id=session.id,
        assistant_message=(
            f"{bot.name} oluşturuldu ve Ana Asistanınıza bağlandı. "
            "Yeni davranışı yayın öncesi simülatörde deneyebilirsiniz."
        ),
        bot=bot,
        knowledge_items_created=knowledge_count,
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
