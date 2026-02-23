"""Tenant-scoped Google OAuth token storage."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GoogleOAuthToken(Base):
    __tablename__ = "google_oauth_tokens"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_google_oauth_tokens_tenant_provider"),
        Index("ix_google_oauth_tokens_tenant_provider", "tenant_id", "provider"),
        Index("ix_google_oauth_tokens_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="google", index=True)
    scopes_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

