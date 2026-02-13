"""
Pydantic schemas for Plan model.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlanBase(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    plan_type: str
    price_monthly: float
    price_yearly: float
    currency: str
    message_limit: int
    bot_limit: int
    knowledge_items_limit: int
    feature_flags: dict
    trial_days: int
    is_active: bool
    is_public: bool
    sort_order: int


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    plan_type: str | None = None
    price_monthly: float | None = None
    price_yearly: float | None = None
    currency: str | None = None
    message_limit: int | None = None
    bot_limit: int | None = None
    knowledge_items_limit: int | None = None
    feature_flags: dict | None = None
    trial_days: int | None = None
    is_active: bool | None = None
    is_public: bool | None = None
    sort_order: int | None = None


class PlanResponse(PlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
