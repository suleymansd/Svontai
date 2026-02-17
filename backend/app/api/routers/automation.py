"""
Automation settings router for n8n workflow configuration.

Provides endpoints for tenants to manage their n8n automation settings.
"""

import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.user import User
from app.models.tenant import Tenant
from app.models.automation import (
    TenantAutomationSettings,
    AutomationRun,
    AutomationRunStatus
)
from app.core.config import settings
from app.services.audit_log_service import AuditLogService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/automation", tags=["Automation"])


# ===========================================
# Request/Response Models
# ===========================================

class AutomationSettingsResponse(BaseModel):
    """Response model for automation settings."""
    
    id: str
    tenant_id: str
    use_n8n: bool
    default_workflow_id: Optional[str] = None
    whatsapp_workflow_id: Optional[str] = None
    widget_workflow_id: Optional[str] = None
    call_workflow_id: Optional[str] = None
    custom_n8n_url: Optional[str] = None
    enable_auto_retry: bool = True
    max_retries: int = 2
    timeout_seconds: int = 10
    
    # Global settings info
    global_n8n_enabled: bool = False
    
    class Config:
        from_attributes = True


class AutomationSettingsUpdate(BaseModel):
    """Request model for updating automation settings."""
    
    use_n8n: Optional[bool] = None
    default_workflow_id: Optional[str] = None
    whatsapp_workflow_id: Optional[str] = None
    widget_workflow_id: Optional[str] = None
    call_workflow_id: Optional[str] = None
    custom_n8n_url: Optional[str] = None
    enable_auto_retry: Optional[bool] = None
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=60)


class AutomationRunResponse(BaseModel):
    """Response model for automation run."""
    
    id: str
    tenant_id: str
    channel: str
    from_number: str
    to_number: Optional[str]
    message_id: Optional[str]
    message_content: Optional[str]
    n8n_workflow_id: Optional[str]
    n8n_execution_id: Optional[str]
    status: str
    error_message: Optional[str]
    duration_ms: Optional[int]
    retry_count: int
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class TestEventRequest(BaseModel):
    """Request to send a test event to n8n."""
    
    test_message: str = "Bu bir test mesajıdır / This is a test message"


class TestEventResponse(BaseModel):
    """Response from test event."""
    
    success: bool
    run_id: Optional[str] = None
    message: str


# ===========================================
# Endpoints
# ===========================================

@router.get("/settings", response_model=AutomationSettingsResponse)
async def get_automation_settings(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["automations:read"]))
):
    """
    Get automation settings for current tenant.
    
    Returns the tenant's n8n automation configuration including
    workflow IDs and feature flags.
    """
    tenant_id = str(current_tenant.id)
    
    # Get or create settings
    automation_settings = db.query(TenantAutomationSettings).filter(
        TenantAutomationSettings.tenant_id == tenant_id
    ).first()
    
    if not automation_settings:
        # Create default settings
        automation_settings = TenantAutomationSettings(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            use_n8n=False
        )
        db.add(automation_settings)
        db.commit()
        db.refresh(automation_settings)
    
    response = AutomationSettingsResponse(
        id=str(automation_settings.id),
        tenant_id=str(automation_settings.tenant_id),
        use_n8n=automation_settings.use_n8n,
        default_workflow_id=automation_settings.default_workflow_id,
        whatsapp_workflow_id=automation_settings.whatsapp_workflow_id,
        widget_workflow_id=automation_settings.widget_workflow_id,
        call_workflow_id=getattr(automation_settings, "call_workflow_id", None),
        custom_n8n_url=automation_settings.custom_n8n_url,
        enable_auto_retry=automation_settings.enable_auto_retry,
        max_retries=automation_settings.max_retries,
        timeout_seconds=automation_settings.timeout_seconds,
        global_n8n_enabled=settings.USE_N8N
    )
    
    return response


