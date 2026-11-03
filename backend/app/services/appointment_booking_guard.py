"""Serialize bookings on the tenant, shared with the AI booking path."""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.tenant import Tenant


def lock_booking_calendar(db: Session, tenant_id: UUID) -> None:
    db.query(Tenant).filter(Tenant.id == tenant_id).with_for_update().one()


def require_available_interval(
    db: Session,
    tenant_id: UUID,
    starts_at: datetime,
    duration_minutes: int,
    *,
    exclude_id: UUID | None = None,
) -> None:
    end = starts_at + timedelta(minutes=duration_minutes)
    query = db.query(Appointment).filter(
        Appointment.tenant_id == tenant_id,
        Appointment.status != "cancelled",
        Appointment.starts_at < end,
    )
    if exclude_id is not None:
        query = query.filter(Appointment.id != exclude_id)
    for existing in query.yield_per(100):
        if existing.starts_at + timedelta(minutes=existing.duration_minutes) > starts_at:
            raise HTTPException(status_code=409, detail="Seçilen saat başka bir randevu ile çakışıyor. Lütfen başka bir saat seçin.")
