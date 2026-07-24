"""Product analytics endpoints."""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.rate_limit import RateLimiter, rate_limit_key, require_rate_limit
from app.db.session import get_db
from app.dependencies.auth import get_access_token_payload, get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.user import User
from app.services.product_analytics_service import ProductAnalyticsService


router = APIRouter(tags=["product-analytics"])
event_rate_limiter = RateLimiter(240, 60, "product-events")


class ProductEventInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: Literal["navigation", "action", "error", "funnel", "performance"] = "action"
    path: str | None = Field(default=None, max_length=500)
    session_id: str = Field(min_length=8, max_length=64)
    properties: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class ProductEventBatch(BaseModel):
    events: list[ProductEventInput] = Field(min_length=1, max_length=20)


async def _require_super_admin(
    user: User = Depends(get_current_user),
    token: dict = Depends(get_access_token_payload),
) -> User:
    if not user.is_admin or token.get("portal") != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user


@router.post("/product-analytics/events", status_code=status.HTTP_202_ACCEPTED)
async def collect_product_events(
    payload: ProductEventBatch,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    require_rate_limit(
        event_rate_limiter,
        rate_limit_key(request, "product-events", tenant.id, current_user.id),
    )
    accepted = ProductAnalyticsService(db).record_batch(
        tenant_id=tenant.id,
        user_id=current_user.id,
        events=[event.model_dump() for event in payload.events],
    )
    return {"accepted": accepted}


@router.get("/product-analytics/friction")
async def tenant_product_friction(
    days: int = Query(default=30, ge=1, le=90),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> dict:
    return ProductAnalyticsService(db).friction_summary(days=days, tenant_id=tenant.id)


@router.get("/admin/product-analytics/friction")
async def global_product_friction(
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
) -> dict:
    return ProductAnalyticsService(db).friction_summary(days=days)
