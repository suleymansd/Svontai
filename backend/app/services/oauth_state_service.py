"""Issue and atomically consume opaque OAuth state values."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.oauth_state import OAuthState


class InvalidOAuthState(ValueError):
    """Raised when an OAuth state is invalid, expired, or already consumed."""


class OAuthStateService:
    """Keep OAuth state bindings server-side and enforce one-time use."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _hash(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    def issue(
        self,
        *,
        provider: str,
        tenant_id: UUID,
        user_id: UUID,
        expires_minutes: int = 10,
        exclusive_tenant: bool = False,
    ) -> str:
        normalized_provider = provider.strip().lower()
        if not normalized_provider or len(normalized_provider) > 30:
            raise ValueError("Invalid OAuth provider")

        state = secrets.token_urlsafe(48)
        now = utc_now_naive()
        pending_query = self.db.query(OAuthState).filter(
            OAuthState.provider == normalized_provider,
            OAuthState.tenant_id == tenant_id,
            OAuthState.consumed_at.is_(None),
        )
        if not exclusive_tenant:
            pending_query = pending_query.filter(OAuthState.user_id == user_id)
        pending_query.delete(synchronize_session=False)
        self.db.add(
            OAuthState(
                provider=normalized_provider,
                state_hash=self._hash(state),
                tenant_id=tenant_id,
                user_id=user_id,
                expires_at=now + timedelta(minutes=max(1, expires_minutes)),
            )
        )
        self.db.commit()
        return state

    def consume(self, *, provider: str, state: str) -> OAuthState:
        normalized_provider = provider.strip().lower()
        now = utc_now_naive()
        record = self.db.query(OAuthState).filter(
            OAuthState.provider == normalized_provider,
            OAuthState.state_hash == self._hash(state),
            OAuthState.consumed_at.is_(None),
            OAuthState.expires_at > now,
        ).first()
        if record is None:
            raise InvalidOAuthState(
                "OAuth state geçersiz, süresi dolmuş veya daha önce kullanılmış"
            )

        updated = self.db.query(OAuthState).filter(
            OAuthState.id == record.id,
            OAuthState.consumed_at.is_(None),
        ).update({OAuthState.consumed_at: now}, synchronize_session=False)
        if updated != 1:
            self.db.rollback()
            raise InvalidOAuthState("OAuth state daha önce kullanılmış")

        self.db.commit()
        self.db.refresh(record)
        return record
