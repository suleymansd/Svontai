"""
Lead notes model.

Production intent:
- System-of-record for notes linked to a Lead (and optionally Call/Conversation).
- Used by n8n workflows (call summaries, follow-ups) and by panel UI (manual notes).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LeadNote(Base):
    __tablename__ = "lead_notes"
    __table_args__ = (
        Index("ix_lead_notes_tenant_created", "tenant_id", "created_at"),
        Index("ix_lead_notes_tenant_lead", "tenant_id", "lead_id"),
        Index("ix_lead_notes_tenant_call", "tenant_id", "call_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source: Mapped[str] = mapped_column(String(30), nullable=False, default="panel")  # panel|n8n|voice|whatsapp
    note_type: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")  # manual|call_summary|system

    title: Mapped[str] = mapped_column(String(140), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant")
    lead = relationship("Lead")
    call = relationship("Call")
    conversation = relationship("Conversation")
    user = relationship("User")

