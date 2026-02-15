"""
Payments service (Stripe-ready).

This module intentionally keeps payment provider details behind a small API so we
can swap providers (iyzico, paytr, etc.) later without touching routers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.plan import Plan
from app.models.subscription import TenantSubscription
from app.services.subscription_service import SubscriptionService

try:
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None


BillingInterval = Literal["monthly", "yearly"]


@dataclass(frozen=True)
class CheckoutSessionResult:
    checkout_url: str
    provider: str


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.subscription_service = SubscriptionService(db)

    def _get_price_id(self, plan_name: str, interval: BillingInterval) -> str:
        plan_map = settings.STRIPE_PRICE_IDS.get(plan_name, {})
        price_id = (plan_map.get(interval) or "").strip()
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe price id tanımlı değil (plan={plan_name}, interval={interval})"
            )
        return price_id

    def _require_payments_enabled(self) -> None:
        if not settings.PAYMENTS_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ödeme altyapısı aktif değil"
            )
        if settings.PAYMENTS_PROVIDER != "stripe":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Desteklenmeyen ödeme sağlayıcısı"
            )
        if stripe is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe bağımlılığı yüklenmemiş"
            )
        if not settings.STRIPE_SECRET_KEY.strip():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe secret key eksik"
            )

    def create_checkout_session(
        self,
        tenant_id: UUID,
        user_id: UUID,
        user_email: str,
        tenant_name: str,
        plan: Plan,
        interval: BillingInterval = "monthly"
    ) -> CheckoutSessionResult:
        """
        Create a provider checkout session and return a redirect URL.

        For free plans, this should not be called.
        """
        self._require_payments_enabled()
        stripe.api_key = settings.STRIPE_SECRET_KEY.strip()

        subscription = self.subscription_service.get_subscription(tenant_id)
        if subscription is None:
            subscription = self.subscription_service.create_subscription(tenant_id, "free")

        customer_id = (subscription.external_customer_id or "").strip()
        if not customer_id:
            customer = stripe.Customer.create(
                email=user_email,
                name=tenant_name,
                metadata={
                    "tenant_id": str(tenant_id),
                    "created_by_user_id": str(user_id),
                },
            )
            customer_id = customer.id
            subscription.external_customer_id = customer_id
            subscription.payment_provider = "stripe"
            self.db.commit()

        success_url = (settings.STRIPE_SUCCESS_URL or f"{settings.FRONTEND_URL}/dashboard/billing?payment=success").strip()
        cancel_url = (settings.STRIPE_CANCEL_URL or f"{settings.FRONTEND_URL}/dashboard/billing?payment=cancel").strip()

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[
                {"price": self._get_price_id(plan.name, interval), "quantity": 1}
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(tenant_id),
            metadata={
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "plan_name": plan.name,
                "interval": interval,
            },
            subscription_data={
                "metadata": {
                    "tenant_id": str(tenant_id),
                    "plan_name": plan.name,
                    "interval": interval,
                }
            },
            allow_promotion_codes=True,
        )

        checkout_url = (session.url or "").strip()
        if not checkout_url:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Checkout URL üretilemedi"
            )
        return CheckoutSessionResult(checkout_url=checkout_url, provider="stripe")

    def apply_successful_checkout(
        self,
        tenant_id: UUID,
        plan_name: str,
        stripe_customer_id: str | None,
        stripe_subscription_id: str | None
    ) -> TenantSubscription:
        subscription = self.subscription_service.upgrade_plan(tenant_id, plan_name)
        subscription.payment_provider = "stripe"
        if stripe_customer_id:
            subscription.external_customer_id = stripe_customer_id
        if stripe_subscription_id:
            subscription.external_subscription_id = stripe_subscription_id
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

