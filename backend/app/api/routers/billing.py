"""Billing endpoints for plans, limits, and Stripe flows."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.plan import Plan
from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.tenant import Tenant
from app.models.user import User
from app.services.billing_service import BillingService
from app.services.payment_service import PaymentService

try:
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None


router = APIRouter(prefix="/billing", tags=["Billing"])


class BillingPlanResponse(BaseModel):
    plan: Literal["free", "pro", "premium", "enterprise"]
    renew_at: str | None = None
    status: str
    seats: int | None = None
    notes: str | None = None


class BillingLimitsBody(BaseModel):
    monthly_runs: int
    rate_limits: dict[str, int] = Field(default_factory=dict)


class BillingUsageBody(BaseModel):
    monthly_runs_used: int
    monthly_runs_remaining: int
    by_tool: dict[str, int] = Field(default_factory=dict)
    chart_30d: list[dict[str, int | str]] = Field(default_factory=list)


class BillingLimitsResponse(BaseModel):
    plan: Literal["free", "pro", "premium", "enterprise"]
    limits: BillingLimitsBody
    usage: BillingUsageBody


class StripeCheckoutRequest(BaseModel):
    plan: Literal["pro", "premium"]
    interval: Literal["monthly", "yearly"] = "monthly"


class StripeCheckoutResponse(BaseModel):
    url: str


class StripePortalResponse(BaseModel):
    url: str


def _to_dict(obj: Any) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict_recursive"):
        try:
            return obj.to_dict_recursive()
        except Exception:
            return {}
    return {}


def _read_value(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_uuid(raw: str | None, field_name: str) -> UUID:
    value = (raw or "").strip()
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} missing")
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} invalid") from exc


@router.get("/plan", response_model=BillingPlanResponse)
async def get_billing_plan(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> BillingPlanResponse:
    payload = BillingService(db).get_plan_payload(current_tenant.id)
    return BillingPlanResponse(
        plan=payload["plan"],
        renew_at=payload["renew_at"],
        status=payload["status"],
        seats=payload.get("seats"),
        notes=payload.get("notes"),
    )


@router.get("/limits", response_model=BillingLimitsResponse)
async def get_billing_limits(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> BillingLimitsResponse:
    payload = BillingService(db).get_limits_payload(current_tenant.id)
    return BillingLimitsResponse(
        plan=payload["plan"],
        limits=BillingLimitsBody(
            monthly_runs=payload["limits"]["monthly_runs"],
            rate_limits=payload["limits"]["rate_limits"],
        ),
        usage=BillingUsageBody(
            monthly_runs_used=payload["usage"]["monthly_runs_used"],
            monthly_runs_remaining=payload["usage"]["monthly_runs_remaining"],
            by_tool=payload["usage"]["by_tool"],
            chart_30d=payload["usage"]["chart_30d"],
        ),
    )


@router.post("/stripe/checkout-session", response_model=StripeCheckoutResponse)
async def create_stripe_checkout_session(
    payload: StripeCheckoutRequest,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
) -> StripeCheckoutResponse:
    plan = db.query(Plan).filter(Plan.name == payload.plan).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan bulunamadı")

    result = PaymentService(db).create_checkout_session(
        tenant_id=current_tenant.id,
        user_id=current_user.id,
        user_email=current_user.email,
        tenant_name=current_tenant.name,
        plan=plan,
        interval=payload.interval,
    )
    return StripeCheckoutResponse(url=result.checkout_url)


@router.get("/stripe/portal", response_model=StripePortalResponse)
async def create_stripe_portal_session(
    return_url: str | None = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
) -> StripePortalResponse:
    url = PaymentService(db).create_billing_portal_session(
        tenant_id=current_tenant.id,
        return_url=return_url,
    )
    return StripePortalResponse(url=url)


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
    db: Session = Depends(get_db),
) -> dict:
    if stripe is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe bağımlılığı yok")

    webhook_secret = settings.STRIPE_WEBHOOK_SECRET.strip()
    if not webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe webhook secret eksik")
    if not stripe_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="stripe-signature header eksik")

    payload_bytes = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload_bytes,
            sig_header=stripe_signature,
            secret=webhook_secret,
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook imzası doğrulanamadı")

    event_id = str(_read_value(event, "id", "")).strip()
    event_type = str(_read_value(event, "type", "")).strip()
    if not event_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe event id missing")

    event_row = db.query(StripeWebhookEvent).filter(StripeWebhookEvent.event_id == event_id).first()
    if event_row and event_row.processed:
        return {"received": True, "duplicate": True}

    if event_row is None:
        event_row = StripeWebhookEvent(
            event_id=event_id,
            event_type=event_type or "unknown",
            payload_json=_to_dict(event),
            processed=False,
        )
        db.add(event_row)
        db.commit()
        db.refresh(event_row)

    payment_service = PaymentService(db)
    data_object = _read_value(_read_value(event, "data"), "object")
    metadata = _read_value(data_object, "metadata", {}) or {}

    tenant_id: UUID | None = None

    if event_type == "checkout.session.completed" and data_object is not None:
        tenant_id = _parse_uuid(
            _read_value(metadata, "tenant_id") or _read_value(data_object, "client_reference_id"),
            "tenant_id",
        )
        plan_name = str(_read_value(metadata, "plan_name", "")).strip()
        if not plan_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="plan_name missing")

        payment_service.sync_subscription_from_webhook(
            tenant_id=tenant_id,
            stripe_customer_id=_read_value(data_object, "customer"),
            stripe_subscription_id=_read_value(data_object, "subscription"),
            stripe_status="active",
            plan_name=plan_name,
        )

    if event_type in {"customer.subscription.updated", "customer.subscription.deleted"} and data_object is not None:
        tenant_id = _parse_uuid(_read_value(metadata, "tenant_id"), "tenant_id")

        item_rows = _read_value(_read_value(data_object, "items", {}), "data", []) or []
        first_item = item_rows[0] if item_rows else {}
        price_obj = _read_value(first_item, "price", {})
        price_id = _read_value(price_obj, "id")
        resolved_plan = _read_value(metadata, "plan_name") or payment_service.resolve_plan_name_from_price_id(price_id)

        payment_service.sync_subscription_from_webhook(
            tenant_id=tenant_id,
            stripe_customer_id=_read_value(data_object, "customer"),
            stripe_subscription_id=_read_value(data_object, "id"),
            stripe_status=_read_value(data_object, "status"),
            current_period_end_ts=_read_value(data_object, "current_period_end"),
            plan_name=str(resolved_plan).strip() if resolved_plan else None,
        )

    event_row.processed = True
    event_row.processed_at = datetime.utcnow()
    if tenant_id:
        event_row.tenant_id = tenant_id
    db.commit()

    return {"received": True}
