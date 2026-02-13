"""
Automation models for n8n workflow integration.

These models track automation runs and tenant-specific automation settings
for the n8n workflow engine integration.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, JSON, Boolean, Text, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AutomationRunStatus(str, Enum):
    """Status of an automation run."""
    RECEIVED = "received"      # Event received, queued for processing
    RUNNING = "running"        # Currently being processed by n8n
    SUCCESS = "success"        # Completed successfully
    FAILED = "failed"          # Failed with error
    TIMEOUT = "timeout"        # Timed out waiting for n8n
    SKIPPED = "skipped"        # Skipped (e.g., AI paused, feature flag off)


class AutomationChannel(str, Enum):
    """Supported automation channels."""
    WHATSAPP = "whatsapp"
    WEB_WIDGET = "web_widget"


class AutomationRun(Base):
    """
    Tracks individual automation executions.
    
    Each time a message triggers an n8n workflow, a record is created here
    to track the execution status and results.
    """
    
    __tablename__ = "automation_runs"
    __table_args__ = (
        Index("ix_automation_runs_tenant_created", "tenant_id", "created_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    # Tenant association
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Channel info
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AutomationChannel.WHATSAPP.value
    )
    
    # Message details
    from_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    to_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    message_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    message_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # n8n execution info
    n8n_workflow_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    n8n_execution_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    
    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AutomationRunStatus.RECEIVED.value,
        index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Correlation
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )
    
    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Request/Response tracking
    request_payload: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )
    response_payload: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    
    # Metadata
    extra_data: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
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
        back_populates="automation_runs"
    )
    
    def __repr__(self) -> str:
        return f"<AutomationRun {self.id} status={self.status}>"
    
    def mark_running(self, n8n_execution_id: Optional[str] = None):
        """Mark the run as currently executing."""
        self.status = AutomationRunStatus.RUNNING.value
        self.started_at = datetime.utcnow()
        if n8n_execution_id:
            self.n8n_execution_id = n8n_execution_id
        self.updated_at = datetime.utcnow()
    
    def mark_success(self, response_payload: Optional[dict] = None):
        """Mark the run as successful."""
        self.status = AutomationRunStatus.SUCCESS.value
        self.completed_at = datetime.utcnow()
        if self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        if response_payload:
            self.response_payload = response_payload
        self.updated_at = datetime.utcnow()
    
    def mark_failed(self, error_message: str, response_payload: Optional[dict] = None):
        """Mark the run as failed."""
        self.status = AutomationRunStatus.FAILED.value
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        if self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        if response_payload:
            self.response_payload = response_payload
        self.updated_at = datetime.utcnow()
    
    def mark_timeout(self):
        """Mark the run as timed out."""
        self.status = AutomationRunStatus.TIMEOUT.value
        self.completed_at = datetime.utcnow()
        self.error_message = "Request timed out waiting for n8n response"
        if self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        self.updated_at = datetime.utcnow()


class TenantAutomationSettings(Base):
    """
    Tenant-specific automation settings.
    
    Controls whether a tenant uses n8n for workflow automation
    and stores their default workflow configuration.
    """
    
    __tablename__ = "tenant_automation_settings"
    
    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    # Tenant association (one-to-one)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    
    # n8n enablement (per-tenant override of global USE_N8N flag)
    use_n8n: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    # Default workflow for incoming messages
    default_workflow_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # WhatsApp-specific workflow
    whatsapp_workflow_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Web widget-specific workflow
    widget_workflow_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Custom n8n webhook URL (if tenant has own n8n instance)
    custom_n8n_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Custom shared secret (per-tenant security)
    custom_shared_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Feature flags
    enable_auto_retry: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10
    )
    
    # Metadata
    extra_settings: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
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
        back_populates="automation_settings"
    )
    
    def __repr__(self) -> str:
        return f"<TenantAutomationSettings tenant_id={self.tenant_id} use_n8n={self.use_n8n}>"
    
    def get_workflow_id(self, channel: str) -> Optional[str]:
        """Get the workflow ID for a specific channel."""
        if channel == AutomationChannel.WHATSAPP.value and self.whatsapp_workflow_id:
            return self.whatsapp_workflow_id
        if channel == AutomationChannel.WEB_WIDGET.value and self.widget_workflow_id:
            return self.widget_workflow_id
        return self.default_workflow_id
