"""Ticketing API routes."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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

router = APIRouter(prefix="/tickets", tags=["Tickets"])


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
        last_activity_at=datetime.utcnow(),
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
    ticket.last_activity_at = datetime.utcnow()

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
    ticket.last_activity_at = datetime.utcnow()

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
