"""
Session service for refresh token rotation.
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.session import UserSession
from app.core.config import settings
from app.core.security import hash_token


class SessionService:
    """Service for user sessions."""

    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        user_id: UUID,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> UserSession:
        """Create a session for a refresh token."""
        now = datetime.utcnow()
        session = UserSession(
            user_id=user_id,
            refresh_token_hash=hash_token(refresh_token),
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def rotate_session(
        self,
        session: UserSession,
        refresh_token: str
    ) -> UserSession:
        """Rotate the refresh token hash for a session."""
        now = datetime.utcnow()
        session.refresh_token_hash = hash_token(refresh_token)
        session.last_used_at = now
        session.expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        self.db.commit()
        self.db.refresh(session)
        return session

    def revoke_session(self, session: UserSession) -> None:
        """Revoke a session."""
        session.revoked_at = datetime.utcnow()
        self.db.commit()
