"""
Subscription service for managing tenant subscriptions and limits.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.plan import Plan, DEFAULT_PLANS
from app.models.subscription import TenantSubscription, SubscriptionStatus
from app.models.tenant import Tenant


class SubscriptionService:
    """Service for managing subscriptions and enforcing limits."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_free_plan(self) -> Plan:
        """Get or create the free plan."""
        plan = self.db.query(Plan).filter(Plan.name == "free").first()
        if not plan:
            # Create default plans
            for plan_data in DEFAULT_PLANS:
                new_plan = Plan(**plan_data)
                self.db.add(new_plan)
            self.db.commit()
            plan = self.db.query(Plan).filter(Plan.name == "free").first()
        return plan
    
    def create_subscription(
        self,
        tenant_id: uuid.UUID,
        plan_name: str = "free"
    ) -> TenantSubscription:
        """Create a new subscription for a tenant."""
        # Get plan
        plan = self.db.query(Plan).filter(Plan.name == plan_name).first()
        if not plan:
            plan = self.get_or_create_free_plan()
        
        # Check if subscription exists
        existing = self.db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant_id
        ).first()
        
        if existing:
            return existing
        
        # Create subscription
        now = datetime.utcnow()
        trial_ends_at = now + timedelta(days=plan.trial_days) if plan.trial_days > 0 else None
        
        subscription = TenantSubscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status=SubscriptionStatus.TRIAL.value if trial_ends_at else SubscriptionStatus.ACTIVE.value,
            started_at=now,
            trial_ends_at=trial_ends_at,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            usage_reset_at=now
        )
        
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        
        return subscription
    
    def get_subscription(self, tenant_id: uuid.UUID) -> Optional[TenantSubscription]:
        """Get subscription for a tenant."""
        return self.db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant_id
        ).first()
    
    def check_message_limit(self, tenant_id: uuid.UUID) -> tuple[bool, str]:
        """
        Check if tenant can send more messages.
        Returns (can_send, message).
        """
        subscription = self.get_subscription(tenant_id)
        
        if not subscription:
            return False, "Abonelik bulunamadı"
        
        # Check if subscription is active
        if not subscription.is_active():
            if subscription.status == SubscriptionStatus.EXPIRED.value:
                return False, "Aboneliğiniz sona erdi. Lütfen planınızı yenileyin."
            elif subscription.status == SubscriptionStatus.CANCELLED.value:
                return False, "Aboneliğiniz iptal edildi."
            elif subscription.status == SubscriptionStatus.PAST_DUE.value:
                return False, "Ödeme bekleniyor. Lütfen ödemenizi tamamlayın."
            else:
                return False, "Aboneliğiniz aktif değil."
        
        # Check message limit
        plan = subscription.plan
        if subscription.messages_used_this_month >= plan.message_limit:
            return False, f"Aylık mesaj limitinize ({plan.message_limit}) ulaştınız. Planınızı yükseltin."
        
        return True, "OK"
    
    def increment_message_count(self, tenant_id: uuid.UUID) -> bool:
        """Increment message count for tenant."""
        subscription = self.get_subscription(tenant_id)
        if subscription:
            subscription.messages_used_this_month += 1
            self.db.commit()
            return True
        return False
    
    def check_bot_limit(self, tenant_id: uuid.UUID, current_bot_count: int) -> tuple[bool, str]:
        """Check if tenant can create more bots."""
        subscription = self.get_subscription(tenant_id)
        
        if not subscription:
            return False, "Abonelik bulunamadı"
        
        plan = subscription.plan
        if current_bot_count >= plan.bot_limit:
            return False, f"Bot limitinize ({plan.bot_limit}) ulaştınız. Planınızı yükseltin."
        
        return True, "OK"
    
    def check_feature(self, tenant_id: uuid.UUID, feature_key: str) -> bool:
        """Check if a feature is enabled for tenant's plan."""
        subscription = self.get_subscription(tenant_id)
        
        if not subscription:
            return False
        
        plan = subscription.plan
        return plan.feature_flags.get(feature_key, False)
    
    def get_usage_stats(self, tenant_id: uuid.UUID) -> dict:
        """Get current usage statistics for a tenant."""
        subscription = self.get_subscription(tenant_id)
        
        if not subscription:
            return {}
        
        plan = subscription.plan
        
        return {
            "plan_name": plan.display_name,
            "plan_type": plan.plan_type,
            "messages_used": subscription.messages_used_this_month,
            "message_limit": plan.message_limit,
            "messages_remaining": max(0, plan.message_limit - subscription.messages_used_this_month),
            "message_usage_percent": round((subscription.messages_used_this_month / plan.message_limit) * 100, 1) if plan.message_limit > 0 else 0,
            "bot_limit": plan.bot_limit,
            "knowledge_limit": plan.knowledge_items_limit,
            "status": subscription.status,
            "trial_ends_at": subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "features": plan.feature_flags
        }
    
    def upgrade_plan(
        self,
        tenant_id: uuid.UUID,
        new_plan_name: str,
        external_subscription_id: Optional[str] = None
    ) -> TenantSubscription:
        """Upgrade tenant to a new plan."""
        subscription = self.get_subscription(tenant_id)
        new_plan = self.db.query(Plan).filter(Plan.name == new_plan_name).first()
        
        if not new_plan:
            raise ValueError(f"Plan not found: {new_plan_name}")
        
        if subscription:
            subscription.plan_id = new_plan.id
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.external_subscription_id = external_subscription_id
            subscription.current_period_start = datetime.utcnow()
            subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
            subscription.trial_ends_at = None
        else:
            subscription = self.create_subscription(tenant_id, new_plan_name)
        
        self.db.commit()
        return subscription
    
    def cancel_subscription(self, tenant_id: uuid.UUID, immediate: bool = False) -> TenantSubscription:
        """Cancel a subscription."""
        subscription = self.get_subscription(tenant_id)
        
        if subscription:
            subscription.cancelled_at = datetime.utcnow()
            if immediate:
                subscription.status = SubscriptionStatus.CANCELLED.value
                subscription.ends_at = datetime.utcnow()
            else:
                # Will cancel at end of period
                subscription.ends_at = subscription.current_period_end
            
            self.db.commit()
        
        return subscription
    
    def reset_monthly_usage(self, tenant_id: uuid.UUID):
        """Reset monthly usage counters."""
        subscription = self.get_subscription(tenant_id)
        if subscription:
            subscription.messages_used_this_month = 0
            subscription.usage_reset_at = datetime.utcnow()
            self.db.commit()


# Helper function to check limits in middleware
def check_subscription_limit(
    db: Session,
    tenant_id: uuid.UUID,
    limit_type: str = "message"
) -> tuple[bool, str]:
    """
    Check subscription limits.
    
    Args:
        db: Database session
        tenant_id: Tenant UUID
        limit_type: Type of limit to check ('message', 'bot', etc.)
    
    Returns:
        Tuple of (allowed: bool, message: str)
    """
    service = SubscriptionService(db)
    
    if limit_type == "message":
        return service.check_message_limit(tenant_id)
    elif limit_type == "bot":
        # Get current bot count
        from app.models.bot import Bot
        bot_count = db.query(Bot).filter(Bot.tenant_id == tenant_id).count()
        return service.check_bot_limit(tenant_id, bot_count)
    else:
        return True, "OK"

