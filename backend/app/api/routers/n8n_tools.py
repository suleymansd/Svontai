"""
n8n tool callback endpoints.

These endpoints are called from n8n workflows to perform side-effectful actions
in SvontAI's system-of-record (DB) and to keep usage/audit consistent.

Auth: Authorization: Bearer <n8n_callback_jwt> (tenant-scoped).
"""

from __future__ import annotations

import re
import secrets
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.n8n_security import verify_n8n_bearer_token
from app.db.session import get_db
from app.models.bot import Bot
from app.models.automation import AutomationRun
from app.models.call import Call
from app.models.call import CallTranscript
from app.models.conversation import Conversation, ConversationStatus
from app.models.knowledge import BotKnowledgeItem
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_note import LeadNote
from app.models.incident import Incident
from app.models.real_estate import RealEstateLeadListingEvent, RealEstateListing
from app.models.tenant import Tenant
from app.services.appointment_availability_service import AppointmentAvailabilityService
from app.services.assistant_profile_service import AssistantProfileService
from app.services.ai_service import ai_service
from app.services.audit_log_service import AuditLogService
from app.services.usage_counter_service import UsageCounterService
from app.services.push_notification_service import send_tenant_push_notification
from app.services.system_event_service import SystemEventService
from app.core.config import settings

router = APIRouter(prefix="/api/v1/n8n", tags=["n8n Tools"])


_NON_DIGIT_RE = re.compile(r"[^0-9+]")


def _normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    if raw.startswith("tel:"):
        raw = raw[4:]
    raw = _NON_DIGIT_RE.sub("", raw)
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    if raw and not raw.startswith("+") and raw.isdigit():
        # best-effort: keep digits (tenant may not be TR)
        return raw
    return raw or None


async def _verify_tenant(request: Request, tenant_id: str) -> None:
    auth = await verify_n8n_bearer_token(request)
    verified_tenant_id = auth.get("tenant_id")
    if verified_tenant_id and verified_tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")


def _verify_error_webhook(authorization: str | None = Header(default=None)) -> None:
    expected = settings.N8N_ERROR_WEBHOOK_SECRET.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="n8n error reporting is not configured",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


class N8NErrorReportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    execution_id: str = Field(..., alias="executionId", min_length=1, max_length=100)
    workflow_id: str | None = Field(default=None, alias="workflowId", max_length=100)
    workflow_name: str = Field(default="unknown", alias="workflowName", max_length=255)
    last_node: str | None = Field(default=None, alias="lastNode", max_length=255)
    error_message: str = Field(..., alias="errorMessage", min_length=1, max_length=2000)
    error_stack: str | None = Field(default=None, alias="errorStack", max_length=8000)
    execution_url: str | None = Field(default=None, alias="executionUrl", max_length=1000)
    mode: str | None = Field(default=None, max_length=50)


