"""Tenant integration status endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.google_oauth_token import GoogleOAuthToken
from app.models.tenant import Tenant
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount
from app.services.google_oauth_token_service import GoogleOAuthTokenService
from app.services.autopilot_service import AutopilotService
from app.services.google_calendar_service import GoogleCalendarError, GoogleCalendarService


IntegrationState = Literal["connected", "missing", "expired"]


GOOGLE_SCOPE_MAP: dict[str, list[str]] = {
    "google_drive": [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ],
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://mail.google.com/",
    ],
    "google_sheets": [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/spreadsheets",
    ],
    "google_calendar": [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.events.freebusy",
    ],
}


class IntegrationStatusItem(BaseModel):
    status: IntegrationState
    required_scopes: list[str] = Field(default_factory=list)
    granted_scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    required: bool = True
    connectable: bool = False
    manageable: bool = False
    message: str | None = None


class IntegrationStatusResponse(BaseModel):
    google_drive: IntegrationStatusItem
    gmail: IntegrationStatusItem
    openai: IntegrationStatusItem
    ai_provider: IntegrationStatusItem
    google_sheets: IntegrationStatusItem
    document_converter: IntegrationStatusItem
    whatsapp_cloud: IntegrationStatusItem
    whatsapp_qr: IntegrationStatusItem
    google_calendar: IntegrationStatusItem
    n8n: IntegrationStatusItem


router = APIRouter(prefix="/integrations", tags=["Integrations"])


def _has_any_scope(granted_scopes: list[str], required_scopes: list[str]) -> bool:
    granted = set(granted_scopes or [])
    return any(scope in granted for scope in required_scopes)


def _google_item(
    *,
    key: str,
    token_state: IntegrationState,
    granted_scopes: list[str],
    expires_at: datetime | None,
    configured: bool,
) -> IntegrationStatusItem:
    required_scopes = GOOGLE_SCOPE_MAP[key]
    if token_state == "expired" and granted_scopes:
        return IntegrationStatusItem(
            status="expired",
            required_scopes=required_scopes,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
            connectable=configured,
            manageable=True,
            message="Google erişim süresi doldu. Gerekli izinleri yenilemek için tekrar bağlayın.",
        )

    scope_ready = (
        GoogleCalendarService.has_required_calendar_scopes(granted_scopes)
        if key == "google_calendar"
        else _has_any_scope(granted_scopes, required_scopes)
    )
    if not granted_scopes or not scope_ready:
        has_partial_google_connection = bool(granted_scopes)
        return IntegrationStatusItem(
            status="missing",
            required_scopes=required_scopes,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
            connectable=configured,
            manageable=bool(granted_scopes),
            message=(
                "Google Calendar uygunluk izni eksik. Randevu saatlerini doğrulamak için hesabı yeniden bağlayın."
                if key == "google_calendar" and has_partial_google_connection
                else "Google bağlantısını bir kez tamamladığınızda Drive, Gmail, Sheets ve Calendar birlikte açılır."
                if configured
                else "Google OAuth sunucu ayarları henüz tamamlanmadı. Sistem yöneticisinin Google Client bilgilerini eklemesi gerekiyor."
            ),
        )

    return IntegrationStatusItem(
        status="connected",
        required_scopes=required_scopes,
        granted_scopes=granted_scopes,
        expires_at=expires_at,
        connectable=configured,
        manageable=True,
        message="Google servisleri tek güvenli bağlantı üzerinden çalışıyor.",
    )


@router.get("/status", response_model=IntegrationStatusResponse)
async def get_integrations_status(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> IntegrationStatusResponse:
    _ = current_user

    google_token_service = GoogleOAuthTokenService(db)
    google_configured = GoogleCalendarService.is_configured()
    google_token = db.query(GoogleOAuthToken).filter(
        GoogleOAuthToken.tenant_id == current_tenant.id,
        GoogleOAuthToken.provider == "google",
    ).first()
    google_state: IntegrationState = "missing"
    granted_scopes: list[str] = []
    expires_at: datetime | None = None
    if google_token is not None:
        google_state = google_token_service.ensure_fresh_or_expired(google_token)
        db.refresh(google_token)
        granted_scopes = list(google_token.scopes_json or [])
        expires_at = google_token.expires_at

    whatsapp_account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.tenant_id == current_tenant.id,
        WhatsAppAccount.is_active == True,
    ).first()
    whatsapp_cloud_connected = bool(
        whatsapp_account
        and whatsapp_account.provider == "meta_cloud"
        and whatsapp_account.phone_number_id
        and whatsapp_account.access_token_encrypted
    )
    whatsapp_qr_connected = bool(
        whatsapp_account
        and whatsapp_account.provider == "openwa"
        and whatsapp_account.provider_session_id
    )

    ai_connected = bool(settings.ai_api_key)
    n8n_connected = bool(settings.USE_N8N and (settings.N8N_BASE_URL or "").strip())
    document_converter_connected = n8n_connected

    return IntegrationStatusResponse(
        google_drive=_google_item(
            key="google_drive",
            token_state=google_state,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
            configured=google_configured,
        ),
        gmail=_google_item(
            key="gmail",
            token_state=google_state,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
            configured=google_configured,
        ),
        google_sheets=_google_item(
            key="google_sheets",
            token_state=google_state,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
            configured=google_configured,
        ),
        google_calendar=_google_item(
            key="google_calendar",
            token_state=google_state,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
            configured=google_configured,
        ),
        # Keep ``openai`` for older clients while tools use the provider-neutral key.
        openai=IntegrationStatusItem(
            status="connected" if ai_connected else "missing",
            message="Yapay zeka sağlayıcısı sistem tarafından yönetilir.",
        ),
        ai_provider=IntegrationStatusItem(
            status="connected" if ai_connected else "missing",
            message="Yapay zeka sağlayıcısı sistem tarafından yönetilir.",
        ),
        document_converter=IntegrationStatusItem(
            status="connected" if document_converter_connected else "missing",
            message="Belge dönüştürme servisi otomasyon altyapısıyla birlikte yönetilir.",
        ),
        whatsapp_cloud=IntegrationStatusItem(
            status="connected" if whatsapp_cloud_connected else "missing",
            required=not whatsapp_qr_connected,
            connectable=True,
            manageable=whatsapp_cloud_connected,
            message=(
                "WhatsApp QR bağlı olduğu için Cloud bağlantısı zorunlu değil."
                if whatsapp_qr_connected and not whatsapp_cloud_connected
                else "Meta WhatsApp Cloud alternatif bağlantı yöntemidir."
            ),
        ),
        whatsapp_qr=IntegrationStatusItem(
            status="connected" if whatsapp_qr_connected else "missing",
            connectable=True,
            manageable=whatsapp_qr_connected,
            message="Telefonunuzdaki WhatsApp hesabı QR ile SvontAI'ye bağlıdır.",
        ),
        n8n=IntegrationStatusItem(
            status="connected" if n8n_connected else "missing",
            message="Otomasyon altyapısı sistem tarafından yönetilir.",
        ),
    )


@router.get("/google/start")
async def start_google_oauth(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
) -> dict:
    """Start one Google OAuth flow covering Drive, Gmail, Sheets and Calendar."""
    try:
        return GoogleCalendarService(db).get_oauth_start(current_tenant.id, current_user.id)
    except GoogleCalendarError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "GOOGLE_OAUTH_NOT_CONFIGURED",
                "message": str(exc),
                "action": "Google Client ID, Client Secret ve callback URL sunucu ayarlarına eklenmelidir.",
            },
        ) from exc


@router.get("/diagnostics")
async def get_integration_diagnostics(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> dict:
    _ = current_user
    return AutopilotService(db).run_diagnostics(current_tenant)


@router.post("/{provider}/repair")
async def repair_integration(
    provider: str,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
) -> dict:
    return AutopilotService(db).repair_provider(current_tenant, provider, current_user)
