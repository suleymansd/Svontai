"""
Schemas for appointment management.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AppointmentCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, max_length=40)
    subject: str = Field(min_length=1, max_length=255)
    starts_at: datetime
    duration_minutes: int = Field(default=60, ge=10, le=480)
    notes: str | None = None
    reminder_before_minutes: int = Field(default=60, ge=5, le=10080)


class AppointmentUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, max_length=40)
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    starts_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=10, le=480)
    notes: str | None = None
    status: str | None = Field(default=None, pattern="^(scheduled|completed|cancelled)$")
    reminder_before_minutes: int | None = Field(default=None, ge=5, le=10080)


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    created_by: UUID | None
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    conversation_id: UUID | None
    subject: str
    notes: str | None
    starts_at: datetime
    duration_minutes: int
    source: str
    status: str
    reminder_before_minutes: int
    reminder_before_sent_at: datetime | None
    reminder_after_sent_at: datetime | None
    calendar_provider: str | None
    calendar_event_id: str | None
    calendar_sync_status: str
    calendar_last_error: str | None
    calendar_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AppointmentReminderResult(BaseModel):
    sent_before: int = 0
    sent_after: int = 0


class AppointmentServiceItem(BaseModel):
    id: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(default=60, ge=10, le=480)
    active: bool = True


class BusinessHoursDay(BaseModel):
    enabled: bool = False
    start: str = Field(default="09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(default="18:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    @field_validator("end")
    @classmethod
    def validate_range(cls, value: str, info):
        start = info.data.get("start")
        if start and value <= start:
            raise ValueError("Bitiş saati başlangıç saatinden sonra olmalıdır")
        return value


class AppointmentSettingsPayload(BaseModel):
    configured: bool = False
    timezone: str = Field(default="Europe/Istanbul", min_length=1, max_length=80)
    minimum_notice_hours: int = Field(default=2, ge=0, le=720)
    booking_window_days: int = Field(default=30, ge=1, le=365)
    slot_interval_minutes: int = Field(default=30, ge=10, le=240)
    booking_location: str = Field(default="", max_length=300)
    booking_notes: str = Field(default="", max_length=1000)
    services: list[AppointmentServiceItem] = Field(default_factory=list, max_length=30)
    weekly_hours: dict[str, BusinessHoursDay]
    closed_dates: list[str] = Field(default_factory=list, max_length=100)


class AvailabilitySlotResponse(BaseModel):
    start_at: datetime
    end_at: datetime
    local_label: str
    service_id: str
    service_name: str
    duration_minutes: int


class AppointmentAvailabilityResponse(BaseModel):
    timezone: str
    reliable: bool = True
    calendar_connected: bool = False
    warnings: list[str] = Field(default_factory=list)
    slots: list[AvailabilitySlotResponse] = Field(default_factory=list)