@router.post("/errors/report")
async def report_n8n_error(
    body: N8NErrorReportRequest,
    _: None = Depends(_verify_error_webhook),
    db: Session = Depends(get_db),
) -> dict[str, str | bool | None]:
    run = db.query(AutomationRun).filter(
        AutomationRun.n8n_execution_id == body.execution_id
    ).first()
    tenant_id = str(run.tenant_id) if run and run.tenant_id else None
    correlation_id = run.correlation_id if run else None

    event = SystemEventService(db).log(
        tenant_id=tenant_id,
        source="n8n",
        level="error",
        code="N8N_EXECUTION_FAILED",
        message=f"{body.workflow_name}: {body.error_message}"[:500],
        meta_json={
            "execution_id": body.execution_id,
            "workflow_id": body.workflow_id,
            "workflow_name": body.workflow_name,
            "last_node": body.last_node,
            "execution_url": body.execution_url,
            "mode": body.mode,
            "error_stack": (body.error_stack or "")[:4000] or None,
            "automation_run_id": str(run.id) if run else None,
        },
        correlation_id=correlation_id,
    )

    title = f"n8n workflow failed: {body.workflow_name}"[:255]
    incident = db.query(Incident).filter(
        Incident.tenant_id == tenant_id,
        Incident.title == title,
        Incident.status != "resolved",
    ).first()
    if incident is None:
        incident = Incident(
            tenant_id=tenant_id,
            title=title,
            severity="sev3",
            status="open",
            root_cause=f"Last node: {body.last_node or 'unknown'}; execution: {body.execution_id}",
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

    return {
        "ok": True,
        "event_id": event.id,
        "incident_id": incident.id,
        "tenant_id": tenant_id,
    }


class AIReplyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    bot_id: str = Field(..., alias="botId")
    conversation_id: str = Field(..., alias="conversationId")
    message: str


class AIReplyResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    should_reply: bool = Field(..., alias="shouldReply")
    reply_text: str = Field(default="", alias="replyText")
    handoff_required: bool = Field(default=False, alias="handoffRequired")
    appointment_created: bool = Field(default=False, alias="appointmentCreated")
    appointment_id: str | None = Field(default=None, alias="appointmentId")


class AIGenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    purpose: Literal["meeting_summary", "pdf_summary", "report_generator"]
    text: str = Field(..., min_length=1, max_length=100_000)


class AIContentItem(BaseModel):
    text: str


class AIOutputItem(BaseModel):
    content: list[AIContentItem]


class AIGenerateResponse(BaseModel):
    success: bool = True
    text: str
    content: list[AIContentItem]
    output: list[AIOutputItem]


_TOOL_AI_PROMPTS = {
    "meeting_summary": (
        "Sen profesyonel bir toplantı asistanısın. Metni Türkçe ve maddeler halinde özetle. "
        "Kararları, sorumluları ve aksiyon maddelerini ayrı başlıklarda çıkar. Bilgi uydurma."
    ),
    "pdf_summary": (
        "Sen profesyonel bir doküman özetleyicisisin. Verilen metni Türkçe, kısa ve maddeler "
        "halinde özetle. Ana fikirleri ve önemli verileri koru; bilgi uydurma."
    ),
    "report_generator": (
        "Sen profesyonel bir iş analisti ve teknik yazarsın. Verilen metinden Türkçe, kapsamlı, "
        "düzenli ve net bir rapor üret. Bulgular, değerlendirme ve öneriler başlıklarını kullan."
    ),
}


@router.post("/ai/reply", response_model=AIReplyResponse)
async def generate_ai_reply(
    request: Request,
    body: AIReplyRequest,
    db: Session = Depends(get_db),
) -> AIReplyResponse:
    """Generate a tenant-scoped bot reply for a verified n8n workflow."""
    await _verify_tenant(request, body.tenant_id)
    try:
        tenant_id = UUID(body.tenant_id)
        bot_id = UUID(body.bot_id)
        conversation_id = UUID(body.conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant, bot or conversation ID") from exc

    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        Bot.tenant_id == tenant_id,
        Bot.is_active.is_(True),
    ).first()
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.bot_id == bot_id,
    ).first()
    if bot is None or conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot or conversation not found")

    if conversation.is_ai_paused or conversation.status == ConversationStatus.HUMAN_TAKEOVER.value:
        return AIReplyResponse(shouldReply=False, handoffRequired=True)

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    appointment_service = AppointmentAvailabilityService(db)
    assistant_profile_service = AssistantProfileService(db)
    knowledge_items = db.query(BotKnowledgeItem).filter(BotKnowledgeItem.bot_id == bot_id).all()
    reply = await ai_service.generate_reply(
        bot=bot,
        knowledge_items=knowledge_items,
        conversation=conversation,
        last_user_message=body.message,
        bot_settings=bot.settings,
        runtime_context=assistant_profile_service.build_runtime_context(tenant, bot),
    )
    appointment = None
    if assistant_profile_service.capability_enabled(bot, "appointment_management"):
        reply, appointment = appointment_service.apply_ai_action(
            tenant=tenant,
            conversation=conversation,
            reply=reply,
        )
    if appointment is not None:
        await send_tenant_push_notification(
            tenant_id=tenant.id,
            event_type="appointment",
            title="Yeni randevu oluşturuldu",
            body=f"{appointment.customer_name} için {appointment.subject} randevusu oluşturuldu.",
            url="/dashboard/appointments",
            tag="svontai-ai-appointment",
            extra={"appointment_id": str(appointment.id)},
        )
    return AIReplyResponse(
        shouldReply=bool(reply.strip()),
        replyText=reply,
        appointmentCreated=appointment is not None,
        appointmentId=str(appointment.id) if appointment else None,
    )


