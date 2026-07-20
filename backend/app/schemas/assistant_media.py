"""Schemas for the tenant assistant media library."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssistantMediaUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1200)
    keywords: list[str] | None = Field(default=None, max_length=12)
    is_active: bool | None = None

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        result: list[str] = []
        for item in value:
            normalized = item.strip()[:60]
            if normalized and normalized.casefold() not in {existing.casefold() for existing in result}:
                result.append(normalized)
        return result


class AssistantMediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    media_type: Literal["image", "video", "catalog"]
    mime_type: str
    file_size_bytes: int
    keywords: list[str]
    is_active: bool
    send_count: int
    last_sent_at: datetime | None
    preview_url: str
    created_at: datetime
    updated_at: datetime
