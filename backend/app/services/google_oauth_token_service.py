"""Google OAuth token state and refresh helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token
from app.models.google_oauth_token import GoogleOAuthToken

logger = logging.getLogger(__name__)


class GoogleOAuthTokenService:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    EXPIRY_SAFETY_SECONDS = 60

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _configured_for_refresh() -> bool:
        return bool((settings.GOOGLE_CLIENT_ID or "").strip() and (settings.GOOGLE_CLIENT_SECRET or "").strip())

    @staticmethod
    def parse_scopes(raw_scope: str | list[str] | None) -> list[str]:
        if isinstance(raw_scope, list):
            return sorted({str(item).strip() for item in raw_scope if str(item).strip()})
        if isinstance(raw_scope, str):
            return sorted({item.strip() for item in raw_scope.replace(",", " ").split() if item.strip()})
        return []

    def get_tenant_google_token(self, tenant_id) -> GoogleOAuthToken | None:
        return self.db.query(GoogleOAuthToken).filter(
            GoogleOAuthToken.tenant_id == tenant_id,
            GoogleOAuthToken.provider == "google",
        ).first()

    def upsert_tenant_google_token(
        self,
        *,
        tenant_id,
        access_token: str | None,
        refresh_token: str | None,
        scopes: list[str] | None,
        expires_in_seconds: int | None,
    ) -> GoogleOAuthToken:
        token_row = self.get_tenant_google_token(tenant_id)
        if token_row is None:
            token_row = GoogleOAuthToken(
                tenant_id=tenant_id,
                provider="google",
            )
            self.db.add(token_row)

        if access_token:
            token_row.access_token_encrypted = encrypt_token(access_token)
        if refresh_token:
            token_row.refresh_token_encrypted = encrypt_token(refresh_token)
        if scopes is not None:
            token_row.scopes_json = scopes

        if expires_in_seconds and expires_in_seconds > 0:
            token_row.expires_at = self._utcnow() + timedelta(seconds=max(1, expires_in_seconds - self.EXPIRY_SAFETY_SECONDS))
        elif expires_in_seconds is not None:
            token_row.expires_at = None

        token_row.updated_at = self._utcnow()
        self.db.commit()
        self.db.refresh(token_row)
        return token_row

    def ensure_fresh_or_expired(self, token_row: GoogleOAuthToken) -> str:
        now = self._utcnow()
        if token_row.expires_at is None or token_row.expires_at > now:
            return "connected"

        if not token_row.refresh_token_encrypted or not self._configured_for_refresh():
            return "expired"

        refresh_token = decrypt_token(token_row.refresh_token_encrypted)
        if not refresh_token:
            return "expired"

        try:
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
                logger.warning("Google token refresh failed status=%s body=%s", response.status_code, str(data)[:300])
                return "expired"

            scopes = self.parse_scopes(data.get("scope")) or list(token_row.scopes_json or [])
            self.upsert_tenant_google_token(
                tenant_id=token_row.tenant_id,
                access_token=data.get("access_token"),
                refresh_token=None,
                scopes=scopes,
                expires_in_seconds=int(data.get("expires_in") or 3600),
            )
            return "connected"
        except Exception as exc:
            logger.warning("Google token refresh exception: %s", exc)
            return "expired"

