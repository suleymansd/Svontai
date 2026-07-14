"""
Schemas for voice calls.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    lead_id: UUID | None = None
    provider: str
    provider_call_id: str
    direction: str
    status: str
    from_number: str
    to_number: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int
    recording_url: str | None = None
    cost_estimate: float | None = None
    created_at: datetime
    updated_at: datetime


class CallTranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    call_id: UUID
    segment_index: int
    speaker: str
    text: str
    ts_iso: str | None = None
    created_at: datetime


class CallSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    call_id: UUID
    intent: str | None = None
    labels_json: dict
    action_items_json: dict
    summary: str
    created_at: datetime
    updated_at: datetime
