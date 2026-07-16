"""
Onboarding API router for WhatsApp setup flow.
"""

import json
from uuid import UUID
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.user import User
from app.models.tenant import Tenant
from app.services.onboarding_service import OnboardingService
from app.services.meta_api import MetaAPIError, meta_api_service
from app.services.openwa_client import OpenWAError, openwa_client
from app.services.system_event_service import SystemEventService
from app.core.rate_limit import rate_limit_key, require_rate_limit, whatsapp_connect_rate_limiter
from app.core.config import settings


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
    model_config = ConfigDict(from_attributes=True)

    step_key: str
    step_order: int
    step_name: str
    step_description: Optional[str]
    status: str
    message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: datetime


class OnboardingStatusResponse(BaseModel):
    """Response for onboarding status."""
    steps: List[OnboardingStepResponse]
    current_step: Optional[str]
    is_complete: bool
    whatsapp_connected: bool
    phone_number: Optional[str]
    provider: Optional[str] = None
    provider_status: Optional[str] = None
    openwa_enabled: bool = False


class OAuthCallbackRequest(BaseModel):
    """Request for OAuth callback."""
    code: str
    state: str


class WhatsAppAccountResponse(BaseModel):
    """Response for WhatsApp account info."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    provider_session_id: Optional[str]
    waba_id: Optional[str]
    phone_number_id: Optional[str]
    display_phone_number: Optional[str]
    token_status: str
    webhook_status: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class OpenWAStartRequest(BaseModel):
    accepted_unofficial_risk: bool = False


class OpenWAStatusResponse(BaseModel):
    provider: str
    session_id: Optional[str]
    status: str
    connected: bool
    phone_number: Optional[str]
    push_name: Optional[str]
    last_error: Optional[str]
    qr_code: Optional[str] = None


class WhatsAppDiagnosticsResponse(BaseModel):
    environment: str
    backend_url: str
    webhook_public_url: str
    meta_app_id_set: bool
    meta_app_secret_set: bool
    meta_config_id_set: bool
    meta_redirect_uri: str
    expected_redirect_uri: str
    checks: list[dict]
    issues: list[str]
    hints: list[str]
    oauth_url_preview: str
    live_probe: Optional[dict] = None


@router.post("/whatsapp/start", response_model=OnboardingStartResponse)
async def start_whatsapp_onboarding(
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> OnboardingStartResponse:
    """
    Start WhatsApp onboarding process.
    
    Returns OAuth URL and Embedded Signup configuration.
    """
    require_rate_limit(
        whatsapp_connect_rate_limiter,
        rate_limit_key(request, "whatsapp-connect", current_tenant.id),
        "Çok fazla WhatsApp bağlantı denemesi. Lütfen birkaç dakika sonra tekrar deneyin.",
    )
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


@router.post("/whatsapp/openwa/start", response_model=OpenWAStatusResponse)
async def start_openwa_onboarding(
    body: OpenWAStartRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
) -> OpenWAStatusResponse:
    require_rate_limit(
        whatsapp_connect_rate_limiter,
        rate_limit_key(request, "openwa-connect", current_tenant.id),
        "Çok fazla WhatsApp bağlantı denemesi. Lütfen birkaç dakika sonra tekrar deneyin.",
    )
    try:
        result = await OnboardingService(db).start_openwa_onboarding(
            current_tenant.id,
            accepted_unofficial_risk=body.accepted_unofficial_risk,
        )
        SystemEventService(db).log(
            tenant_id=str(current_tenant.id),
            source="openwa",
            level="info",
            code="OPENWA_SESSION_STARTED",
            message="WhatsApp QR bağlantı oturumu başlatıldı.",
            meta_json={"session_id": result.get("session_id"), "user_id": str(current_user.id)},
            correlation_id=None,
        )
        return OpenWAStatusResponse(**result)
    except OpenWAError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if exc.status_code in {None, 400, 404, 409} else status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )


@router.get("/whatsapp/openwa/qr", response_model=OpenWAStatusResponse)
async def get_openwa_qr(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> OpenWAStatusResponse:
    _ = current_user
    try:
        return OpenWAStatusResponse(
            **(await OnboardingService(db).get_openwa_qr(current_tenant.id))
        )
    except OpenWAError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if exc.status_code in {None, 404} else status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )


@router.post("/whatsapp/openwa/disconnect")
async def disconnect_openwa(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
) -> dict:
    try:
        await OnboardingService(db).disconnect_openwa(current_tenant.id)
    except OpenWAError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"success": True, "message": "WhatsApp QR bağlantısı kaldırıldı."}


@router.get("/whatsapp/diagnostics", response_model=WhatsAppDiagnosticsResponse)
async def whatsapp_diagnostics(
    live: bool = Query(False, description="Canlı OAuth endpoint probe çalıştır"),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> WhatsAppDiagnosticsResponse:
    diagnostics = meta_api_service.get_onboarding_diagnostics()
    if live:
        diagnostics["live_probe"] = await meta_api_service.probe_oauth_dialog()
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
        phone_number=account.display_phone_number if account else None,
        provider=account.provider if account else None,
        provider_status=(
            (account.provider_metadata_json or {}).get("engine_status")
            if account and account.provider == "openwa"
            else (account.token_status if account else None)
        ),
        openwa_enabled=bool(settings.OPENWA_ENABLED and openwa_client.configured),
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
    
    # Delete existing account and remote QR session when applicable.
    account = service.get_whatsapp_account(current_tenant.id)
    if account:
        if account.provider == "openwa":
            try:
                await service.disconnect_openwa(current_tenant.id)
            except OpenWAError as exc:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
        else:
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
