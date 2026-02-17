"""
n8n tool callback endpoints.

These endpoints are called from n8n workflows to perform side-effectful actions
in SvontAI's system-of-record (DB) and to keep usage/audit consistent.

Auth: Authorization: Bearer <n8n_callback_jwt> (tenant-scoped).
"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.n8n_security import verify_n8n_bearer_token
from app.db.session import get_db
from app.models.call import Call
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_note import LeadNote
from app.services.audit_log_service import AuditLogService
from app.services.usage_counter_service import UsageCounterService

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


class LeadUpsertRequest(BaseModel):
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

    # Optional: link an existing call to this lead
    call_provider: str | None = Field(default=None, alias="callProvider")
    call_provider_call_id: str | None = Field(default=None, alias="callProviderCallId")

    class Config:
        populate_by_name = True


class LeadUpsertResponse(BaseModel):
    ok: bool = True
    lead_id: str = Field(..., alias="leadId")
    created: bool
    updated: bool

    class Config:
        populate_by_name = True


@router.post("/leads/upsert", response_model=LeadUpsertResponse)
async def upsert_lead(
    request: Request,
    body: LeadUpsertRequest,
    db: Session = Depends(get_db),
) -> LeadUpsertResponse:
    await _verify_tenant(request, body.tenant_id)

    tenant_uuid = UUID(body.tenant_id)
    phone_norm = _normalize_phone(body.phone)
    email_norm = (body.email or "").strip().lower() or None

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

    return LeadUpsertResponse(leadId=str(lead.id), created=created, updated=updated)


class NoteCreateRequest(BaseModel):
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

    class Config:
        populate_by_name = True


class NoteCreateResponse(BaseModel):
    ok: bool = True
    note_id: str = Field(..., alias="noteId")
    created: bool

    class Config:
        populate_by_name = True


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
    tenant_id: str = Field(..., alias="tenantId")
    message_count: int = Field(default=0, alias="messageCount")
    voice_seconds: int = Field(default=0, alias="voiceSeconds")
    workflow_runs: int = Field(default=0, alias="workflowRuns")
    tool_calls: int = Field(default=0, alias="toolCalls")
    outbound_calls: int = Field(default=0, alias="outboundCalls")
    extra: dict | None = None

    class Config:
        populate_by_name = True


class UsageIncrementResponse(BaseModel):
    ok: bool = True
    period_key: str = Field(..., alias="periodKey")
    message_count: int = Field(..., alias="messageCount")
    voice_seconds: int = Field(..., alias="voiceSeconds")
    workflow_runs: int = Field(..., alias="workflowRuns")
    tool_calls: int = Field(..., alias="toolCalls")
    outbound_calls: int = Field(..., alias="outboundCalls")

    class Config:
        populate_by_name = True


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
    tenant_id: str = Field(..., alias="tenantId")
    action: str
    resource_type: str | None = Field(default=None, alias="resourceType")
    resource_id: str | None = Field(default=None, alias="resourceId")
    payload: dict | None = None

    class Config:
        populate_by_name = True


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
