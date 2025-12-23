"""
Onboarding steps model for tracking setup progress.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OnboardingProvider(str, Enum):
    """Onboarding provider types."""
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    MESSENGER = "messenger"


class StepStatus(str, Enum):
    """Step status enum."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ERROR = "error"
    SKIPPED = "skipped"


class OnboardingStep(Base):
    """Onboarding step tracking for multi-step setup flows."""
    
    __tablename__ = "onboarding_steps"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    provider: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Integration provider (whatsapp, instagram, etc.)"
    )
    step_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Unique step identifier"
    )
    step_order: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )
    step_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    step_description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default=StepStatus.PENDING.value,
        nullable=False
    )
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Status message or error details"
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional step metadata"
    )
    
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    
    def __repr__(self) -> str:
        return f"<OnboardingStep {self.provider}:{self.step_key} - {self.status}>"


class AuditLog(Base):
    """Audit log for tracking important actions."""
    
    __tablename__ = "audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    
    payload_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog {self.action} at {self.created_at}>"


# WhatsApp Onboarding Step Keys
WHATSAPP_ONBOARDING_STEPS = [
    {
        "step_key": "start_setup",
        "step_order": 1,
        "step_name": "Kurulumu Başlat",
        "step_name_en": "Start Setup",
        "step_description": "WhatsApp bağlantısı başlatıldı"
    },
    {
        "step_key": "meta_auth",
        "step_order": 2,
        "step_name": "Meta ile Bağlan",
        "step_name_en": "Connect with Meta",
        "step_description": "Facebook/Meta hesabınızla giriş yapın"
    },
    {
        "step_key": "select_waba",
        "step_order": 3,
        "step_name": "WhatsApp Business Seç",
        "step_name_en": "Select WhatsApp Business",
        "step_description": "WhatsApp Business hesabınızı ve numaranızı seçin"
    },
    {
        "step_key": "save_credentials",
        "step_order": 4,
        "step_name": "Bilgileri Kaydet",
        "step_name_en": "Save Credentials",
        "step_description": "API bilgileri güvenli şekilde kaydediliyor"
    },
    {
        "step_key": "configure_webhook",
        "step_order": 5,
        "step_name": "Webhook Yapılandır",
        "step_name_en": "Configure Webhook",
        "step_description": "Mesaj alma için webhook ayarlanıyor"
    },
    {
        "step_key": "verify_webhook",
        "step_order": 6,
        "step_name": "Webhook Doğrula",
        "step_name_en": "Verify Webhook",
        "step_description": "Meta webhook doğrulaması bekleniyor"
    },
    {
        "step_key": "complete",
        "step_order": 7,
        "step_name": "Tamamlandı",
        "step_name_en": "Complete",
        "step_description": "WhatsApp bağlantısı başarılı!"
    }
]