@router.post("/ai/generate", response_model=AIGenerateResponse)
async def generate_tool_text(
    request: Request,
    body: AIGenerateRequest,
) -> AIGenerateResponse:
    """Run an allowlisted tool-generation task for a verified tenant workflow."""
    await _verify_tenant(request, body.tenant_id)
    try:
        UUID(body.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant ID") from exc

    try:
        generated = await ai_service.generate_text(
            system_prompt=_TOOL_AI_PROMPTS[body.purpose],
            user_text=body.text.strip(),
            max_tokens=1600 if body.purpose == "report_generator" else 900,
            temperature=0.25,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI generation failed") from exc

    if not generated:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI returned an empty response")

    item = AIContentItem(text=generated)
    return AIGenerateResponse(
        text=generated,
        content=[item],
        output=[AIOutputItem(content=[item])],
    )


class LeadUpsertRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    phone: str | None = None
    email: str | None = None
    name: str | None = None
    company: str | None = None
    status: str | None = None
    source: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    extra_data: dict | None = Field(default=None, alias="extraData")
    bot_id: str | None = Field(default=None, alias="botId")
    conversation_id: str | None = Field(default=None, alias="conversationId")

    # Optional: link an existing call to this lead
    call_provider: str | None = Field(default=None, alias="callProvider")
    call_provider_call_id: str | None = Field(default=None, alias="callProviderCallId")


class LeadUpsertResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    lead_id: str = Field(..., alias="leadId")
    created: bool
    updated: bool


class LeadGetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    lead_id: str | None = Field(default=None, alias="leadId")
    phone: str | None = None
    email: str | None = None


class LeadGetResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    lead_id: str = Field(..., alias="leadId")
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    status: str
    source: str
    tags: list[str]
    notes: str | None = None
    extra_data: dict = Field(default_factory=dict, alias="extraData")


@router.post("/leads/get", response_model=LeadGetResponse)
async def get_lead(
    request: Request,
    body: LeadGetRequest,
    db: Session = Depends(get_db),
) -> LeadGetResponse:
    await _verify_tenant(request, body.tenant_id)
    tenant_uuid = UUID(body.tenant_id)

    lead: Lead | None = None
    if body.lead_id:
        try:
            lead_uuid = UUID(body.lead_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid leadId")
        lead = db.query(Lead).filter(Lead.id == lead_uuid, Lead.tenant_id == tenant_uuid, Lead.is_deleted == False).first()
    else:
        phone_norm = _normalize_phone(body.phone)
        email_norm = (body.email or "").strip().lower() or None
        if not phone_norm and not email_norm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="leadId or phone/email required")
        query = db.query(Lead).filter(Lead.tenant_id == tenant_uuid, Lead.is_deleted == False)
        if phone_norm:
            query = query.filter(Lead.phone == phone_norm)
        else:
            query = query.filter(Lead.email == email_norm)
        lead = query.first()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    UsageCounterService(db).increment(tenant_id=tenant_uuid, tool_calls=1, extra={"last_tool": "leads_get"})
    return LeadGetResponse(
        leadId=str(lead.id),
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        company=lead.company,
        status=lead.status,
        source=lead.source,
        tags=list(lead.tags or []),
        notes=lead.notes,
        extraData=dict(lead.extra_data or {}),
    )


class LeadPatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    lead_id: str | None = Field(default=None, alias="leadId")
    phone: str | None = None
    email: str | None = None

    name: str | None = None
    company: str | None = None
    status: str | None = None
    source: str | None = None

    tags_add: list[str] | None = Field(default=None, alias="tagsAdd")
    tags_remove: list[str] | None = Field(default=None, alias="tagsRemove")
    extra_data_merge: dict | None = Field(default=None, alias="extraDataMerge")
    notes_append: str | None = Field(default=None, alias="notesAppend")


class LeadPatchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    lead_id: str = Field(..., alias="leadId")
    updated: bool


@router.post("/leads/patch", response_model=LeadPatchResponse)
async def patch_lead(
    request: Request,
    body: LeadPatchRequest,
    db: Session = Depends(get_db),
) -> LeadPatchResponse:
    await _verify_tenant(request, body.tenant_id)
    tenant_uuid = UUID(body.tenant_id)

    lead: Lead | None = None
    if body.lead_id:
        try:
            lead_uuid = UUID(body.lead_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid leadId")
        lead = db.query(Lead).filter(Lead.id == lead_uuid, Lead.tenant_id == tenant_uuid, Lead.is_deleted == False).first()
    else:
        phone_norm = _normalize_phone(body.phone)
        email_norm = (body.email or "").strip().lower() or None
        if not phone_norm and not email_norm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="leadId or phone/email required")
        query = db.query(Lead).filter(Lead.tenant_id == tenant_uuid, Lead.is_deleted == False)
        if phone_norm:
            query = query.filter(Lead.phone == phone_norm)
        else:
            query = query.filter(Lead.email == email_norm)
        lead = query.first()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    updated = False
    if body.name is not None and body.name != lead.name:
        lead.name = body.name
        updated = True
    if body.company is not None and body.company != lead.company:
        lead.company = body.company
        updated = True
    if body.status is not None and body.status != lead.status:
        lead.status = body.status
        updated = True
    if body.source is not None and body.source != lead.source:
        lead.source = body.source
        updated = True

    tags = list(lead.tags or [])
    if body.tags_add:
        for t in body.tags_add:
            if t not in tags:
                tags.append(t)
        updated = True
    if body.tags_remove:
        tags = [t for t in tags if t not in set(body.tags_remove)]
        updated = True
    if updated:
        lead.tags = tags

    if body.extra_data_merge is not None:
        lead.extra_data = {**(lead.extra_data or {}), **dict(body.extra_data_merge)}
        updated = True

    if body.notes_append:
        existing = (lead.notes or "").strip()
        append = body.notes_append.strip()
        lead.notes = f"{existing}\n{append}".strip() if existing else append
        updated = True

    if updated:
        db.commit()
        db.refresh(lead)

    AuditLogService(db).safe_log(
        action="n8n.leads.patch",
        tenant_id=body.tenant_id,
        user_id=None,
        resource_type="lead",
        resource_id=str(lead.id),
        payload={"updated": updated},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )

    UsageCounterService(db).increment(tenant_id=tenant_uuid, tool_calls=1, extra={"last_tool": "leads_patch"})
    return LeadPatchResponse(leadId=str(lead.id), updated=updated)


@router.post("/leads/upsert", response_model=LeadUpsertResponse)
async def upsert_lead(
    request: Request,
    body: LeadUpsertRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> LeadUpsertResponse:
    await _verify_tenant(request, body.tenant_id)

    tenant_uuid = UUID(body.tenant_id)
    phone_norm = _normalize_phone(body.phone)
    email_norm = (body.email or "").strip().lower() or None

    bot_uuid: UUID | None = None
    conversation_uuid: UUID | None = None
    try:
        bot_uuid = UUID(body.bot_id) if body.bot_id else None
        conversation_uuid = UUID(body.conversation_id) if body.conversation_id else None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bot or conversation ID") from exc

    bot: Bot | None = None
    if bot_uuid:
        bot = db.query(Bot).filter(Bot.id == bot_uuid, Bot.tenant_id == tenant_uuid).first()
        if bot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    if conversation_uuid:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_uuid).first()
        if conversation is None or (bot_uuid and conversation.bot_id != bot_uuid):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        if not bot_uuid:
            bot = db.query(Bot).filter(Bot.id == conversation.bot_id, Bot.tenant_id == tenant_uuid).first()
            if bot is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
            bot_uuid = bot.id

    if bot_uuid is None:
        bot = (
            db.query(Bot)
            .filter(
                Bot.tenant_id == tenant_uuid,
                Bot.is_active.is_(True),
            )
            .order_by(Bot.created_at.asc())
            .first()
        )
        if bot is not None:
            bot_uuid = bot.id

    if not phone_norm and not email_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="phone or email is required")

    query = db.query(Lead).filter(Lead.tenant_id == tenant_uuid, Lead.is_deleted == False)
    if phone_norm:
        query = query.filter(Lead.phone == phone_norm)
    elif email_norm:
        query = query.filter(Lead.email == email_norm)

    lead = query.first()
    created = False
    updated = False

    if lead is None:
        lead = Lead(
            tenant_id=tenant_uuid,
            bot_id=bot_uuid,
            conversation_id=conversation_uuid,
            phone=phone_norm,
            email=email_norm,
            name=(body.name or None),
            company=(body.company or None),
            status=(body.status or LeadStatus.NEW.value),
            source=(body.source or LeadSource.MANUAL.value),
            tags=list(body.tags or []),
            notes=body.notes,
            extra_data=dict(body.extra_data or {}),
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        created = True
    else:
        # Update only provided fields
        if body.name is not None and body.name != lead.name:
            lead.name = body.name
            updated = True
        if email_norm is not None and email_norm != lead.email:
            lead.email = email_norm
            updated = True
        if phone_norm is not None and phone_norm != lead.phone:
            lead.phone = phone_norm
            updated = True
        if body.company is not None and body.company != lead.company:
            lead.company = body.company
            updated = True
        if body.status is not None and body.status != lead.status:
            lead.status = body.status
            updated = True
        if body.source is not None and body.source != lead.source:
            lead.source = body.source
            updated = True
        if body.tags is not None:
            lead.tags = list(body.tags)
            updated = True
        if body.notes is not None:
            lead.notes = body.notes
            updated = True
        if body.extra_data is not None:
            lead.extra_data = dict(body.extra_data)
            updated = True
        if bot_uuid is not None and bot_uuid != lead.bot_id:
            lead.bot_id = bot_uuid
            updated = True
        if conversation_uuid is not None and conversation_uuid != lead.conversation_id:
            lead.conversation_id = conversation_uuid
            updated = True

        if updated:
            db.commit()
            db.refresh(lead)

    # Optional: link call -> lead
    if body.call_provider and body.call_provider_call_id:
        call = db.query(Call).filter(
            Call.tenant_id == tenant_uuid,
            Call.provider == body.call_provider,
            Call.provider_call_id == body.call_provider_call_id,
        ).first()
        if call and call.lead_id != lead.id:
            call.lead_id = lead.id
            db.commit()

    AuditLogService(db).safe_log(
        action="n8n.leads.upsert",
        tenant_id=body.tenant_id,
        user_id=None,
        resource_type="lead",
        resource_id=str(lead.id),
        payload={"created": created, "updated": updated, "phone": bool(phone_norm), "email": bool(email_norm)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )

    UsageCounterService(db).increment(
        tenant_id=tenant_uuid,
        tool_calls=1,
        extra={"last_tool": "leads_upsert"},
    )

    if created:
        background_tasks.add_task(
            send_tenant_push_notification,
            tenant_id=tenant_uuid,
            event_type="new_lead",
            title="Yeni müşteri oluştu",
            body=f"SvontAI {lead.name or lead.phone or 'yeni bir müşteri'} için kayıt oluşturdu.",
            url="/dashboard/leads",
            tag="svontai-new-lead",
            extra={"lead_id": str(lead.id)},
        )

    return LeadUpsertResponse(leadId=str(lead.id), created=created, updated=updated)


class NoteCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    lead_id: str | None = Field(default=None, alias="leadId")
    call_id: str | None = Field(default=None, alias="callId")
    conversation_id: str | None = Field(default=None, alias="conversationId")

    # Alternative call reference
    call_provider: str | None = Field(default=None, alias="callProvider")
    call_provider_call_id: str | None = Field(default=None, alias="callProviderCallId")

    title: str | None = None
    content: str
    note_type: str = Field(default="manual", alias="noteType")
    source: str = "n8n"
    meta_json: dict | None = Field(default=None, alias="metaJson")


class NoteCreateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    note_id: str = Field(..., alias="noteId")
    created: bool


@router.post("/notes/create", response_model=NoteCreateResponse)
async def create_note(
    request: Request,
    body: NoteCreateRequest,
    db: Session = Depends(get_db),
) -> NoteCreateResponse:
    await _verify_tenant(request, body.tenant_id)
    tenant_uuid = UUID(body.tenant_id)

    call: Call | None = None
    call_id: UUID | None = None
    if body.call_id:
        try:
            call_id = UUID(body.call_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid callId")
    elif body.call_provider and body.call_provider_call_id:
        call = db.query(Call).filter(
            Call.tenant_id == tenant_uuid,
            Call.provider == body.call_provider,
            Call.provider_call_id == body.call_provider_call_id,
        ).first()
        if call:
            call_id = call.id

    lead_id: UUID | None = None
    if body.lead_id:
        try:
            lead_id = UUID(body.lead_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid leadId")

    # If call has a lead, inherit it (unless explicit lead_id provided)
    if lead_id is None and call_id is not None:
        call = call or db.query(Call).filter(Call.id == call_id, Call.tenant_id == tenant_uuid).first()
        if call and call.lead_id:
            lead_id = call.lead_id

    if body.note_type == "call_summary" and call_id is not None:
        existing = db.query(LeadNote).filter(
            LeadNote.tenant_id == tenant_uuid,
            LeadNote.call_id == call_id,
            LeadNote.note_type == "call_summary",
        ).first()
        if existing:
            existing.title = body.title or existing.title
            existing.content = body.content
            existing.source = body.source
            existing.meta_json = dict(body.meta_json or existing.meta_json or {})
            if lead_id and existing.lead_id != lead_id:
                existing.lead_id = lead_id
            db.commit()
            db.refresh(existing)
            UsageCounterService(db).increment(tenant_id=tenant_uuid, tool_calls=1, extra={"last_tool": "notes_upsert"})
            return NoteCreateResponse(noteId=str(existing.id), created=False)

    note = LeadNote(
        tenant_id=tenant_uuid,
        lead_id=lead_id,
        call_id=call_id,
        conversation_id=UUID(body.conversation_id) if body.conversation_id else None,
        created_by=None,
        source=body.source,
        note_type=body.note_type,
        title=(body.title or ""),
        content=body.content,
        meta_json=dict(body.meta_json or {}),
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    AuditLogService(db).safe_log(
        action="n8n.notes.create",
        tenant_id=body.tenant_id,
        user_id=None,
        resource_type="lead_note",
        resource_id=str(note.id),
        payload={"note_type": body.note_type, "has_lead": bool(lead_id), "has_call": bool(call_id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )

    UsageCounterService(db).increment(
        tenant_id=tenant_uuid,
        tool_calls=1,
        extra={"last_tool": "notes_create"},
    )

    return NoteCreateResponse(noteId=str(note.id), created=True)


class UsageIncrementRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    message_count: int = Field(default=0, alias="messageCount")
    voice_seconds: int = Field(default=0, alias="voiceSeconds")
    workflow_runs: int = Field(default=0, alias="workflowRuns")
    tool_calls: int = Field(default=0, alias="toolCalls")
    outbound_calls: int = Field(default=0, alias="outboundCalls")
    extra: dict | None = None


class UsageIncrementResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    period_key: str = Field(..., alias="periodKey")
    message_count: int = Field(..., alias="messageCount")
    voice_seconds: int = Field(..., alias="voiceSeconds")
    workflow_runs: int = Field(..., alias="workflowRuns")
    tool_calls: int = Field(..., alias="toolCalls")
    outbound_calls: int = Field(..., alias="outboundCalls")


@router.post("/usage/increment", response_model=UsageIncrementResponse)
async def increment_usage(
    request: Request,
    body: UsageIncrementRequest,
    db: Session = Depends(get_db),
) -> UsageIncrementResponse:
    await _verify_tenant(request, body.tenant_id)
    tenant_uuid = UUID(body.tenant_id)

    counter = UsageCounterService(db).increment(
        tenant_id=tenant_uuid,
        message_count=body.message_count,
        voice_seconds=body.voice_seconds,
        workflow_runs=body.workflow_runs,
        tool_calls=body.tool_calls,
        outbound_calls=body.outbound_calls,
        extra=body.extra,
    )

    return UsageIncrementResponse(
        periodKey=counter.period_key,
        messageCount=counter.message_count,
        voiceSeconds=counter.voice_seconds,
        workflowRuns=counter.workflow_runs,
        toolCalls=counter.tool_calls,
        outboundCalls=counter.outbound_calls,
    )


class AuditLogRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    action: str
    resource_type: str | None = Field(default=None, alias="resourceType")
    resource_id: str | None = Field(default=None, alias="resourceId")
    payload: dict | None = None


@router.post("/audit/log")
async def append_audit_log(
    request: Request,
    body: AuditLogRequest,
    db: Session = Depends(get_db),
) -> dict:
    await _verify_tenant(request, body.tenant_id)
    tenant_uuid = UUID(body.tenant_id)

    AuditLogService(db).safe_log(
        action=body.action,
        tenant_id=body.tenant_id,
        user_id=None,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        payload=body.payload,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )

    UsageCounterService(db).increment(tenant_id=tenant_uuid, tool_calls=1, extra={"last_tool": "audit_log"})

    return {"ok": True}


class CallResolveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    provider: str
    provider_call_id: str = Field(..., alias="providerCallId")


class CallResolveResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    call_id: str = Field(..., alias="callId")
    lead_id: str | None = Field(default=None, alias="leadId")
    from_number: str = Field(..., alias="from")
    to_number: str | None = Field(default=None, alias="to")
    status: str
    duration_seconds: int = Field(..., alias="durationSeconds")


@router.post("/calls/resolve", response_model=CallResolveResponse)
async def resolve_call(
    request: Request,
    body: CallResolveRequest,
    db: Session = Depends(get_db),
) -> CallResolveResponse:
    await _verify_tenant(request, body.tenant_id)

    tenant_uuid = UUID(body.tenant_id)
    call = db.query(Call).filter(
        Call.tenant_id == tenant_uuid,
        Call.provider == body.provider,
        Call.provider_call_id == body.provider_call_id,
    ).first()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    UsageCounterService(db).increment(tenant_id=tenant_uuid, tool_calls=1, extra={"last_tool": "calls_resolve"})
    return CallResolveResponse(
        callId=str(call.id),
        leadId=str(call.lead_id) if call.lead_id else None,
        from_number=call.from_number,
        to_number=call.to_number,
        status=call.status,
        durationSeconds=int(call.duration_seconds or 0),
    )


class CallTranscriptRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    call_id: str | None = Field(default=None, alias="callId")
    provider: str | None = None
    provider_call_id: str | None = Field(default=None, alias="providerCallId")


class CallTranscriptItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    segment_index: int = Field(..., alias="segmentIndex")
    speaker: str
    text: str
    ts_iso: str | None = Field(default=None, alias="tsIso")


class CallTranscriptResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    call_id: str = Field(..., alias="callId")
    items: list[CallTranscriptItem]


@router.post("/calls/transcript", response_model=CallTranscriptResponse)
async def get_call_transcript(
    request: Request,
    body: CallTranscriptRequest,
    db: Session = Depends(get_db),
) -> CallTranscriptResponse:
    await _verify_tenant(request, body.tenant_id)
    tenant_uuid = UUID(body.tenant_id)

    call: Call | None = None
    if body.call_id:
        try:
            call_uuid = UUID(body.call_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid callId")
        call = db.query(Call).filter(Call.id == call_uuid, Call.tenant_id == tenant_uuid).first()
    elif body.provider and body.provider_call_id:
        call = db.query(Call).filter(
            Call.tenant_id == tenant_uuid,
            Call.provider == body.provider,
            Call.provider_call_id == body.provider_call_id,
        ).first()
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="callId or (provider, providerCallId) required")

    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    rows = db.query(CallTranscript).filter(
        CallTranscript.call_id == call.id,
        CallTranscript.tenant_id == tenant_uuid,
    ).order_by(CallTranscript.segment_index.asc()).all()

    UsageCounterService(db).increment(tenant_id=tenant_uuid, tool_calls=1, extra={"last_tool": "calls_transcript"})
    return CallTranscriptResponse(
        callId=str(call.id),
        items=[
            CallTranscriptItem(
                segmentIndex=int(r.segment_index or 0),
                speaker=r.speaker,
                text=r.text,
                tsIso=r.ts_iso,
            )
            for r in rows
        ],
    )


class RealEstateListingSearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    sale_rent: str | None = Field(default=None, alias="saleRent")
    property_type: str | None = Field(default=None, alias="propertyType")
    location_text: str | None = Field(default=None, alias="locationText")
    budget_max: int | None = Field(default=None, alias="budgetMax")
    budget_min: int | None = Field(default=None, alias="budgetMin")
    rooms: str | None = None
    m2_min: int | None = Field(default=None, alias="m2Min")
    limit: int = Field(default=3, ge=1, le=20)


class RealEstateListingSearchItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    sale_rent: str = Field(..., alias="saleRent")
    property_type: str = Field(..., alias="propertyType")
    location_text: str = Field(..., alias="locationText")
    price: int
    currency: str
    m2: int | None = None
    rooms: str | None = None
    url: str | None = None
    media: list = Field(default_factory=list)


class RealEstateListingSearchResponse(BaseModel):
    ok: bool = True
    count: int
    items: list[RealEstateListingSearchItem]


@router.post("/real-estate/listings/search", response_model=RealEstateListingSearchResponse)
async def real_estate_search_listings(
    request: Request,
    body: RealEstateListingSearchRequest,
    db: Session = Depends(get_db),
) -> RealEstateListingSearchResponse:
    await _verify_tenant(request, body.tenant_id)
    tenant_uuid = UUID(body.tenant_id)

    query = db.query(RealEstateListing).filter(
        RealEstateListing.tenant_id == tenant_uuid,
        RealEstateListing.is_active == True,
    )
    if body.sale_rent:
        query = query.filter(RealEstateListing.sale_rent == body.sale_rent)
    if body.property_type:
        query = query.filter(RealEstateListing.property_type.ilike(f"%{body.property_type.strip()}%"))
    if body.location_text:
        query = query.filter(RealEstateListing.location_text.ilike(f"%{body.location_text.strip()}%"))
    if body.budget_min is not None:
        query = query.filter(RealEstateListing.price >= int(body.budget_min))
    if body.budget_max is not None:
        query = query.filter(RealEstateListing.price <= int(body.budget_max))
    if body.m2_min is not None:
        query = query.filter(RealEstateListing.m2.isnot(None)).filter(RealEstateListing.m2 >= int(body.m2_min))
    if body.rooms:
        # best-effort string contains match
        query = query.filter(RealEstateListing.rooms.ilike(f"%{body.rooms.strip()}%"))

    rows = query.order_by(RealEstateListing.updated_at.desc()).limit(int(body.limit)).all()

    UsageCounterService(db).increment(tenant_id=tenant_uuid, tool_calls=1, extra={"last_tool": "re_listings_search"})

    items = [
        RealEstateListingSearchItem(
            id=str(r.id),
            title=r.title,
            saleRent=r.sale_rent,
            propertyType=r.property_type,
            locationText=r.location_text,
            price=int(r.price or 0),
            currency=r.currency or "TRY",
            m2=r.m2,
            rooms=r.rooms,
            url=r.url,
            media=list(r.media or []),
        )
        for r in rows
    ]
    return RealEstateListingSearchResponse(count=len(items), items=items)


class RealEstateListingEventRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    lead_id: str = Field(..., alias="leadId")
    listing_id: str = Field(..., alias="listingId")
    event: str
    meta_json: dict | None = Field(default=None, alias="metaJson")


@router.post("/real-estate/listing-events")
async def real_estate_listing_event(
    request: Request,
    body: RealEstateListingEventRequest,
    db: Session = Depends(get_db),
) -> dict:
    await _verify_tenant(request, body.tenant_id)
    tenant_uuid = UUID(body.tenant_id)
    try:
        lead_uuid = UUID(body.lead_id)
        listing_uuid = UUID(body.listing_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid leadId/listingId")

    row = RealEstateLeadListingEvent(
        tenant_id=tenant_uuid,
        lead_id=lead_uuid,
        listing_id=listing_uuid,
        event=body.event,
        meta_json=dict(body.meta_json or {}),
    )
    db.add(row)
    db.commit()

    UsageCounterService(db).increment(tenant_id=tenant_uuid, tool_calls=1, extra={"last_tool": "re_listing_event"})
    return {"ok": True, "id": str(row.id)}
