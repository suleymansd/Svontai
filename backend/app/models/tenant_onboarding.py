"""
Tenant Onboarding model for tracking setup progress.
"""

import uuid
from datetime import datetime
from app.core.time import utc_now_naive
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OnboardingStepKey(str, Enum):
    """Onboarding step keys."""
    CREATE_TENANT = "create_tenant"
    BUSINESS_PROFILE = "business_profile"
    CUSTOMER_GOALS = "customer_goals"
    KNOWLEDGE_SOURCES = "knowledge_sources"
    CONNECT_WHATSAPP = "connect_whatsapp"
    AUTOPILOT_SETUP = "autopilot_setup"
    REVIEW_READY = "review_ready"


ONBOARDING_STEPS_CONFIG = [
    {
        "key": OnboardingStepKey.CREATE_TENANT.value,
        "title": "Hesap oluşturuldu",
        "description": "SmartWA çalışma alanınız hazırlandı",
        "order": 1,
        "required": True
    },
    {
        "key": OnboardingStepKey.BUSINESS_PROFILE.value,
        "title": "İşletmeyi tanıyalım",
        "description": "Sektör, ton ve müşteri amacını belirleyin",
        "order": 2,
        "required": True
    },
    {
        "key": OnboardingStepKey.CUSTOMER_GOALS.value,
        "title": "Müşteri akışını seçin",
        "description": "Müşterilerinizin size en çok neden yazdığını seçin",
        "order": 3,
        "required": True
    },
    {
        "key": OnboardingStepKey.KNOWLEDGE_SOURCES.value,
        "title": "Bilgi kaynakları",
        "description": "Web sitesi, Instagram veya kısa not ekleyin",
        "order": 4,
        "required": False
    },
    {
        "key": OnboardingStepKey.CONNECT_WHATSAPP.value,
        "title": "WhatsApp bağlantısı",
        "description": "Numaranızı bağlayın veya daha sonra tamamlayın",
        "order": 5,
        "required": False
    },
    {
        "key": OnboardingStepKey.AUTOPILOT_SETUP.value,
        "title": "Otonom kurulum",
        "description": "Bot ve sistem ayarları otomatik hazırlanır",
        "order": 6,
        "required": True
    },
    {
        "key": OnboardingStepKey.REVIEW_READY.value,
        "title": "Hazır",
        "description": "Sistemin durumunu kontrol edip panele geçin",
        "order": 7,
        "required": True
    }
]


class TenantOnboarding(Base):
    """Tenant onboarding progress tracking."""
    
    __tablename__ = "tenant_onboarding"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    # Overall status
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    # Steps as JSON for flexibility
    steps: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )
    # Current step
    current_step: Mapped[str] = mapped_column(
        String(50),
        default=OnboardingStepKey.CREATE_TENANT.value,
        nullable=False
    )
    # Dismissed (user skipped onboarding)
    dismissed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False
    )
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="onboarding"
    )
    
    def __repr__(self) -> str:
        return f"<TenantOnboarding {self.tenant_id} - {self.current_step}>"
    
    @classmethod
    def create_default(cls, tenant_id: uuid.UUID) -> "TenantOnboarding":
        """Create default onboarding with initial steps."""
        steps = {}
        for step_config in ONBOARDING_STEPS_CONFIG:
            steps[step_config["key"]] = {
                "completed": False,
                "completed_at": None,
                "title": step_config["title"],
                "description": step_config["description"],
                "order": step_config["order"],
                "required": step_config["required"]
            }
        # Mark create_tenant as completed since tenant exists
        steps[OnboardingStepKey.CREATE_TENANT.value]["completed"] = True
        steps[OnboardingStepKey.CREATE_TENANT.value]["completed_at"] = utc_now_naive().isoformat()
        
        return cls(
            tenant_id=tenant_id,
            steps=steps,
            current_step=OnboardingStepKey.BUSINESS_PROFILE.value
        )
    
    def complete_step(self, step_key: str) -> bool:
        """Mark a step as completed."""
        if step_key in self.steps:
            self.steps[step_key]["completed"] = True
            self.steps[step_key]["completed_at"] = utc_now_naive().isoformat()
            self._update_current_step()
            self._check_completion()
            return True
        return False
    
    def _update_current_step(self):
        """Update current step to next incomplete step."""
        for step_config in sorted(ONBOARDING_STEPS_CONFIG, key=lambda x: x["order"]):
            step_key = step_config["key"]
            if step_key in self.steps and not self.steps[step_key]["completed"]:
                if step_config["required"]:
                    self.current_step = step_key
                    return
        self.current_step = OnboardingStepKey.REVIEW_READY.value
    
    def _check_completion(self):
        """Check if all required steps are completed."""
        for step_config in ONBOARDING_STEPS_CONFIG:
            if step_config["required"]:
                step_key = step_config["key"]
                if step_key in self.steps and not self.steps[step_key]["completed"]:
                    return
        self.is_completed = True
        self.completed_at = utc_now_naive()
    
    def get_progress_percentage(self) -> int:
        """Get completion percentage."""
        total = len([s for s in ONBOARDING_STEPS_CONFIG if s["required"]])
        completed = len([
            k for k, v in self.steps.items() 
            if v.get("completed") and any(s["key"] == k and s["required"] for s in ONBOARDING_STEPS_CONFIG)
        ])
        return int((completed / total) * 100) if total > 0 else 0
