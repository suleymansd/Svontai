"""Tenant voice automation controls."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.voice_automation import CallIntent, OutboundCallJob
from app.services.voice_automation_service import VoiceAutomationService
from app.core.rate_limit import rate_limit_key, require_rate_limit, voice_test_call_rate_limiter


router = APIRouter(prefix="/voice-automation", tags=["Voice Automation"])


class VoiceSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    enabled: bool
    provider: str
    from_number: str | None = None
    allow_appointment_booking: bool
    require_explicit_call_request: bool
    business_hours_json: dict
    allowed_triggers_json: list
    handoff_rules_json: list
    max_attempts_per_lead: int
    cooldown_minutes: int
    daily_call_limit: int
    meta_json: dict
    created_at: datetime
    updated_at: datetime


class VoiceSettingsUpdate(BaseModel):
    enabled: bool | None = None
    provider: str | None = Field(default=None, max_length=40)
    from_number: str | None = Field(default=None, max_length=60)
    allow_appointment_booking: bool | None = None
    require_explicit_call_request: bool | None = None
    business_hours_json: dict | None = None
    allowed_triggers_json: list[str] | None = None
    handoff_rules_json: list[str] | None = None
    max_attempts_per_lead: int | None = Field(default=None, ge=1, le=10)
    cooldown_minutes: int | None = Field(default=None, ge=1, le=10080)
    daily_call_limit: int | None = Field(default=None, ge=0, le=1000)
    meta_json: dict | None = None


class CallIntentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    bot_id: UUID | None = None
    conversation_id: UUID | None = None
    lead_id: UUID | None = None
    customer_phone: str
    customer_name: str | None = None
    trigger: str
    reason: str
    status: str
    confidence: int
    next_attempt_at: datetime | None = None
    processed_at: datetime | None = None
    meta_json: dict
    created_at: datetime
    updated_at: datetime


class OutboundCallJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    call_intent_id: UUID | None = None
    call_id: UUID | None = None
    provider: str
    from_number: str
    to_number: str
    status: str
    attempts: int
    max_attempts: int
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    provider_call_id: str | None = None
    created_at: datetime
    updated_at: datetime


class TestCallRequest(BaseModel):
    customer_phone: str = Field(..., min_length=6, max_length=60)
    customer_name: str | None = Field(default=None, max_length=255)
    reason: str = Field(default="Panel test araması", max_length=500)


@router.get("/settings", response_model=VoiceSettingsResponse)
async def get_voice_settings(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    return VoiceAutomationService(db).get_or_create_settings(current_tenant.id)


@router.patch("/settings", response_model=VoiceSettingsResponse)
async def update_voice_settings(
    payload: VoiceSettingsUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
):
    return VoiceAutomationService(db).update_settings(
        current_tenant.id,
        payload.model_dump(exclude_unset=True),
    )


@router.get("/intents", response_model=list[CallIntentResponse])
async def list_call_intents(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    query = db.query(CallIntent).filter(CallIntent.tenant_id == current_tenant.id)
    if status:
        query = query.filter(CallIntent.status == status)
    return query.order_by(CallIntent.created_at.desc()).limit(limit).all()


@router.get("/jobs", response_model=list[OutboundCallJobResponse])
async def list_outbound_jobs(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    query = db.query(OutboundCallJob).filter(OutboundCallJob.tenant_id == current_tenant.id)
    if status:
        query = query.filter(OutboundCallJob.status == status)
    return query.order_by(OutboundCallJob.created_at.desc()).limit(limit).all()


@router.post("/test-call", response_model=CallIntentResponse)
async def create_test_call_intent(
    payload: TestCallRequest,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
):
    require_rate_limit(
        voice_test_call_rate_limiter,
        rate_limit_key(request, "voice-test-call", current_tenant.id),
        "Çok fazla test araması isteği. Lütfen daha sonra tekrar deneyin.",
    )
    service = VoiceAutomationService(db)
    intent = CallIntent(
        tenant_id=current_tenant.id,
        customer_phone=payload.customer_phone,
        customer_name=payload.customer_name,
        trigger="manual_test",
        reason=payload.reason,
        status="pending",
        confidence=100,
        meta_json={"source": "panel_test"},
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)
    service.enqueue_intent(intent)
    db.refresh(intent)
    return intent
