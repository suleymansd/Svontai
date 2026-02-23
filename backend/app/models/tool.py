"""Tool catalog model."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    required_plan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    coming_soon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    input_schema_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_schema_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    required_integrations_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    n8n_workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
