"""Persistent conversational training sessions for tenant assistants."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class AssistantTrainingSession(Base):
    """Stores a reviewable AI-generated specialist proposal before it goes live."""

    __tablename__ = "assistant_training_sessions"
    __table_args__ = (
        Index("ix_assistant_training_sessions_tenant_updated", "tenant_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="collecting", index=True)
    messages_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    proposal_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    specialist_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bots.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )
