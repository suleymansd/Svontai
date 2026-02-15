"""
Subscription API router for managing plans and subscriptions.
"""

from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.user import User
from app.models.tenant import Tenant
from app.models.plan import Plan
from app.models.subscription import TenantSubscription
from app.services.subscription_service import SubscriptionService
from app.services.audit_log_service import AuditLogService
from app.services.email_service import EmailService


router = APIRouter(prefix="/subscription", tags=["subscription"])


# Schemas
class PlanResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: Optional[str]
    plan_type: str
    price_monthly: float
    price_yearly: float
    currency: str
    message_limit: int
    bot_limit: int
    knowledge_items_limit: int
    feature_flags: dict
    trial_days: int
    
    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    id: str
    plan_name: str
    plan_display_name: str
    status: str
    started_at: str
    trial_ends_at: Optional[str]
    current_period_end: Optional[str]
    messages_used: int
    message_limit: int
    
    class Config:
        from_attributes = True


class UsageStatsResponse(BaseModel):
    plan_name: str
    plan_type: str
    messages_used: int
    message_limit: int
    messages_remaining: int
    message_usage_percent: float
    bot_limit: int
    knowledge_limit: int
    status: str
    trial_ends_at: Optional[str]
    current_period_end: Optional[str]
    features: dict


class UpgradeRequest(BaseModel):
    plan_name: str


# Endpoints
@router.get("/plans", response_model=List[PlanResponse])
async def list_plans(
    db: Session = Depends(get_db)
):
    """List all available plans."""
    plans = db.query(Plan).filter(
        Plan.is_active == True,
        Plan.is_public == True
    ).order_by(Plan.sort_order).all()
    
    return [
        PlanResponse(
            id=str(plan.id),
            name=plan.name,
            display_name=plan.display_name,
            description=plan.description,
            plan_type=plan.plan_type,
            price_monthly=float(plan.price_monthly),
            price_yearly=float(plan.price_yearly),
            currency=plan.currency,
            message_limit=plan.message_limit,
            bot_limit=plan.bot_limit,
            knowledge_items_limit=plan.knowledge_items_limit,
            feature_flags=plan.feature_flags,
            trial_days=plan.trial_days
        )
        for plan in plans
    ]


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
):
    """Get current tenant's subscription."""
    service = SubscriptionService(db)
    subscription = service.get_subscription(tenant.id)
    
    if not subscription:
        # Create free subscription
        subscription = service.create_subscription(tenant.id, "free")
    
    return SubscriptionResponse(
        id=str(subscription.id),
        plan_name=subscription.plan.name,
        plan_display_name=subscription.plan.display_name,
        status=subscription.status,
        started_at=subscription.started_at.isoformat(),
        trial_ends_at=subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
        current_period_end=subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        messages_used=subscription.messages_used_this_month,
        message_limit=subscription.plan.message_limit
    )


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
):
    """Get current usage statistics."""
    service = SubscriptionService(db)
    stats = service.get_usage_stats(tenant.id)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Abonelik bulunamadı"
        )
    
    return UsageStatsResponse(**stats)


@router.post("/upgrade")
async def upgrade_subscription(
    request: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request_meta: Request = None,
    _: None = Depends(require_permissions(["settings:write"]))
):
    """
    Upgrade to a new plan.
    
    NOTE: This is a stub for payment integration.
    In production, this would:
    1. Create a checkout session with payment provider (Stripe, Iyzico, etc.)
    2. Redirect user to payment page
    3. Handle webhook for successful payment
    4. Then upgrade the subscription
    """
    service = SubscriptionService(db)
    
    # Check if plan exists
    plan = db.query(Plan).filter(Plan.name == request.plan_name).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan bulunamadı"
        )

    if (float(plan.price_monthly) > 0 or float(plan.price_yearly) > 0) and not settings.ALLOW_UNPAID_PLAN_UPGRADES:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Bu plan için ödeme gerekli. Lütfen ödeme sayfasından checkout başlatın."
        )
    
    # For demo/development: Direct upgrade
    # TODO: Integrate with payment provider
    subscription = service.upgrade_plan(tenant.id, request.plan_name)
    AuditLogService(db).log(
        action="subscription.upgrade",
        tenant_id=str(tenant.id),
        user_id=str(current_user.id),
        resource_type="subscription",
        resource_id=str(subscription.id),
        payload={"plan_name": request.plan_name},
        ip_address=request_meta.client.host if request_meta else None,
        user_agent=request_meta.headers.get("User-Agent") if request_meta else None
    )

    EmailService.send_plan_change_email(
        email=current_user.email,
        full_name=current_user.full_name,
        tenant_name=tenant.name,
        plan_display_name=plan.display_name,
        action="Plan yükseltildi"
    )
    
    return {
        "success": True,
        "message": f"{plan.display_name} planına yükseltildi!",
        "subscription_id": str(subscription.id),
        "plan": plan.display_name,
        # In production, return checkout URL
        "checkout_url": None,
        "requires_payment": plan.price_monthly > 0
    }


@router.post("/cancel")
async def cancel_subscription(
    immediate: bool = False,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request_meta: Request = None,
    _: None = Depends(require_permissions(["settings:write"]))
):
    """Cancel current subscription."""
    service = SubscriptionService(db)
    subscription = service.cancel_subscription(tenant.id, immediate)
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Abonelik bulunamadı"
        )

    AuditLogService(db).log(
        action="subscription.cancel",
        tenant_id=str(tenant.id),
        user_id=str(current_user.id),
        resource_type="subscription",
        resource_id=str(subscription.id),
        payload={"immediate": immediate},
        ip_address=request_meta.client.host if request_meta else None,
        user_agent=request_meta.headers.get("User-Agent") if request_meta else None
    )

    EmailService.send_plan_change_email(
        email=current_user.email,
        full_name=current_user.full_name,
        tenant_name=tenant.name,
        plan_display_name=subscription.plan.display_name if subscription.plan else "Mevcut Plan",
        action="Abonelik iptal edildi"
    )

    return {
        "success": True,
        "message": "Abonelik iptal edildi" if immediate else "Abonelik dönem sonunda iptal edilecek",
        "ends_at": subscription.ends_at.isoformat() if subscription.ends_at else None
    }


@router.get("/check-feature/{feature_key}")
async def check_feature(
    feature_key: str,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
):
    """Check if a feature is enabled for the current plan."""
    service = SubscriptionService(db)
    enabled = service.check_feature(tenant.id, feature_key)
    
    return {
        "feature": feature_key,
        "enabled": enabled
    }
