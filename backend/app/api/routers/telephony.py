"""
Telephony registry + resolution endpoints.

Voice Gateway uses /api/v1/telephony/resolve to map inbound "To" number -> tenant_id.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.voice_security import verify_voice_gateway_request_dependency
from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.telephony import TelephonyNumber
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.telephony import (
    TelephonyNumberCreate,
    TelephonyNumberResponse,
    TelephonyResolveResponse,
)
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/api/v1/telephony", tags=["Telephony"])

class TelephonyResolveRequest(BaseModel):
    to: str = Field(..., min_length=6, max_length=60)


@router.get("/numbers", response_model=list[TelephonyNumberResponse])
async def list_numbers(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
):
    return db.query(TelephonyNumber).filter(
        TelephonyNumber.tenant_id == current_tenant.id
    ).order_by(TelephonyNumber.created_at.desc()).all()


@router.post("/numbers", response_model=TelephonyNumberResponse, status_code=status.HTTP_201_CREATED)
async def create_number(
    payload: TelephonyNumberCreate,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    _: None = Depends(require_permissions(["settings:write"])),
):
    number = TelephonyNumber(
        tenant_id=current_tenant.id,
        provider=(payload.provider or "twilio").strip()[:40],
        phone_number=payload.phone_number.strip(),
        label=(payload.label.strip() if isinstance(payload.label, str) and payload.label.strip() else None),
        is_active=bool(payload.is_active),
        meta_json=payload.meta_json or {},
    )
    db.add(number)
    try:
        db.commit()
        db.refresh(number)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Telefon numarası kaydedilemedi")

    AuditLogService(db).safe_log(
        action="telephony.number.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="telephony_number",
        resource_id=str(number.id),
        payload={"phone_number": number.phone_number, "provider": number.provider},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
    )

    return number


@router.post("/resolve", response_model=TelephonyResolveResponse)
async def resolve_tenant_by_number(
    request: Request,
    payload: TelephonyResolveRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_voice_gateway_request_dependency),
):
    normalized = payload.to.strip()
    record = db.query(TelephonyNumber).filter(
        TelephonyNumber.phone_number == normalized,
        TelephonyNumber.is_active.is_(True),
    ).first()

    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tenant mapping for this number")

    return TelephonyResolveResponse(tenantId=str(record.tenant_id), provider=record.provider, phoneNumber=record.phone_number)
