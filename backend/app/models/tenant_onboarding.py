"""
Tenant Onboarding model for tracking setup progress.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OnboardingStepKey(str, Enum):
    """Onboarding step keys."""
    CREATE_TENANT = "create_tenant"
    CREATE_BOT = "create_bot"
    ADD_WELCOME_MESSAGE = "add_welcome_message"
    ADD_KNOWLEDGE = "add_knowledge"
    CONNECT_WHATSAPP = "connect_whatsapp"
    ACTIVATE_BOT = "activate_bot"


ONBOARDING_STEPS_CONFIG = [
    {
        "key": OnboardingStepKey.CREATE_TENANT.value,
        "title": "İşletme Oluştur",
        "description": "İşletmenizi kaydedin",
        "order": 1,
        "required": True
    },
    {
        "key": OnboardingStepKey.CREATE_BOT.value,
        "title": "İlk Botunuzu Oluşturun",
        "description": "AI asistanınıza bir isim verin",
        "order": 2,
        "required": True
    },
    {
        "key": OnboardingStepKey.ADD_WELCOME_MESSAGE.value,
        "title": "Karşılama Mesajı Ekleyin",
        "description": "Müşterilerinizi nasıl karşılayacağınızı belirleyin",
        "order": 3,
        "required": True
    },
    {
        "key": OnboardingStepKey.ADD_KNOWLEDGE.value,
        "title": "Bilgi Tabanı Oluşturun",
        "description": "Botunuzun cevaplayacağı bilgileri ekleyin",
        "order": 4,
        "required": True
    },
    {
        "key": OnboardingStepKey.CONNECT_WHATSAPP.value,
        "title": "WhatsApp Bağlayın",
        "description": "WhatsApp Business hesabınızı bağlayın (opsiyonel)",
        "order": 5,
        "required": False
    },
    {
        "key": OnboardingStepKey.ACTIVATE_BOT.value,
        "title": "Botu Aktif Edin",
        "description": "Botunuzu yayına alın",
        "order": 6,
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
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
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
        steps[OnboardingStepKey.CREATE_TENANT.value]["completed_at"] = datetime.utcnow().isoformat()
        
        return cls(
            tenant_id=tenant_id,
            steps=steps,
            current_step=OnboardingStepKey.CREATE_BOT.value
        )
    
    def complete_step(self, step_key: str) -> bool:
        """Mark a step as completed."""
        if step_key in self.steps:
            self.steps[step_key]["completed"] = True
            self.steps[step_key]["completed_at"] = datetime.utcnow().isoformat()
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
        self.current_step = OnboardingStepKey.ACTIVATE_BOT.value
    
    def _check_completion(self):
        """Check if all required steps are completed."""
        for step_config in ONBOARDING_STEPS_CONFIG:
            if step_config["required"]:
                step_key = step_config["key"]
                if step_key in self.steps and not self.steps[step_key]["completed"]:
                    return
        self.is_completed = True
        self.completed_at = datetime.utcnow()
    
    def get_progress_percentage(self) -> int:
        """Get completion percentage."""
        total = len([s for s in ONBOARDING_STEPS_CONFIG if s["required"]])
        completed = len([
            k for k, v in self.steps.items() 
            if v.get("completed") and any(s["key"] == k and s["required"] for s in ONBOARDING_STEPS_CONFIG)
        ])
        return int((completed / total) * 100) if total > 0 else 0

