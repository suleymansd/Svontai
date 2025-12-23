"""
Tenant onboarding service for managing setup wizard progress.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.tenant_onboarding import TenantOnboarding, OnboardingStepKey, ONBOARDING_STEPS_CONFIG
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.knowledge import BotKnowledgeItem


class TenantOnboardingService:
    """Service for managing tenant onboarding progress."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_onboarding(self, tenant_id: uuid.UUID) -> TenantOnboarding:
        """Get or create onboarding progress for tenant."""
        onboarding = self.db.query(TenantOnboarding).filter(
            TenantOnboarding.tenant_id == tenant_id
        ).first()
        
        if not onboarding:
            onboarding = TenantOnboarding.create_default(tenant_id)
            self.db.add(onboarding)
            self.db.commit()
            self.db.refresh(onboarding)
        
        return onboarding
    
    def get_onboarding_status(self, tenant_id: uuid.UUID) -> dict:
        """Get full onboarding status for frontend."""
        onboarding = self.get_or_create_onboarding(tenant_id)
        
        # Build steps list with current state
        steps = []
        for config in sorted(ONBOARDING_STEPS_CONFIG, key=lambda x: x["order"]):
            step_key = config["key"]
            step_data = onboarding.steps.get(step_key, {})
            
            steps.append({
                "key": step_key,
                "title": config["title"],
                "description": config["description"],
                "order": config["order"],
                "required": config["required"],
                "completed": step_data.get("completed", False),
                "completed_at": step_data.get("completed_at"),
                "is_current": onboarding.current_step == step_key
            })
        
        return {
            "is_completed": onboarding.is_completed,
            "completed_at": onboarding.completed_at.isoformat() if onboarding.completed_at else None,
            "current_step": onboarding.current_step,
            "progress_percentage": onboarding.get_progress_percentage(),
            "dismissed": onboarding.dismissed,
            "steps": steps
        }
    
    def complete_step(self, tenant_id: uuid.UUID, step_key: str) -> dict:
        """Mark a step as completed."""
        onboarding = self.get_or_create_onboarding(tenant_id)
        
        if step_key in onboarding.steps:
            # Copy steps dict for modification (SQLAlchemy JSON tracking)
            steps = dict(onboarding.steps)
            steps[step_key]["completed"] = True
            steps[step_key]["completed_at"] = datetime.utcnow().isoformat()
            onboarding.steps = steps
            
            # Update current step
            self._update_current_step(onboarding)
            
            # Check if all required steps are done
            self._check_completion(onboarding)
            
            self.db.commit()
        
        return self.get_onboarding_status(tenant_id)
    
    def _update_current_step(self, onboarding: TenantOnboarding):
        """Update current step to next incomplete required step."""
        for config in sorted(ONBOARDING_STEPS_CONFIG, key=lambda x: x["order"]):
            step_key = config["key"]
            step_data = onboarding.steps.get(step_key, {})
            
            if config["required"] and not step_data.get("completed", False):
                onboarding.current_step = step_key
                return
        
        # All required steps completed
        onboarding.current_step = OnboardingStepKey.ACTIVATE_BOT.value
    
    def _check_completion(self, onboarding: TenantOnboarding):
        """Check if all required steps are completed."""
        for config in ONBOARDING_STEPS_CONFIG:
            if config["required"]:
                step_data = onboarding.steps.get(config["key"], {})
                if not step_data.get("completed", False):
                    return
        
        onboarding.is_completed = True
        onboarding.completed_at = datetime.utcnow()
    
    def dismiss_onboarding(self, tenant_id: uuid.UUID) -> dict:
        """Dismiss the onboarding wizard."""
        onboarding = self.get_or_create_onboarding(tenant_id)
        onboarding.dismissed = True
        onboarding.dismissed_at = datetime.utcnow()
        self.db.commit()
        
        return self.get_onboarding_status(tenant_id)
    
    def auto_check_progress(self, tenant_id: uuid.UUID) -> dict:
        """
        Automatically check and update onboarding progress based on tenant state.
        Called after certain actions to keep onboarding in sync.
        """
        onboarding = self.get_or_create_onboarding(tenant_id)
        
        # Check CREATE_BOT
        bot_count = self.db.query(Bot).filter(Bot.tenant_id == tenant_id).count()
        if bot_count > 0 and not onboarding.steps.get(OnboardingStepKey.CREATE_BOT.value, {}).get("completed"):
            self.complete_step(tenant_id, OnboardingStepKey.CREATE_BOT.value)
        
        # Check ADD_WELCOME_MESSAGE - consider done if bot has non-default welcome message
        first_bot = self.db.query(Bot).filter(Bot.tenant_id == tenant_id).first()
        if first_bot and first_bot.welcome_message != "Merhaba! Size nasıl yardımcı olabilirim?":
            if not onboarding.steps.get(OnboardingStepKey.ADD_WELCOME_MESSAGE.value, {}).get("completed"):
                self.complete_step(tenant_id, OnboardingStepKey.ADD_WELCOME_MESSAGE.value)
        
        # Check ADD_KNOWLEDGE
        if first_bot:
            knowledge_count = self.db.query(BotKnowledgeItem).filter(
                BotKnowledgeItem.bot_id == first_bot.id
            ).count()
            if knowledge_count > 0:
                if not onboarding.steps.get(OnboardingStepKey.ADD_KNOWLEDGE.value, {}).get("completed"):
                    self.complete_step(tenant_id, OnboardingStepKey.ADD_KNOWLEDGE.value)
        
        # Check ACTIVATE_BOT
        if first_bot and first_bot.is_active:
            if not onboarding.steps.get(OnboardingStepKey.ACTIVATE_BOT.value, {}).get("completed"):
                self.complete_step(tenant_id, OnboardingStepKey.ACTIVATE_BOT.value)
        
        return self.get_onboarding_status(tenant_id)
    
    def get_next_action(self, tenant_id: uuid.UUID) -> dict:
        """Get the next recommended action for the user."""
        onboarding = self.get_or_create_onboarding(tenant_id)
        
        if onboarding.is_completed or onboarding.dismissed:
            return {
                "action": None,
                "message": "Kurulum tamamlandı!",
                "url": "/dashboard"
            }
        
        actions = {
            OnboardingStepKey.CREATE_TENANT.value: {
                "action": "create_tenant",
                "message": "İşletmenizi oluşturun",
                "url": "/dashboard/settings"
            },
            OnboardingStepKey.CREATE_BOT.value: {
                "action": "create_bot",
                "message": "İlk botunuzu oluşturun",
                "url": "/dashboard/bots"
            },
            OnboardingStepKey.ADD_WELCOME_MESSAGE.value: {
                "action": "add_welcome",
                "message": "Karşılama mesajınızı ayarlayın",
                "url": "/dashboard/bots"
            },
            OnboardingStepKey.ADD_KNOWLEDGE.value: {
                "action": "add_knowledge",
                "message": "Bilgi tabanınızı oluşturun",
                "url": "/dashboard/bots"
            },
            OnboardingStepKey.CONNECT_WHATSAPP.value: {
                "action": "connect_whatsapp",
                "message": "WhatsApp hesabınızı bağlayın",
                "url": "/dashboard/setup/whatsapp"
            },
            OnboardingStepKey.ACTIVATE_BOT.value: {
                "action": "activate_bot",
                "message": "Botunuzu aktif edin",
                "url": "/dashboard/bots"
            }
        }
        
        return actions.get(onboarding.current_step, {
            "action": None,
            "message": "Devam edin",
            "url": "/dashboard"
        })


def get_tenant_onboarding_service(db: Session) -> TenantOnboardingService:
    """Get tenant onboarding service instance."""
    return TenantOnboardingService(db)

