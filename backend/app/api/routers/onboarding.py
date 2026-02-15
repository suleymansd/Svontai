"""
Onboarding API router for WhatsApp setup flow.
"""

import json
from uuid import UUID
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.user import User
from app.models.tenant import Tenant
from app.services.onboarding_service import OnboardingService
from app.services.meta_api import MetaAPIError, meta_api_service
from app.services.system_event_service import SystemEventService


router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


# Pydantic schemas
class OnboardingStartResponse(BaseModel):
    """Response for starting onboarding."""
    oauth_url: str
    embedded_config: dict
    verify_token: str
    state: str
    webhook_url: str


class OnboardingStepResponse(BaseModel):
    """Response for a single onboarding step."""
    step_key: str
    step_order: int
    step_name: str
    step_description: Optional[str]
    status: str
    message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: datetime

    class Config:
        from_attributes = True


class OnboardingStatusResponse(BaseModel):
    """Response for onboarding status."""
    steps: List[OnboardingStepResponse]
    current_step: Optional[str]
    is_complete: bool
    whatsapp_connected: bool
    phone_number: Optional[str]


class OAuthCallbackRequest(BaseModel):
    """Request for OAuth callback."""
    code: str
    state: str


class WhatsAppAccountResponse(BaseModel):
    """Response for WhatsApp account info."""
    id: UUID
    waba_id: Optional[str]
    phone_number_id: Optional[str]
    display_phone_number: Optional[str]
    token_status: str
    webhook_status: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WhatsAppDiagnosticsResponse(BaseModel):
    environment: str
    backend_url: str
    webhook_public_url: str
    meta_app_id_set: bool
    meta_app_secret_set: bool
    meta_config_id_set: bool
    meta_redirect_uri: str
    expected_redirect_uri: str
    issues: list[str]
    hints: list[str]
    oauth_url_preview: str


@router.post("/whatsapp/start", response_model=OnboardingStartResponse)
async def start_whatsapp_onboarding(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> OnboardingStartResponse:
    """
    Start WhatsApp onboarding process.
    
    Returns OAuth URL and Embedded Signup configuration.
    """
    service = OnboardingService(db)
    
    try:
        result = service.start_onboarding(current_tenant.id)
        return OnboardingStartResponse(**result)
    except MetaAPIError as e:
        error_messages = e.details.get("errors") if isinstance(e.details, dict) else None
        detail = "Meta yapılandırması eksik veya geçersiz."
        if error_messages:
            detail = f"{detail} " + " ".join(error_messages)
        SystemEventService(db).log(
            tenant_id=str(current_tenant.id),
            source="meta",
            level="warn",
            code="META_ONBOARDING_CONFIG_INVALID",
            message=detail,
            meta_json={"details": e.details},
            correlation_id=None
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Onboarding başlatılamadı: {str(e)}"
        )


@router.get("/whatsapp/diagnostics", response_model=WhatsAppDiagnosticsResponse)
async def whatsapp_diagnostics(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> WhatsAppDiagnosticsResponse:
    diagnostics = meta_api_service.get_onboarding_diagnostics()
    return WhatsAppDiagnosticsResponse(**diagnostics)


@router.get("/whatsapp/callback")
async def whatsapp_oauth_callback(
    code: str = Query(..., description="Authorization code from Meta"),
    state: str = Query(..., description="State parameter with tenant ID"),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth callback from Meta.
    
    This endpoint is called by Meta after user completes authorization.
    Exchanges code for token and saves credentials.
    """
    # Extract tenant_id from state
    try:
        tenant_id_str = state.split(":")[0]
        tenant_id = UUID(tenant_id_str)
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz state parametresi"
        )
    
    service = OnboardingService(db)
    
    try:
        await service.process_oauth_callback(tenant_id, code)
        return HTMLResponse(
            content="""
            <html>
            <head><title>WhatsApp Bağlandı</title></head>
            <body>
                <script>
                    if (window.opener) {
                        window.opener.postMessage({type: 'WHATSAPP_CONNECTED', success: true}, '*');
                        window.close();
                    } else {
                        window.location.href = '/dashboard/setup/whatsapp?success=true';
                    }
                </script>
                <p>WhatsApp bağlantısı başarılı! Bu pencere kapanacak...</p>
            </body>
            </html>
            """
        )
    except MetaAPIError as e:
        error_message = f"Meta API hatası: {e.message}"
        error_message_js = json.dumps(error_message)
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>WhatsApp Bağlantı Hatası</title></head>
            <body>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{type: 'WHATSAPP_CONNECTED', success: false, error: {error_message_js}}}, '*');
                    }}
                </script>
                <p>{error_message}</p>
            </body>
            </html>
            """,
            status_code=status.HTTP_400_BAD_REQUEST
        )


@router.get("/whatsapp/status", response_model=OnboardingStatusResponse)
async def get_whatsapp_onboarding_status(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> OnboardingStatusResponse:
    """
    Get current WhatsApp onboarding status.
    
    Returns all steps with their current statuses.
    """
    service = OnboardingService(db)
    
    steps = service.get_onboarding_steps(current_tenant.id)
    account = service.get_whatsapp_account(current_tenant.id)
    
    # Find current step (first non-done step)
    current_step = None
    is_complete = True
    for step in steps:
        if step.status != "done":
            current_step = step.step_key
            is_complete = False
            break
    
    return OnboardingStatusResponse(
        steps=[OnboardingStepResponse.model_validate(s) for s in steps],
        current_step=current_step,
        is_complete=is_complete,
        whatsapp_connected=account.is_active if account else False,
        phone_number=account.display_phone_number if account else None
    )


@router.get("/whatsapp/account", response_model=Optional[WhatsAppAccountResponse])
async def get_whatsapp_account(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> Optional[WhatsAppAccountResponse]:
    """
    Get WhatsApp account details.
    
    Returns account info without sensitive data (tokens).
    """
    service = OnboardingService(db)
    account = service.get_whatsapp_account(current_tenant.id)
    
    if not account:
        return None
    
    return WhatsAppAccountResponse.model_validate(account)


@router.post("/whatsapp/reset")
async def reset_whatsapp_onboarding(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
):
    """
    Reset WhatsApp onboarding to start fresh.
    
    Deletes existing WhatsApp account and resets steps.
    """
    service = OnboardingService(db)
    
    # Delete existing account
    account = service.get_whatsapp_account(current_tenant.id)
    if account:
        db.delete(account)
    
    # Re-initialize steps
    service.initialize_onboarding_steps(current_tenant.id)
    
    db.commit()
    
    service.create_audit_log(
        tenant_id=current_tenant.id,
        user_id=current_user.id,
        action="whatsapp_onboarding_reset"
    )
    
    return {"success": True, "message": "WhatsApp kurulumu sıfırlandı"}


@router.post("/whatsapp/retry-step/{step_key}")
async def retry_onboarding_step(
    step_key: str,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
):
    """
    Retry a failed onboarding step.
    """
    from app.models.onboarding import StepStatus
    
    service = OnboardingService(db)
    
    step = service.update_step_status(
        current_tenant.id,
        step_key,
        StepStatus.PENDING,
        message="Yeniden deneniyor..."
    )
    
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adım bulunamadı"
        )
    
    return {"success": True, "message": f"{step_key} adımı sıfırlandı"}
