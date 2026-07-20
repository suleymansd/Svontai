"""
Google Calendar OAuth + event integration service (Real Estate Pack).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from app.core.time import utc_now_naive
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID

import httpx
import jwt
from jwt import InvalidTokenError as JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token
from app.models.real_estate import RealEstateGoogleCalendarIntegration
from app.models.appointment import Appointment
from app.models.google_oauth_token import GoogleOAuthToken
from app.models.tenant import Tenant
from app.services.google_oauth_token_service import GoogleOAuthTokenService


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
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    STATE_EXP_MINUTES = 15
    CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"

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
        return utc_now_naive()

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
        expires_in = int(token_data.get("expires_in") or 0)
        granted_scopes = GoogleOAuthTokenService.parse_scopes(token_data.get("scope")) or [
            scope for scope in self.SCOPES if scope.startswith("https://www.googleapis.com/auth/")
        ]
        if access_token:
            integration.access_token_encrypted = encrypt_token(access_token)
        if refresh_token:
            integration.refresh_token_encrypted = encrypt_token(refresh_token)

        integration.status = "active"
        integration.calendar_id = "primary"
        integration.updated_at = self._utcnow()

        self.db.commit()
        self.db.refresh(integration)

        GoogleOAuthTokenService(self.db).upsert_tenant_google_token(
            tenant_id=tenant_id,
            access_token=access_token,
            refresh_token=refresh_token,
            scopes=granted_scopes,
            expires_in_seconds=expires_in if expires_in > 0 else None,
        )
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
            token_row_service = GoogleOAuthTokenService(self.db)
            fresh_access_token = self._refresh_access_token(refresh_token)
            integration.access_token_encrypted = encrypt_token(fresh_access_token)
            integration.updated_at = self._utcnow()
            self.db.commit()
            token_row_service.upsert_tenant_google_token(
                tenant_id=integration.tenant_id,
                access_token=fresh_access_token,
                refresh_token=None,
                scopes=None,
                expires_in_seconds=3600,
            )
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

    def _tenant_access_token(self, tenant_id: UUID) -> str:
        token_service = GoogleOAuthTokenService(self.db)
        token_row = token_service.get_tenant_google_token(tenant_id)
        if token_row is None:
            raise GoogleCalendarError("Tenant için bağlı Google hesabı bulunamadı.")
        scopes = set(token_row.scopes_json or [])
        if self.CALENDAR_EVENTS_SCOPE not in scopes and "https://www.googleapis.com/auth/calendar" not in scopes:
            raise GoogleCalendarError("Google Calendar izni verilmemiş.")
        if token_service.ensure_fresh_or_expired(token_row) != "connected":
            raise GoogleCalendarError("Google oturumunun süresi dolmuş; hesabı yeniden bağlayın.")
        token_row = token_service.get_tenant_google_token(tenant_id)
        access_token = decrypt_token(token_row.access_token_encrypted) if token_row and token_row.access_token_encrypted else None
        if not access_token:
            raise GoogleCalendarError("Aktif Google access token bulunamadı.")
        return access_token

    @staticmethod
    def _appointment_event_payload(appointment: Appointment) -> dict:
        end_at = appointment.starts_at + timedelta(minutes=appointment.duration_minutes or 60)
        description_parts = [
            f"Müşteri: {appointment.customer_name}",
            appointment.notes or "",
            f"SvontAI randevu kimliği: {appointment.id}",
        ]
        payload: dict = {
            "summary": appointment.subject,
            "description": "\n".join(part for part in description_parts if part),
            "start": {"dateTime": appointment.starts_at.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_at.isoformat(), "timeZone": "UTC"},
            "extendedProperties": {"private": {"svontai_appointment_id": str(appointment.id)}},
        }
        if appointment.customer_email:
            payload["attendees"] = [{"email": appointment.customer_email}]
        return payload

    def sync_appointment(self, appointment: Appointment) -> str:
        access_token = self._tenant_access_token(appointment.tenant_id)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        base_url = f"{self.CALENDAR_API_BASE}/calendars/primary/events"

        if appointment.status == "cancelled":
            if appointment.calendar_event_id:
                response = httpx.delete(
                    f"{base_url}/{appointment.calendar_event_id}",
                    headers=headers,
                    params={"sendUpdates": "none"},
                    timeout=20,
                )
                if response.status_code not in {204, 404, 410}:
                    raise GoogleCalendarError(f"Google Calendar event silinemedi: {response.text[:300]}")
            appointment.calendar_provider = "google"
            appointment.calendar_sync_status = "cancelled"
            appointment.calendar_last_error = None
            appointment.calendar_synced_at = self._utcnow()
            self.db.commit()
            return "cancelled"

        payload = self._appointment_event_payload(appointment)
        if appointment.calendar_event_id:
            response = httpx.patch(
                f"{base_url}/{appointment.calendar_event_id}",
                headers=headers,
                params={"sendUpdates": "none"},
                json=payload,
                timeout=20,
            )
        else:
            response = httpx.post(
                base_url,
                headers=headers,
                params={"sendUpdates": "none"},
                json=payload,
                timeout=20,
            )
        try:
            data = response.json()
        except Exception:
            data = {}
        if not response.is_success or "error" in data:
            detail = (data.get("error") or {}).get("message") or response.text[:300]
            raise GoogleCalendarError(f"Google Calendar randevu senkronizasyonu başarısız: {detail}")

        appointment.calendar_event_id = data.get("id") or appointment.calendar_event_id
        appointment.calendar_provider = "google"
        appointment.calendar_sync_status = "synced"
        appointment.calendar_last_error = None
        appointment.calendar_synced_at = self._utcnow()
        self.db.commit()
        return "synced"

    def sync_pending_appointments(self, limit: int = 100) -> dict[str, int]:
        rows = (
            self.db.query(Appointment)
            .join(GoogleOAuthToken, GoogleOAuthToken.tenant_id == Appointment.tenant_id)
            .filter(
                GoogleOAuthToken.provider == "google",
                Appointment.calendar_sync_status.in_(["pending", "failed"]),
            )
            .order_by(Appointment.updated_at.asc())
            .limit(limit)
            .all()
        )
        result = {"processed": 0, "synced": 0, "cancelled": 0, "failed": 0}
        for appointment in rows:
            result["processed"] += 1
            try:
                status_value = self.sync_appointment(appointment)
                result[status_value] += 1
            except Exception as exc:
                self.db.rollback()
                appointment = self.db.get(Appointment, appointment.id)
                if appointment is not None:
                    appointment.calendar_sync_status = "failed"
                    appointment.calendar_last_error = str(exc)[:1000]
                    self.db.commit()
                result["failed"] += 1
        return result

    def pull_appointment_updates(self, limit_tenants: int = 100) -> dict[str, int]:
        token_rows = self.db.query(GoogleOAuthToken).filter(
            GoogleOAuthToken.provider == "google"
        ).limit(limit_tenants).all()
        result = {"tenants": 0, "events": 0, "updated": 0, "failed": 0}

        for token_row in token_rows:
            tenant = self.db.get(Tenant, token_row.tenant_id)
            if tenant is None:
                continue
            result["tenants"] += 1
            try:
                access_token = self._tenant_access_token(tenant.id)
                sync_token = str((tenant.settings or {}).get("google_calendar_appointment_sync_token") or "")
                params: dict[str, str | int | bool] = {
                    "singleEvents": True,
                    "showDeleted": True,
                    "maxResults": 2500,
                }
                if sync_token:
                    params["syncToken"] = sync_token
                else:
                    params["timeMin"] = (self._utcnow() - timedelta(days=90)).isoformat() + "Z"

                response = httpx.get(
                    f"{self.CALENDAR_API_BASE}/calendars/primary/events",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                    timeout=20,
                )
                if response.status_code == 410 and sync_token:
                    params.pop("syncToken", None)
                    params["timeMin"] = (self._utcnow() - timedelta(days=90)).isoformat() + "Z"
                    response = httpx.get(
                        f"{self.CALENDAR_API_BASE}/calendars/primary/events",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params=params,
                        timeout=20,
                    )
                data = response.json()
                if not response.is_success or "error" in data:
                    detail = (data.get("error") or {}).get("message") or response.text[:300]
                    raise GoogleCalendarError(f"Google Calendar değişiklikleri alınamadı: {detail}")

                for event in data.get("items") or []:
                    private = ((event.get("extendedProperties") or {}).get("private") or {})
                    appointment_id = private.get("svontai_appointment_id")
                    if not appointment_id:
                        continue
                    try:
                        appointment_uuid = UUID(str(appointment_id))
                    except ValueError:
                        continue
                    appointment = self.db.query(Appointment).filter(
                        Appointment.id == appointment_uuid,
                        Appointment.tenant_id == tenant.id,
                    ).first()
                    if appointment is None:
                        continue
                    result["events"] += 1
                    if event.get("status") == "cancelled":
                        appointment.status = "cancelled"
                        appointment.calendar_sync_status = "cancelled"
                    else:
                        start_at = self._parse_google_dt((event.get("start") or {}).get("dateTime"))
                        if start_at:
                            appointment.starts_at = start_at
                        if event.get("summary"):
                            appointment.subject = str(event["summary"])[:255]
                        appointment.calendar_sync_status = "synced"
                    appointment.calendar_provider = "google"
                    appointment.calendar_event_id = str(event.get("id") or appointment.calendar_event_id or "") or None
                    appointment.calendar_last_error = None
                    appointment.calendar_synced_at = self._utcnow()
                    result["updated"] += 1

                next_sync_token = data.get("nextSyncToken")
                if next_sync_token:
                    tenant.settings = {
                        **(tenant.settings or {}),
                        "google_calendar_appointment_sync_token": str(next_sync_token),
                    }
                self.db.commit()
            except Exception:
                self.db.rollback()
                result["failed"] += 1
        return result

    @staticmethod
    def _parse_google_dt(value: str) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
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

    def list_tenant_busy_intervals(
        self,
        tenant_id: UUID,
        *,
        time_min: datetime,
        time_max: datetime,
    ) -> list[tuple[datetime, datetime]]:
        """Return primary-calendar busy periods for the tenant Google connection."""
        access_token = self._tenant_access_token(tenant_id)
        response = httpx.post(
            f"{self.CALENDAR_API_BASE}/freeBusy",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "timeMin": time_min.isoformat() + "Z",
                "timeMax": time_max.isoformat() + "Z",
                "items": [{"id": "primary"}],
            },
            timeout=20,
        )
        try:
            data = response.json()
        except Exception:
            data = {}
        if not response.is_success or "error" in data:
            detail = (data.get("error") or {}).get("message") or response.text[:300]
            raise GoogleCalendarError(f"Google Calendar doluluk bilgisi alınamadı: {detail}")

        rows = (((data.get("calendars") or {}).get("primary") or {}).get("busy") or [])
        output: list[tuple[datetime, datetime]] = []
        for row in rows:
            start_at = self._parse_google_dt(row.get("start"))
            end_at = self._parse_google_dt(row.get("end"))
            if start_at and end_at and end_at > start_at:
                output.append((start_at, end_at))
        return output
