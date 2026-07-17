"""
Tenant onboarding service for managing setup wizard progress.
"""

import uuid
import copy
from datetime import datetime
from app.core.time import utc_now_naive
from typing import Optional

from sqlalchemy.orm import Session

from app.models.tenant_onboarding import TenantOnboarding, OnboardingStepKey, ONBOARDING_STEPS_CONFIG
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.knowledge import BotKnowledgeItem
from app.models.whatsapp_account import WhatsAppAccount
from app.models.user import User
from app.services.autopilot_service import AutopilotService


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
        else:
            self._normalize_steps(onboarding)
        
        return onboarding

    def _normalize_steps(self, onboarding: TenantOnboarding) -> None:
        """Keep older onboarding JSON rows compatible with the current staged flow."""
        changed = False
        steps = dict(onboarding.steps or {})
        for step_config in ONBOARDING_STEPS_CONFIG:
            step_key = step_config["key"]
            if step_key not in steps:
                steps[step_key] = {
                    "completed": step_key == OnboardingStepKey.CREATE_TENANT.value,
                    "completed_at": utc_now_naive().isoformat() if step_key == OnboardingStepKey.CREATE_TENANT.value else None,
                    "title": step_config["title"],
                    "description": step_config["description"],
                    "order": step_config["order"],
                    "required": step_config["required"],
                }
                changed = True
            else:
                for field in ("title", "description", "order", "required"):
                    if steps[step_key].get(field) != step_config[field]:
                        steps[step_key][field] = step_config[field]
                        changed = True

        valid_keys = {step["key"] for step in ONBOARDING_STEPS_CONFIG}
        for old_key in list(steps.keys()):
            if old_key not in valid_keys:
                steps.pop(old_key)
                changed = True

        if onboarding.current_step not in valid_keys:
            onboarding.current_step = OnboardingStepKey.BUSINESS_PROFILE.value
            changed = True

        if changed:
            onboarding.steps = steps
            self._update_current_step(onboarding)
            self._check_completion(onboarding)
            self.db.commit()
    
    def get_onboarding_status(self, tenant_id: uuid.UUID) -> dict:
        """Get full onboarding status for frontend."""
        onboarding = self.get_or_create_onboarding(tenant_id)
        tenant = self.db.get(Tenant, tenant_id)
        tenant_settings = dict((tenant.settings if tenant else {}) or {})
        concierge = dict(tenant_settings.get("concierge_enrichment") or {})
        business_profile = dict(tenant_settings.get("business_profile") or {})
        
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
            "setup_mode": tenant_settings.get("setup_mode", "concierge"),
            "concierge_status": concierge.get("status"),
            "business_profile_status": business_profile.get("status"),
            "steps": steps
        }
    
    def complete_step(self, tenant_id: uuid.UUID, step_key: str) -> dict:
        """Mark a step as completed."""
        onboarding = self.get_or_create_onboarding(tenant_id)
        
        if step_key in onboarding.steps:
            # Copy steps dict for modification (SQLAlchemy JSON tracking)
            steps = copy.deepcopy(onboarding.steps or {})
            steps[step_key]["completed"] = True
            steps[step_key]["completed_at"] = utc_now_naive().isoformat()
            onboarding.steps = steps
            
            # Update current step
            self._update_current_step(onboarding)
            
            # Check if all required steps are done
            self._check_completion(onboarding)
            
            self.db.commit()
        
        return self.get_onboarding_status(tenant_id)

    def save_business_profile(self, tenant: Tenant, payload: dict) -> dict:
        """Persist staged onboarding answers into tenant settings."""
        onboarding = self.get_or_create_onboarding(tenant.id)
        settings = dict(tenant.settings or {})
        profile = dict(settings.get("business_profile") or {})
        concierge = dict(settings.get("concierge_enrichment") or {})
        onboarding_answers = {
            "setup_mode": payload.get("setup_mode") if payload.get("setup_mode") in {"self_serve", "concierge"} else "self_serve",
            "industry": payload.get("industry") or "unknown",
            "primary_goal": payload.get("primary_goal") or "",
            "tone": payload.get("tone") or "professional",
            "handoff_rules": payload.get("handoff_rules") or [],
            "website_url": payload.get("website_url") or "",
            "instagram_url": payload.get("instagram_url") or "",
            "business_summary": payload.get("business_summary") or "",
            "source": "customer_onboarding",
            "updated_at": utc_now_naive().isoformat(),
        }
        setup_mode = onboarding_answers["setup_mode"]
        settings["setup_mode"] = setup_mode
        settings["onboarding_answers"] = onboarding_answers
        settings["business_profile"] = {
            **profile,
            "status": "customer_collected" if setup_mode == "self_serve" else "needs_enrichment",
            "source": "customer_onboarding",
            "business_name": tenant.name,
            "industry": onboarding_answers["industry"],
            "tone": onboarding_answers["tone"],
            "summary": onboarding_answers["business_summary"],
            "services": profile.get("services") or [],
            "faq": profile.get("faq") or [],
            "updated_at": onboarding_answers["updated_at"],
        }
        settings["concierge_enrichment"] = {
            **concierge,
            "status": "pending" if setup_mode == "concierge" else concierge.get("status") or "pending",
            "source": "customer_onboarding",
            "setup_mode": setup_mode,
            "updated_at": utc_now_naive().isoformat(),
        }
        tenant.settings = settings
        self.db.commit()

        self.complete_step(tenant.id, OnboardingStepKey.BUSINESS_PROFILE.value)
        self.complete_step(tenant.id, OnboardingStepKey.CUSTOMER_GOALS.value)
        self.complete_step(tenant.id, OnboardingStepKey.KNOWLEDGE_SOURCES.value)
        # Start preparing the tenant immediately. The final onboarding action
        # remains an idempotent readiness check, not a manual bot creation step.
        AutopilotService(self.db).run(tenant)
        return self.get_onboarding_status(tenant.id)

    def run_autopilot_setup(self, tenant: Tenant, user: User) -> dict:
        """Run the autonomous setup and update onboarding progress."""
        AutopilotService(self.db).run(tenant, user)
        self.complete_step(tenant.id, OnboardingStepKey.AUTOPILOT_SETUP.value)
        account = self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant.id,
            WhatsAppAccount.is_active == True,
        ).first()
        if account:
            self.complete_step(tenant.id, OnboardingStepKey.CONNECT_WHATSAPP.value)
        self.complete_step(tenant.id, OnboardingStepKey.REVIEW_READY.value)
        return self.get_onboarding_status(tenant.id)
    
    def _update_current_step(self, onboarding: TenantOnboarding):
        """Update current step to next incomplete required step."""
        for config in sorted(ONBOARDING_STEPS_CONFIG, key=lambda x: x["order"]):
            step_key = config["key"]
            step_data = onboarding.steps.get(step_key, {})
            
            if config["required"] and not step_data.get("completed", False):
                onboarding.current_step = step_key
                return
        
        # All required steps completed
        onboarding.current_step = OnboardingStepKey.REVIEW_READY.value
    
    def _check_completion(self, onboarding: TenantOnboarding):
        """Check if all required steps are completed."""
        for config in ONBOARDING_STEPS_CONFIG:
            if config["required"]:
                step_data = onboarding.steps.get(config["key"], {})
                if not step_data.get("completed", False):
                    return
        
        onboarding.is_completed = True
        onboarding.completed_at = utc_now_naive()
    
    def dismiss_onboarding(self, tenant_id: uuid.UUID) -> dict:
        """Dismiss the onboarding wizard."""
        onboarding = self.get_or_create_onboarding(tenant_id)
        onboarding.dismissed = True
        onboarding.dismissed_at = utc_now_naive()
        self.db.commit()
        
        return self.get_onboarding_status(tenant_id)
    
    def auto_check_progress(self, tenant_id: uuid.UUID) -> dict:
        """
        Automatically check and update onboarding progress based on tenant state.
        Called after certain actions to keep onboarding in sync.
        """
        onboarding = self.get_or_create_onboarding(tenant_id)
        
        account = self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant_id,
            WhatsAppAccount.is_active == True,
        ).first()
        if account and not onboarding.steps.get(OnboardingStepKey.CONNECT_WHATSAPP.value, {}).get("completed"):
            self.complete_step(tenant_id, OnboardingStepKey.CONNECT_WHATSAPP.value)

        if (onboarding.steps or {}).get(OnboardingStepKey.AUTOPILOT_SETUP.value, {}).get("completed"):
            return self.get_onboarding_status(tenant_id)

        # Compatibility for tenants already initialized by autopilot.
        bot_count = self.db.query(Bot).filter(Bot.tenant_id == tenant_id).count()
        knowledge_count = self.db.query(BotKnowledgeItem).join(Bot).filter(Bot.tenant_id == tenant_id).count()
        if bot_count > 0 and knowledge_count > 0:
            self.complete_step(tenant_id, OnboardingStepKey.AUTOPILOT_SETUP.value)
        
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
            OnboardingStepKey.BUSINESS_PROFILE.value: {
                "action": "business_profile",
                "message": "İşletmenizi birkaç kısa soruyla tanıyalım",
                "url": "/dashboard/onboarding"
            },
            OnboardingStepKey.CUSTOMER_GOALS.value: {
                "action": "customer_goals",
                "message": "Müşteri akışınızı seçin",
                "url": "/dashboard/onboarding"
            },
            OnboardingStepKey.KNOWLEDGE_SOURCES.value: {
                "action": "knowledge_sources",
                "message": "Bilgi kaynaklarınızı ekleyin",
                "url": "/dashboard/onboarding"
            },
            OnboardingStepKey.CONNECT_WHATSAPP.value: {
                "action": "connect_whatsapp",
                "message": "WhatsApp hesabınızı bağlayın",
                "url": "/dashboard/onboarding"
            },
            OnboardingStepKey.AUTOPILOT_SETUP.value: {
                "action": "autopilot_setup",
                "message": "SmartWA sistemi sizin için kursun",
                "url": "/dashboard/onboarding"
            },
            OnboardingStepKey.REVIEW_READY.value: {
                "action": "review_ready",
                "message": "Kurulumu kontrol edin ve panele geçin",
                "url": "/dashboard/onboarding"
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
