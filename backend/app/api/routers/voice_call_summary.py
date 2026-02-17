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

router = APIRouter(prefix="/api/v1/voice", tags=["Voice (n8n callbacks)"])


class CallSummaryUpsertRequest(BaseModel):
    tenant_id: str = Field(..., alias="tenantId")
    provider: str
    provider_call_id: str = Field(..., alias="providerCallId")
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

    call = db.query(Call).filter(
        Call.tenant_id == body.tenant_id,
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

    return CallSummaryUpsertResponse(callId=str(call.id), summaryId=str(summary.id))

