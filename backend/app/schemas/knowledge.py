"""
Pydantic schemas for BotKnowledgeItem model.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KnowledgeItemBase(BaseModel):
    """Base schema for KnowledgeItem."""
    title: str
    question: str
    answer: str


class KnowledgeItemCreate(KnowledgeItemBase):
    """Schema for creating a new knowledge item."""
    pass


class KnowledgeItemUpdate(BaseModel):
    """Schema for updating a knowledge item."""
    title: str | None = None
    question: str | None = None
    answer: str | None = None


class KnowledgeItemResponse(KnowledgeItemBase):
    """Schema for knowledge item response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    bot_id: UUID
    created_at: datetime

