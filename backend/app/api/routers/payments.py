"""
Payments router (Stripe-ready).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_log_service import AuditLogService
from app.services.email_service import EmailService
from app.services.payment_service import PaymentService

try:
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None

router = APIRouter(prefix="/payments", tags=["Payments"])


class CheckoutRequest(BaseModel):
    plan_name: str
    interval: Literal["monthly", "yearly"] = "monthly"


class CheckoutResponse(BaseModel):
    checkout_url: str
    provider: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> CheckoutResponse:
    plan = db.query(Plan).filter(Plan.name == payload.plan_name).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan bulunamadı")

    if float(plan.price_monthly) <= 0 and float(plan.price_yearly) <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ücretsiz plan için ödeme gerekmez"
        )

    service = PaymentService(db)
    result = service.create_checkout_session(
        tenant_id=current_tenant.id,
        user_id=current_user.id,
        user_email=current_user.email,
        tenant_name=current_tenant.name,
        plan=plan,
        interval=payload.interval
    )

    AuditLogService(db).log(
        action="payments.checkout.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="subscription",
        resource_id=str(current_tenant.id),
        payload={"plan_name": plan.name, "interval": payload.interval, "provider": result.provider},
    )

    return CheckoutResponse(checkout_url=result.checkout_url, provider=result.provider)


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Stripe webhook endpoint.
    """
    from app.core.config import settings

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
            secret=webhook_secret
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook imzası doğrulanamadı")

    event_type = getattr(event, "type", "")
    data_object = getattr(getattr(event, "data", None), "object", None)

    if event_type == "checkout.session.completed" and data_object is not None:
        metadata = getattr(data_object, "metadata", {}) or {}
        tenant_id_raw = (metadata.get("tenant_id") or getattr(data_object, "client_reference_id", "") or "").strip()
        plan_name = (metadata.get("plan_name") or "").strip()
        if not tenant_id_raw or not plan_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook metadata eksik")

        try:
            tenant_id = UUID(tenant_id_raw)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id geçersiz")

        subscription_id = getattr(data_object, "subscription", None)
        customer_id = getattr(data_object, "customer", None)

        service = PaymentService(db)
        subscription = service.apply_successful_checkout(
            tenant_id=tenant_id,
            plan_name=plan_name,
            stripe_customer_id=str(customer_id) if customer_id else None,
            stripe_subscription_id=str(subscription_id) if subscription_id else None,
        )

        tenant = subscription.tenant
        user = db.query(User).filter(User.id == tenant.owner_id).first() if tenant else None
        plan = subscription.plan

        AuditLogService(db).log(
            action="payments.webhook.checkout_completed",
            tenant_id=str(tenant_id),
            user_id=str(user.id) if user else None,
            resource_type="subscription",
            resource_id=str(subscription.id),
            payload={
                "event": event_type,
                "plan_name": plan_name,
                "stripe_customer_id": str(customer_id) if customer_id else None,
                "stripe_subscription_id": str(subscription_id) if subscription_id else None,
            },
        )

        if user and plan and tenant:
            EmailService.send_plan_change_email(
                email=user.email,
                full_name=user.full_name,
                tenant_name=tenant.name,
                plan_display_name=plan.display_name,
                action="Ödeme tamamlandı / Plan aktif edildi"
            )

    return {"received": True}

