"""
Workspace notes model for internal operations.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkspaceNote(Base):
    """Post-it style notes for each tenant."""

    __tablename__ = "workspace_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    title: Mapped[str] = mapped_column(
        String(140),
        nullable=False
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    color: Mapped[str] = mapped_column(
        String(30),
        default="slate",
        nullable=False
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    position_x: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    position_y: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
