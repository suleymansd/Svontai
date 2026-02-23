"""Tenant integration status endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
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
        "https://www.googleapis.com/auth/calendar",
    ],
}


class IntegrationStatusItem(BaseModel):
    status: IntegrationState
    required_scopes: list[str] = Field(default_factory=list)
    granted_scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class IntegrationStatusResponse(BaseModel):
    google_drive: IntegrationStatusItem
    gmail: IntegrationStatusItem
    openai: IntegrationStatusItem
    google_sheets: IntegrationStatusItem
    document_converter: IntegrationStatusItem
    whatsapp_cloud: IntegrationStatusItem
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
) -> IntegrationStatusItem:
    required_scopes = GOOGLE_SCOPE_MAP[key]
    if not granted_scopes or not _has_any_scope(granted_scopes, required_scopes):
        return IntegrationStatusItem(
            status="missing",
            required_scopes=required_scopes,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
        )

    if token_state == "expired":
        return IntegrationStatusItem(
            status="expired",
            required_scopes=required_scopes,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
        )

    return IntegrationStatusItem(
        status="connected",
        required_scopes=required_scopes,
        granted_scopes=granted_scopes,
        expires_at=expires_at,
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

    whatsapp_connected = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.tenant_id == current_tenant.id,
        WhatsAppAccount.is_active == True,
        WhatsAppAccount.phone_number_id.isnot(None),
        WhatsAppAccount.access_token_encrypted.isnot(None),
    ).first() is not None

    openai_connected = bool((settings.OPENAI_API_KEY or "").strip())
    n8n_connected = bool(settings.USE_N8N and (settings.N8N_BASE_URL or "").strip())
    document_converter_connected = n8n_connected

    return IntegrationStatusResponse(
        google_drive=_google_item(
            key="google_drive",
            token_state=google_state,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
        ),
        gmail=_google_item(
            key="gmail",
            token_state=google_state,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
        ),
        google_sheets=_google_item(
            key="google_sheets",
            token_state=google_state,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
        ),
        google_calendar=_google_item(
            key="google_calendar",
            token_state=google_state,
            granted_scopes=granted_scopes,
            expires_at=expires_at,
        ),
        openai=IntegrationStatusItem(status="connected" if openai_connected else "missing"),
        document_converter=IntegrationStatusItem(status="connected" if document_converter_connected else "missing"),
        whatsapp_cloud=IntegrationStatusItem(status="connected" if whatsapp_connected else "missing"),
        n8n=IntegrationStatusItem(status="connected" if n8n_connected else "missing"),
    )
