"""
Schemas for appointment management.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AppointmentCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    customer_email: EmailStr | None = None
    subject: str = Field(min_length=1, max_length=255)
    starts_at: datetime
    notes: str | None = None
    reminder_before_minutes: int = Field(default=60, ge=5, le=10080)


class AppointmentUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    customer_email: EmailStr | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    starts_at: datetime | None = None
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
    subject: str
    notes: str | None
    starts_at: datetime
    status: str
    reminder_before_minutes: int
    reminder_before_sent_at: datetime | None
    reminder_after_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AppointmentReminderResult(BaseModel):
    sent_before: int = 0
    sent_after: int = 0
