"""
Appointment management routes with email reminders.
"""

from datetime import date, datetime, timedelta
from app.core.time import utc_now_naive
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.appointment import Appointment
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentAvailabilityResponse,
    AppointmentReminderResult,
    AppointmentResponse,
    AppointmentSettingsPayload,
    AppointmentUpdate
)
from app.services.appointment_availability_service import AppointmentAvailabilityService
from app.services.audit_log_service import AuditLogService
from app.services.email_service import EmailService
from app.services.push_notification_service import send_tenant_push_notification

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def _format_datetime_label(value: datetime) -> str:
    return value.strftime("%d.%m.%Y %H:%M")


@router.get("/settings", response_model=AppointmentSettingsPayload)
async def get_appointment_settings(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    return AppointmentAvailabilityService(db).get_settings(current_tenant)


@router.patch("/settings", response_model=AppointmentSettingsPayload)
async def update_appointment_settings(
    payload: AppointmentSettingsPayload,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"])),
):
    try:
        result = AppointmentAvailabilityService(db).update_settings(
            current_tenant,
            payload.model_dump(),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    AuditLogService(db).log(
        action="appointment.settings.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="appointment_settings",
        resource_id=str(current_tenant.id),
        payload={
            "timezone": result["timezone"],
            "service_count": len(result["services"]),
            "booking_window_days": result["booking_window_days"],
        },
    )
    return result


@router.get("/availability", response_model=AppointmentAvailabilityResponse)
async def get_appointment_availability(
    start_date: date | None = None,
    days: int = Query(default=7, ge=1, le=31),
    service_id: str | None = Query(default=None, max_length=60),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
):
    return AppointmentAvailabilityService(db).get_available_slots(
        current_tenant,
        start_date=start_date,
        days=days,
        service_id=service_id,
        limit=200,
    )


@router.get("", response_model=list[AppointmentResponse])
async def list_appointments(
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
):
    query = db.query(Appointment).filter(Appointment.tenant_id == current_tenant.id)
    if status_filter:
        query = query.filter(Appointment.status == status_filter)
    appointments = query.order_by(Appointment.starts_at.asc()).all()
    return [AppointmentResponse.model_validate(item) for item in appointments]


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    appointment = Appointment(
        tenant_id=current_tenant.id,
        created_by=current_user.id,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        customer_phone=payload.customer_phone,
        subject=payload.subject,
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
        notes=payload.notes,
        reminder_before_minutes=payload.reminder_before_minutes,
        status="scheduled"
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    if appointment.customer_email:
        background_tasks.add_task(
            EmailService.send_appointment_created_email,
            appointment.customer_email,
            appointment.customer_name,
            appointment.subject,
            _format_datetime_label(appointment.starts_at)
        )

    AuditLogService(db).log(
        action="appointment.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="appointment",
        resource_id=str(appointment.id),
        payload={
            "subject": appointment.subject,
            "starts_at": appointment.starts_at.isoformat(),
            "customer_email": appointment.customer_email
        }
    )
    background_tasks.add_task(
        send_tenant_push_notification,
        tenant_id=current_tenant.id,
        event_type="appointment",
        title="Yeni randevu oluşturuldu",
        body=f"{appointment.customer_name} için {appointment.subject} randevusu kaydedildi.",
        url="/dashboard/appointments",
        tag="svontai-appointment",
        extra={"appointment_id": str(appointment.id)},
    )

    return AppointmentResponse.model_validate(appointment)


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: UUID,
    payload: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.tenant_id == current_tenant.id
    ).first()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Randevu bulunamadı")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(appointment, key, value)
    if {"customer_name", "customer_email", "customer_phone", "subject", "starts_at", "duration_minutes", "notes", "status"} & update_data.keys():
        appointment.calendar_sync_status = "pending"
        appointment.calendar_last_error = None
    db.commit()
    db.refresh(appointment)

    AuditLogService(db).log(
        action="appointment.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="appointment",
        resource_id=str(appointment.id),
        payload=update_data
    )

    return AppointmentResponse.model_validate(appointment)


@router.post("/send-reminders", response_model=AppointmentReminderResult)
async def send_due_reminders(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    now = utc_now_naive()
    appointments = db.query(Appointment).filter(
        Appointment.tenant_id == current_tenant.id,
        Appointment.status != "cancelled",
        Appointment.customer_email.isnot(None)
    ).all()

    sent_before = 0
    sent_after = 0

    for appointment in appointments:
        if not appointment.customer_email:
            continue

        before_trigger = appointment.starts_at - timedelta(minutes=appointment.reminder_before_minutes)
        if (
            appointment.reminder_before_sent_at is None
            and now >= before_trigger
            and now <= appointment.starts_at + timedelta(minutes=5)
        ):
            appointment.reminder_before_sent_at = now
            sent_before += 1
            background_tasks.add_task(
                EmailService.send_appointment_before_reminder_email,
                appointment.customer_email,
                appointment.customer_name,
                appointment.subject,
                _format_datetime_label(appointment.starts_at)
            )

        after_trigger = appointment.starts_at + timedelta(minutes=30)
        if (
            appointment.reminder_after_sent_at is None
            and now >= after_trigger
        ):
            appointment.reminder_after_sent_at = now
            sent_after += 1
            background_tasks.add_task(
                EmailService.send_appointment_after_followup_email,
                appointment.customer_email,
                appointment.customer_name,
                appointment.subject
            )

    if sent_before or sent_after:
        db.commit()

    AuditLogService(db).log(
        action="appointment.reminders.dispatch",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="appointment",
        resource_id=str(current_tenant.id),
        payload={"sent_before": sent_before, "sent_after": sent_after}
    )

    return AppointmentReminderResult(sent_before=sent_before, sent_after=sent_after)
