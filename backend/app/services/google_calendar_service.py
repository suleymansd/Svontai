"""
Google Calendar OAuth + event integration service (Real Estate Pack).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token
from app.models.real_estate import RealEstateGoogleCalendarIntegration


class GoogleCalendarError(Exception):
    """Google Calendar integration error."""


class GoogleCalendarService:
    OAUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
    SCOPES = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    STATE_EXP_MINUTES = 15

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and settings.GOOGLE_REDIRECT_URI)

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.utcnow()

    def _encode_state(self, tenant_id: UUID, agent_id: UUID) -> str:
        payload = {
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "exp": int((self._utcnow() + timedelta(minutes=self.STATE_EXP_MINUTES)).timestamp()),
            "iat": int(self._utcnow().timestamp()),
            "scope": "re_google_calendar",
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def _decode_state(self, state: str) -> dict:
        try:
            payload = jwt.decode(
                state,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except JWTError as exc:
            raise GoogleCalendarError("Geçersiz veya süresi dolmuş state.") from exc

        if payload.get("scope") != "re_google_calendar":
            raise GoogleCalendarError("Geçersiz state kapsamı.")
        return payload

    def get_oauth_start(self, tenant_id: UUID, agent_id: UUID) -> dict:
        if not self.is_configured():
            raise GoogleCalendarError("Google Calendar ayarları eksik. GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI kontrol edin.")

        state = self._encode_state(tenant_id, agent_id)
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        auth_url = f"{self.OAUTH_BASE_URL}?{urlencode(params)}"
        return {"auth_url": auth_url, "state": state}

    def _exchange_code_for_tokens(self, code: str) -> dict:
        response = httpx.post(
            self.TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=20,
        )
        data = response.json()
        if not response.is_success or "error" in data:
            raise GoogleCalendarError(
                f"Google token exchange hatası: {data.get('error_description') or data.get('error') or response.text[:200]}"
            )
        return data

    def _refresh_access_token(self, refresh_token: str) -> str:
        response = httpx.post(
            self.TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
        data = response.json()
        if not response.is_success or "error" in data or not data.get("access_token"):
            raise GoogleCalendarError(
                f"Google token refresh hatası: {data.get('error_description') or data.get('error') or response.text[:200]}"
            )
        return data["access_token"]

    def process_oauth_callback(self, code: str, state: str) -> RealEstateGoogleCalendarIntegration:
        payload = self._decode_state(state)
        tenant_id = UUID(payload["tenant_id"])
        agent_id = UUID(payload["agent_id"])
        token_data = self._exchange_code_for_tokens(code)

        integration = self.db.query(RealEstateGoogleCalendarIntegration).filter(
            RealEstateGoogleCalendarIntegration.tenant_id == tenant_id,
            RealEstateGoogleCalendarIntegration.agent_id == agent_id,
        ).first()
        if integration is None:
            integration = RealEstateGoogleCalendarIntegration(
                tenant_id=tenant_id,
                agent_id=agent_id,
            )
            self.db.add(integration)

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        if access_token:
            integration.access_token_encrypted = encrypt_token(access_token)
        if refresh_token:
            integration.refresh_token_encrypted = encrypt_token(refresh_token)

        integration.status = "active"
        integration.calendar_id = "primary"
        integration.updated_at = self._utcnow()

        self.db.commit()
        self.db.refresh(integration)
        return integration

    def get_agent_integration(self, tenant_id: UUID, agent_id: UUID) -> RealEstateGoogleCalendarIntegration | None:
        return self.db.query(RealEstateGoogleCalendarIntegration).filter(
            RealEstateGoogleCalendarIntegration.tenant_id == tenant_id,
            RealEstateGoogleCalendarIntegration.agent_id == agent_id,
        ).first()

    def disconnect_agent_integration(self, tenant_id: UUID, agent_id: UUID) -> bool:
        integration = self.get_agent_integration(tenant_id, agent_id)
        if integration is None:
            return False
        integration.status = "inactive"
        integration.access_token_encrypted = None
        integration.refresh_token_encrypted = None
        integration.updated_at = self._utcnow()
        self.db.commit()
        return True

    def _resolve_access_token(self, integration: RealEstateGoogleCalendarIntegration) -> str:
        refresh_token = decrypt_token(integration.refresh_token_encrypted) if integration.refresh_token_encrypted else None
        if refresh_token:
            fresh_access_token = self._refresh_access_token(refresh_token)
            integration.access_token_encrypted = encrypt_token(fresh_access_token)
            integration.updated_at = self._utcnow()
            self.db.commit()
            return fresh_access_token

        access_token = decrypt_token(integration.access_token_encrypted) if integration.access_token_encrypted else None
        if not access_token:
            raise GoogleCalendarError("Aktif Google access token bulunamadı.")
        return access_token

    def create_event(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        summary: str,
        description: str,
        start_at: datetime,
        end_at: datetime,
        attendee_email: str | None = None,
    ) -> str:
        integration = self.get_agent_integration(tenant_id, agent_id)
        if integration is None or integration.status != "active":
            raise GoogleCalendarError("Danışman için aktif Google Calendar entegrasyonu bulunamadı.")

        access_token = self._resolve_access_token(integration)
        calendar_id = integration.calendar_id or "primary"

        payload: dict = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_at.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_at.isoformat(), "timeZone": "UTC"},
        }
        if attendee_email:
            payload["attendees"] = [{"email": attendee_email}]

        response = httpx.post(
            f"{self.CALENDAR_API_BASE}/calendars/{calendar_id}/events",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        data = response.json()
        if not response.is_success or "error" in data:
            raise GoogleCalendarError(
                f"Google Calendar event oluşturulamadı: {data.get('error', {}).get('message') or response.text[:300]}"
            )
        return data.get("id")
