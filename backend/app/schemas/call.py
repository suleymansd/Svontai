"""
Schemas for voice calls.
"""

from pydantic import BaseModel


class CallResponse(BaseModel):
    id: str
    tenant_id: str
    lead_id: str | None = None
    provider: str
    provider_call_id: str
    direction: str
    status: str
    from_number: str
    to_number: str
    started_at: str | None = None
    ended_at: str | None = None
    duration_seconds: int
    recording_url: str | None = None
    cost_estimate: float | None = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CallTranscriptResponse(BaseModel):
    id: str
    call_id: str
    segment_index: int
    speaker: str
    text: str
    ts_iso: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class CallSummaryResponse(BaseModel):
    id: str
    call_id: str
    intent: str | None = None
    labels_json: dict
    action_items_json: dict
    summary: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

