"""Ticketing API routes."""

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.ticket import Ticket, TicketMessage
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.ticket import (
    TicketCreate,
    TicketDetailResponse,
    TicketMessageCreate,
    TicketMessageResponse,
    TicketResponse,
    TicketUpdate,
)
from app.services.audit_log_service import AuditLogService
from app.services.system_event_service import SystemEventService
from app.core.time import utc_now_naive

router = APIRouter(prefix="/tickets", tags=["Tickets"])


class PrivacyRequestCreate(BaseModel):
    request_type: Literal["export", "deletion", "correction"]
    consent_ack: bool
    note: str | None = Field(default=None, max_length=1000)


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    tenant_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tickets:manage"]))
):
    query = db.query(Ticket)

    if current_user.is_admin:
        if tenant_id:
            query = query.filter(Ticket.tenant_id == tenant_id)
    else:
        query = query.filter(Ticket.tenant_id == str(current_tenant.id))

    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if priority:
        query = query.filter(Ticket.priority == priority)

    return query.order_by(Ticket.last_activity_at.desc()).offset(skip).limit(limit).all()


@router.post("", response_model=TicketDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tickets:create"]))
):
    ticket = Ticket(
        tenant_id=str(current_tenant.id),
        requester_id=str(current_user.id),
        subject=payload.subject,
        status="open",
        priority=payload.priority or "normal",
        last_activity_at=utc_now_naive(),
    )
    db.add(ticket)
    db.flush()

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=str(current_user.id),
        sender_type="user",
        body=payload.message,
    )
    db.add(message)
    db.commit()
    db.refresh(ticket)

    AuditLogService(db).log(
        action="ticket.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="ticket",
        resource_id=str(ticket.id),
        payload={"subject": ticket.subject, "priority": ticket.priority},
    )

    return TicketDetailResponse(
        **TicketResponse.model_validate(ticket).model_dump(),
        messages=[TicketMessageResponse.model_validate(message)]
    )


@router.post("/privacy-requests", response_model=TicketDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_privacy_request(
    payload: PrivacyRequestCreate,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tickets:create"])),
):
    """Create an auditable privacy operation; destructive work is never immediate."""
    if not payload.consent_ack:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Talebi onaylamanız gerekir")
    labels = {
        "export": "Kişisel veri dışa aktarma talebi",
        "deletion": "Kişisel veri silme talebi",
        "correction": "Kişisel veri düzeltme talebi",
    }
    subject = f"{labels[payload.request_type]} [{current_user.id}]"
    existing = db.query(Ticket).filter(
        Ticket.tenant_id == str(current_tenant.id),
        Ticket.requester_id == str(current_user.id),
        Ticket.subject == subject,
        Ticket.status.in_(["open", "pending"]),
    ).first()
    if existing:
        messages = db.query(TicketMessage).filter(TicketMessage.ticket_id == existing.id).order_by(TicketMessage.created_at.asc()).all()
        return TicketDetailResponse(
            **TicketResponse.model_validate(existing).model_dump(),
            messages=[TicketMessageResponse.model_validate(message) for message in messages],
        )

    ticket = Ticket(
        tenant_id=str(current_tenant.id),
        requester_id=str(current_user.id),
        subject=subject,
        status="open",
        priority="high" if payload.request_type == "deletion" else "normal",
        last_activity_at=utc_now_naive(),
    )
    db.add(ticket)
    db.flush()
    message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=str(current_user.id),
        sender_type="user",
        body=(
            f"Talep türü: {payload.request_type}. Kullanıcı işlemi açıkça onayladı. "
            f"Not: {payload.note or 'Ek not yok.'}"
        ),
    )
    db.add(message)
    db.commit()
    db.refresh(ticket)
    AuditLogService(db).log(
        action=f"privacy.request.{payload.request_type}",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="ticket",
        resource_id=ticket.id,
        payload={"request_type": payload.request_type, "consent_ack": True},
    )
    SystemEventService(db).log(
        tenant_id=str(current_tenant.id),
        source="privacy",
        level="warning" if payload.request_type == "deletion" else "info",
        code="PRIVACY_REQUEST_CREATED",
        message=labels[payload.request_type],
        meta_json={"ticket_id": ticket.id, "request_type": payload.request_type, "user_id": str(current_user.id)},
    )
    return TicketDetailResponse(
        **TicketResponse.model_validate(ticket).model_dump(),
        messages=[TicketMessageResponse.model_validate(message)],
    )


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tickets:manage"]))
):
    query = db.query(Ticket).filter(Ticket.id == str(ticket_id))
    if not current_user.is_admin:
        query = query.filter(Ticket.tenant_id == str(current_tenant.id))
    ticket = query.first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket bulunamadı")

    messages = db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket.id).order_by(TicketMessage.created_at.asc()).all()

    return TicketDetailResponse(
        **TicketResponse.model_validate(ticket).model_dump(),
        messages=[TicketMessageResponse.model_validate(msg) for msg in messages]
    )


@router.post("/{ticket_id}/messages", response_model=TicketMessageResponse)
async def add_ticket_message(
    ticket_id: UUID,
    payload: TicketMessageCreate,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tickets:create"]))
):
    query = db.query(Ticket).filter(Ticket.id == str(ticket_id))
    if not current_user.is_admin:
        query = query.filter(Ticket.tenant_id == str(current_tenant.id))
    ticket = query.first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket bulunamadı")

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=str(current_user.id),
        sender_type="staff" if current_user.is_admin else "user",
        body=payload.body,
    )
    ticket.last_activity_at = utc_now_naive()

    db.add(message)
    db.commit()
    db.refresh(message)

    AuditLogService(db).log(
        action="ticket.message",
        tenant_id=str(ticket.tenant_id),
        user_id=str(current_user.id),
        resource_type="ticket",
        resource_id=str(ticket.id),
        payload={"sender_type": message.sender_type},
    )

    return TicketMessageResponse.model_validate(message)


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tickets:manage"]))
):
    query = db.query(Ticket).filter(Ticket.id == str(ticket_id))
    if not current_user.is_admin:
        query = query.filter(Ticket.tenant_id == str(current_tenant.id))
    ticket = query.first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket bulunamadı")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ticket, key, value)
    ticket.last_activity_at = utc_now_naive()

    db.commit()
    db.refresh(ticket)

    AuditLogService(db).log(
        action="ticket.update",
        tenant_id=str(ticket.tenant_id),
        user_id=str(current_user.id),
        resource_type="ticket",
        resource_id=str(ticket.id),
        payload=update_data,
    )

    return TicketResponse.model_validate(ticket)
