"""
Google Calendar OAuth + event integration service (Real Estate Pack).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse
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
    CALLBACK_PATH = "/real-estate/calendar/google/callback"
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
    def _is_placeholder(value: str) -> bool:
        normalized = (value or "").strip().upper()
        if not normalized:
            return True
        placeholder_tokens = ("YOUR_", "CHANGE_", "EXAMPLE", "PLACEHOLDER", "_HERE")
        return any(token in normalized for token in placeholder_tokens)

    @staticmethod
    def _expected_redirect_uri() -> str:
        base = (settings.BACKEND_URL or settings.WEBHOOK_PUBLIC_URL or "").strip()
        return f"{base.rstrip('/')}{GoogleCalendarService.CALLBACK_PATH}" if base else ""

    def validate_config(self) -> None:
        errors: list[str] = []

        client_id = (settings.GOOGLE_CLIENT_ID or "").strip()
        client_secret = (settings.GOOGLE_CLIENT_SECRET or "").strip()
        redirect_uri = (settings.GOOGLE_REDIRECT_URI or "").strip()
        parsed = urlparse(redirect_uri)
        expected_redirect = self._expected_redirect_uri()
        expected_parsed = urlparse(expected_redirect)

        if self._is_placeholder(client_id):
            errors.append("GOOGLE_CLIENT_ID eksik veya örnek değer olarak bırakılmış.")
        if self._is_placeholder(client_secret):
            errors.append("GOOGLE_CLIENT_SECRET eksik veya örnek değer olarak bırakılmış.")

        if self._is_placeholder(redirect_uri) or not parsed.scheme or not parsed.netloc:
            errors.append("GOOGLE_REDIRECT_URI geçerli bir URL olmalıdır.")
        else:
            if settings.ENVIRONMENT == "prod" and parsed.scheme != "https":
                errors.append("Üretimde GOOGLE_REDIRECT_URI https olmalıdır.")
            if not redirect_uri.endswith(self.CALLBACK_PATH):
                errors.append(f"GOOGLE_REDIRECT_URI '{self.CALLBACK_PATH}' ile bitmelidir.")
            if expected_parsed.netloc and parsed.netloc and expected_parsed.netloc != parsed.netloc:
                errors.append("GOOGLE_REDIRECT_URI domain'i BACKEND_URL/WEBHOOK_PUBLIC_URL ile aynı olmalıdır.")

        if errors:
            raise GoogleCalendarError("Google Calendar yapılandırması eksik/geçersiz. " + " ".join(errors))

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
        self.validate_config()

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

    def get_diagnostics(self) -> dict[str, Any]:
        client_id = (settings.GOOGLE_CLIENT_ID or "").strip()
        client_secret = (settings.GOOGLE_CLIENT_SECRET or "").strip()
        redirect_uri = (settings.GOOGLE_REDIRECT_URI or "").strip()
        parsed = urlparse(redirect_uri)
        expected_redirect = self._expected_redirect_uri()
        expected_parsed = urlparse(expected_redirect)

        issues: list[str] = []
        hints: list[str] = []
        checks: list[dict[str, Any]] = []

        client_id_set = bool(client_id) and not self._is_placeholder(client_id)
        client_secret_set = bool(client_secret) and not self._is_placeholder(client_secret)
        redirect_set = bool(redirect_uri) and not self._is_placeholder(redirect_uri)

        if not client_id_set:
            issues.append("GOOGLE_CLIENT_ID eksik")
        if not client_secret_set:
            issues.append("GOOGLE_CLIENT_SECRET eksik")

        if not redirect_set:
            issues.append("GOOGLE_REDIRECT_URI eksik")
        elif not parsed.scheme or not parsed.netloc:
            issues.append("GOOGLE_REDIRECT_URI geçerli bir URL olmalıdır")
        elif not redirect_uri.endswith(self.CALLBACK_PATH):
            issues.append(f"GOOGLE_REDIRECT_URI '{self.CALLBACK_PATH}' ile bitmelidir")

        if redirect_set and parsed.scheme != "https" and settings.ENVIRONMENT == "prod":
            issues.append("Üretimde GOOGLE_REDIRECT_URI https olmalı")

        if redirect_set and expected_parsed.netloc and parsed.netloc and expected_parsed.netloc != parsed.netloc:
            issues.append("GOOGLE_REDIRECT_URI domain BACKEND_URL/WEBHOOK_PUBLIC_URL ile aynı değil")

        if redirect_set and expected_redirect and redirect_uri != expected_redirect:
            hints.append("GOOGLE_REDIRECT_URI ile beklenen callback URL aynı olmalı (Google Console'da da aynısını tanımlayın).")

        checks.extend([
            {
                "key": "google_client_id",
                "ok": client_id_set,
                "value": "set" if client_id_set else "missing",
                "message": "Client ID tanımlı olmalı",
            },
            {
                "key": "google_client_secret",
                "ok": client_secret_set,
                "value": "set" if client_secret_set else "missing",
                "message": "Client Secret tanımlı olmalı",
            },
            {
                "key": "google_redirect_uri",
                "ok": redirect_set and redirect_uri.endswith(self.CALLBACK_PATH),
                "value": redirect_uri,
                "message": f"Redirect URI '{self.CALLBACK_PATH}' ile bitmeli",
            },
            {
                "key": "redirect_domain_match",
                "ok": not expected_parsed.netloc or not parsed.netloc or expected_parsed.netloc == parsed.netloc,
                "value": f"{parsed.netloc or '-'} vs {expected_parsed.netloc or '-'}",
                "message": "Redirect domain ve backend domain aynı olmalı",
            },
        ])

        hints.append("Google Cloud Console > OAuth 2.0 Client > Authorized redirect URIs içine callback URL birebir eklenmeli.")
        hints.append("Test modunda olmayan uygulamalarda Google OAuth consent screen publish durumu kontrol edilmeli.")

        auth_url_preview = ""
        try:
            auth_url_preview = self.get_oauth_start(UUID(int=0), UUID(int=0)).get("auth_url", "")
        except Exception:
            auth_url_preview = ""

        return {
            "environment": settings.ENVIRONMENT,
            "backend_url": settings.BACKEND_URL,
            "webhook_public_url": settings.WEBHOOK_PUBLIC_URL,
            "google_client_id_set": client_id_set,
            "google_client_secret_set": client_secret_set,
            "google_redirect_uri": redirect_uri,
            "expected_redirect_uri": expected_redirect,
            "checks": checks,
            "issues": issues,
            "hints": hints,
            "auth_url_preview": auth_url_preview,
        }

    async def probe_oauth_dialog(self) -> dict[str, Any]:
        try:
            oauth_url = self.get_oauth_start(UUID(int=0), UUID(int=0)).get("auth_url", "")
        except GoogleCalendarError as exc:
            return {
                "status": "config_invalid",
                "http_status": None,
                "location": "",
                "error": str(exc),
                "error_reason": None,
                "error_description": None,
            }

        try:
            async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
                response = await client.get(
                    oauth_url,
                    headers={"User-Agent": "SvontAI-GoogleCalendar-Diagnostics/1.0"},
                )
            location = response.headers.get("location", "")
            query = parse_qs(urlparse(location).query) if location else {}
            error = (query.get("error") or [None])[0]
            error_description = (query.get("error_description") or [None])[0]
            error_reason = (query.get("error_subtype") or [None])[0]
            status = "error" if (error or error_description or response.status_code >= 400) else "ok"
            return {
                "status": status,
                "http_status": response.status_code,
                "location": location,
                "error": error,
                "error_reason": error_reason,
                "error_description": error_description,
            }
        except Exception as exc:
            return {
                "status": "network_error",
                "http_status": None,
                "location": "",
                "error": str(exc),
                "error_reason": None,
                "error_description": None,
            }

    def _exchange_code_for_tokens(self, code: str) -> dict:
        self.validate_config()
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

    @staticmethod
    def _parse_google_dt(value: str) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=None)
        except Exception:
            return None

    def list_busy_intervals(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        time_min: datetime,
        time_max: datetime,
    ) -> list[tuple[datetime, datetime]]:
        integration = self.get_agent_integration(tenant_id, agent_id)
        if integration is None or integration.status != "active":
            return []

        access_token = self._resolve_access_token(integration)
        calendar_id = integration.calendar_id or "primary"
        response = httpx.post(
            f"{self.CALENDAR_API_BASE}/freeBusy",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "timeMin": time_min.isoformat() + "Z",
                "timeMax": time_max.isoformat() + "Z",
                "items": [{"id": calendar_id}],
            },
            timeout=20,
        )
        data = response.json()
        if not response.is_success or "error" in data:
            raise GoogleCalendarError(
                f"Google Calendar freebusy alınamadı: {data.get('error', {}).get('message') or response.text[:300]}"
            )

        busy_rows = (((data.get("calendars") or {}).get(calendar_id) or {}).get("busy") or [])
        output: list[tuple[datetime, datetime]] = []
        for row in busy_rows:
            start_at = self._parse_google_dt(row.get("start"))
            end_at = self._parse_google_dt(row.get("end"))
            if start_at and end_at and end_at > start_at:
                output.append((start_at, end_at))
        return output
