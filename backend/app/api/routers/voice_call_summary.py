"""
n8n callback endpoint to persist call summary.

n8n can compute call summary + labels + action items and store them here.
Authentication: Bearer token created by create_n8n_jwt_token (tenant-scoped).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.n8n_security import verify_n8n_bearer_token
from app.db.session import get_db
from app.models.call import Call, CallSummary
from app.models.lead_note import LeadNote
from app.services.usage_counter_service import UsageCounterService

router = APIRouter(prefix="/api/v1/voice", tags=["Voice (n8n callbacks)"])


class CallSummaryUpsertRequest(BaseModel):
    tenant_id: str = Field(..., alias="tenantId")
    provider: str
    provider_call_id: str = Field(..., alias="providerCallId")
    lead_id: str | None = Field(default=None, alias="leadId")
    create_lead_note: bool = Field(default=True, alias="createLeadNote")
    intent: str | None = None
    summary: str
    labels_json: dict = Field(default_factory=dict, alias="labelsJson")
    action_items_json: dict = Field(default_factory=dict, alias="actionItemsJson")

    class Config:
        populate_by_name = True


class CallSummaryUpsertResponse(BaseModel):
    ok: bool = True
    call_id: str = Field(..., alias="callId")
    summary_id: str = Field(..., alias="summaryId")

    class Config:
        populate_by_name = True


@router.post("/calls/summary", response_model=CallSummaryUpsertResponse)
async def upsert_call_summary(
    request: Request,
    body: CallSummaryUpsertRequest,
    db: Session = Depends(get_db),
):
    auth = await verify_n8n_bearer_token(request)
    verified_tenant_id = auth.get("tenant_id")
    if verified_tenant_id and verified_tenant_id != body.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    from uuid import UUID

    try:
        tenant_uuid = UUID(body.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenantId")

    call = db.query(Call).filter(
        Call.tenant_id == tenant_uuid,
        Call.provider == body.provider,
        Call.provider_call_id == body.provider_call_id,
    ).first()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    summary = db.query(CallSummary).filter(CallSummary.call_id == call.id).first()
    if summary is None:
        summary = CallSummary(
            tenant_id=call.tenant_id,
            call_id=call.id,
            intent=body.intent,
            summary=body.summary or "",
            labels_json=body.labels_json or {},
            action_items_json=body.action_items_json or {},
        )
        db.add(summary)
    else:
        summary.intent = body.intent
        summary.summary = body.summary or summary.summary
        summary.labels_json = body.labels_json or summary.labels_json
        summary.action_items_json = body.action_items_json or summary.action_items_json

    db.commit()
    db.refresh(summary)

    # Optional: link call -> lead (tenant-scoped; validate UUID format best-effort)
    if body.lead_id:
        try:
            lead_uuid = UUID(body.lead_id)
            if call.lead_id != lead_uuid:
                call.lead_id = lead_uuid
                db.commit()
        except Exception:
            pass

    # Optional: persist as LeadNote (upsert by call_id + note_type)
    if body.create_lead_note:
        existing_note = db.query(LeadNote).filter(
            LeadNote.tenant_id == call.tenant_id,
            LeadNote.call_id == call.id,
            LeadNote.note_type == "call_summary",
        ).first()
        meta = {
            "intent": body.intent,
            "labels": body.labels_json or {},
            "action_items": body.action_items_json or {},
            "provider": body.provider,
            "provider_call_id": body.provider_call_id,
        }
        if existing_note is None:
            note = LeadNote(
                tenant_id=call.tenant_id,
                lead_id=call.lead_id,
                call_id=call.id,
                source="n8n",
                note_type="call_summary",
                title="Call Summary",
                content=body.summary or "",
                meta_json=meta,
            )
            db.add(note)
        else:
            existing_note.lead_id = call.lead_id
            existing_note.content = body.summary or existing_note.content
            existing_note.meta_json = meta
            existing_note.title = existing_note.title or "Call Summary"
        db.commit()

    # Meter as a tool call (summary persistence is a billable tool effect)
    try:
        UsageCounterService(db).increment(tenant_id=tenant_uuid, tool_calls=1, extra={"last_tool": "voice_call_summary"})
    except Exception:
        pass

    return CallSummaryUpsertResponse(callId=str(call.id), summaryId=str(summary.id))