@router.put("/settings", response_model=AutomationSettingsResponse)
async def update_automation_settings(
    update_data: AutomationSettingsUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["automations:manage"]))
):
    """
    Update automation settings for current tenant.
    
    Allows tenants to enable/disable n8n and configure workflow IDs.
    """
    tenant_id = str(current_tenant.id)
    
    # Get or create settings
    automation_settings = db.query(TenantAutomationSettings).filter(
        TenantAutomationSettings.tenant_id == tenant_id
    ).first()
    
    if not automation_settings:
        automation_settings = TenantAutomationSettings(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            use_n8n=False
        )
        db.add(automation_settings)
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(automation_settings, field, value)
    
    db.commit()
    db.refresh(automation_settings)
    
    logger.info(f"Updated automation settings for tenant {tenant_id}")

    AuditLogService(db).log(
        action="automation.settings.update",
        tenant_id=tenant_id,
        user_id=str(current_user.id),
        resource_type="automation_settings",
        resource_id=str(automation_settings.id),
        payload=update_dict,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    
    response = AutomationSettingsResponse(
        id=str(automation_settings.id),
        tenant_id=str(automation_settings.tenant_id),
        use_n8n=automation_settings.use_n8n,
        default_workflow_id=automation_settings.default_workflow_id,
        whatsapp_workflow_id=automation_settings.whatsapp_workflow_id,
        widget_workflow_id=automation_settings.widget_workflow_id,
        call_workflow_id=getattr(automation_settings, "call_workflow_id", None),
        custom_n8n_url=automation_settings.custom_n8n_url,
        enable_auto_retry=automation_settings.enable_auto_retry,
        max_retries=automation_settings.max_retries,
        timeout_seconds=automation_settings.timeout_seconds,
        global_n8n_enabled=settings.USE_N8N
    )
    
    return response


@router.get("/runs", response_model=List[AutomationRunResponse])
async def list_automation_runs(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["automations:read"]))
):
    """
    List automation runs for current tenant.
    
    Shows history of n8n workflow executions.
    """
    tenant_id = str(current_tenant.id)
    
    query = db.query(AutomationRun).filter(
        AutomationRun.tenant_id == tenant_id
    )
    
    if status_filter:
        query = query.filter(AutomationRun.status == status_filter)
    
    runs = query.order_by(AutomationRun.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        AutomationRunResponse(
            id=str(run.id),
            tenant_id=str(run.tenant_id),
            channel=run.channel,
            from_number=run.from_number,
            to_number=run.to_number,
            message_id=run.message_id,
            message_content=run.message_content[:100] if run.message_content else None,
            n8n_workflow_id=run.n8n_workflow_id,
            n8n_execution_id=run.n8n_execution_id,
            status=run.status,
            error_message=run.error_message,
            duration_ms=run.duration_ms,
            retry_count=run.retry_count,
            created_at=run.created_at.isoformat(),
            updated_at=run.updated_at.isoformat()
        )
        for run in runs
    ]


@router.post("/test", response_model=TestEventResponse)
async def send_test_event(
    request: TestEventRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    request_meta: Request = None,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permissions(["automations:manage"]))
):
    """
    Send a test event to n8n.
    
    Useful for testing workflow configuration before going live.
    """
    from app.services.n8n_client import get_n8n_client
    
    tenant_id = current_tenant.id
    
    # Check if n8n is enabled
    if not settings.USE_N8N:
        return TestEventResponse(
            success=False,
            message="n8n workflow engine is not enabled globally (USE_N8N=false)"
        )
    
    n8n_client = get_n8n_client(db)
    
    if not n8n_client.should_use_n8n(tenant_id):
        return TestEventResponse(
            success=False,
            message="n8n is not enabled for this tenant. Enable it in automation settings."
        )
    
    # Send test event
    try:
        run = await n8n_client.trigger_incoming_message(
            tenant_id=tenant_id,
            from_number="+90555TEST001",
            to_number="+90555TEST000",
            text=request.test_message,
            message_id=f"test-{uuid.uuid4()}",
            timestamp="",
            channel="whatsapp",
            correlation_id=str(uuid.uuid4()),
            contact_name="Test User",
            extra_data={"is_test": True}
        )
        
        if run:
            AuditLogService(db).log(
                action="automation.test_event",
                tenant_id=str(current_tenant.id),
                user_id=str(current_user.id),
                resource_type="automation_run",
                resource_id=str(run.id),
                payload={"test_message": request.test_message},
                ip_address=request_meta.client.host if request_meta else None,
                user_agent=request_meta.headers.get("User-Agent") if request_meta else None
            )
            return TestEventResponse(
                success=True,
                run_id=str(run.id),
                message=f"Test event sent successfully. Run ID: {run.id}, Status: {run.status}"
            )
        else:
            return TestEventResponse(
                success=False,
                message="No workflow configured for this tenant/channel"
            )
    
    except Exception as e:
        logger.error(f"Test event failed: {e}", exc_info=True)
        return TestEventResponse(
            success=False,
            message=f"Test event failed: {str(e)}"
        )


@router.get("/status")
async def get_automation_status(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["automations:read"]))
):
    """
    Get overall automation status.
    
    Returns summary of n8n configuration and recent run statistics.
    """
    tenant_id = str(current_tenant.id)
    
    # Get settings
    automation_settings = db.query(TenantAutomationSettings).filter(
        TenantAutomationSettings.tenant_id == tenant_id
    ).first()
    
    # Count recent runs
    from datetime import datetime, timedelta
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    
    total_runs = db.query(AutomationRun).filter(
        AutomationRun.tenant_id == tenant_id,
        AutomationRun.created_at >= one_day_ago
    ).count()
    
    successful_runs = db.query(AutomationRun).filter(
        AutomationRun.tenant_id == tenant_id,
        AutomationRun.created_at >= one_day_ago,
        AutomationRun.status == AutomationRunStatus.SUCCESS.value
    ).count()
    
    failed_runs = db.query(AutomationRun).filter(
        AutomationRun.tenant_id == tenant_id,
        AutomationRun.created_at >= one_day_ago,
        AutomationRun.status == AutomationRunStatus.FAILED.value
    ).count()
    
    return {
        "global_enabled": settings.USE_N8N,
        "tenant_enabled": automation_settings.use_n8n if automation_settings else False,
        "is_configured": bool(
            automation_settings and 
            (automation_settings.default_workflow_id or automation_settings.whatsapp_workflow_id)
        ),
        "n8n_url": settings.N8N_BASE_URL,
        "stats_24h": {
            "total": total_runs,
            "successful": successful_runs,
            "failed": failed_runs,
            "success_rate": round(successful_runs / total_runs * 100, 1) if total_runs > 0 else 0
        }
    }
