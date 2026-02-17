"""
Calls router (read-only for tenant panel).

Call creation/upserts are primarily done through signed gateway endpoints (voice_events).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.call import Call, CallTranscript, CallSummary
from app.models.tenant import Tenant
from app.schemas.call import CallResponse, CallTranscriptResponse, CallSummaryResponse

router = APIRouter(prefix="/calls", tags=["Calls"])


@router.get("", response_model=list[CallResponse])
async def list_calls(
    status_filter: str | None = Query(default=None, alias="status"),
    provider: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    query = db.query(Call).filter(Call.tenant_id == current_tenant.id)
    if status_filter:
        query = query.filter(Call.status == status_filter)
    if provider:
        query = query.filter(Call.provider == provider)
    return query.order_by(Call.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    call = db.query(Call).filter(Call.id == call_id, Call.tenant_id == current_tenant.id).first()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return call


@router.get("/{call_id}/transcript", response_model=list[CallTranscriptResponse])
async def get_call_transcript(
    call_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    call = db.query(Call).filter(Call.id == call_id, Call.tenant_id == current_tenant.id).first()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    items = db.query(CallTranscript).filter(
        CallTranscript.call_id == call_id,
        CallTranscript.tenant_id == current_tenant.id,
    ).order_by(CallTranscript.segment_index.asc()).all()
    return items


@router.get("/{call_id}/summary", response_model=CallSummaryResponse)
async def get_call_summary(
    call_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    call = db.query(Call).filter(Call.id == call_id, Call.tenant_id == current_tenant.id).first()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    summary = db.query(CallSummary).filter(
        CallSummary.call_id == call_id,
        CallSummary.tenant_id == current_tenant.id,
    ).first()
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call summary not found")
    return summary

