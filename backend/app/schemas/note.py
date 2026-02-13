"""
Schemas for workspace notes.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    content: str = Field(min_length=1)
    color: str = Field(default="slate", max_length=30)
    pinned: bool = False
    position_x: int = 0
    position_y: int = 0


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    content: str | None = Field(default=None, min_length=1)
    color: str | None = Field(default=None, max_length=30)
    pinned: bool | None = None
    position_x: int | None = None
    position_y: int | None = None
    archived: bool | None = None


class NoteResponse(BaseModel):
    id: str
    tenant_id: str
    created_by: str | None
    title: str
    content: str
    color: str
    pinned: bool
    position_x: int
    position_y: int
    archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
