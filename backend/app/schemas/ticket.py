"""Pydantic schemas for tickets."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TicketMessageBase(BaseModel):
    body: str


class TicketMessageCreate(TicketMessageBase):
    pass


class TicketMessageResponse(TicketMessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sender_id: str | None = None
    sender_type: str
    created_at: datetime


class TicketBase(BaseModel):
    subject: str
    status: str
    priority: str


class TicketCreate(BaseModel):
    subject: str
    priority: str = "normal"
    message: str


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to: str | None = None


class TicketResponse(TicketBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    requester_id: str | None = None
    assigned_to: str | None = None
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime


class TicketDetailResponse(TicketResponse):
    messages: list[TicketMessageResponse] = []
