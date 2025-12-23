"""
Bot settings model for AI configuration and behavior customization.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResponseTone(str, Enum):
    """Response tone options."""
    FORMAL = "formal"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    CASUAL = "casual"


class EmojiUsage(str, Enum):
    """Emoji usage levels."""
    OFF = "off"
    LIGHT = "light"
    NORMAL = "normal"
    HEAVY = "heavy"


class BotSettings(Base):
    """Bot settings for AI behavior configuration."""
    
    __tablename__ = "bot_settings"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    bot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    # AI Behavior
    response_tone: Mapped[str] = mapped_column(
        String(20),
        default=ResponseTone.FRIENDLY.value,
        nullable=False
    )
    emoji_usage: Mapped[str] = mapped_column(
        String(10),
        default=EmojiUsage.LIGHT.value,
        nullable=False
    )
    max_response_length: Mapped[int] = mapped_column(
        Integer,
        default=500,
        nullable=False
    )
    # Memory settings
    memory_window: Mapped[int] = mapped_column(
        Integer,
        default=10,  # Number of messages to remember
        nullable=False
    )
    # Safety settings
    enable_guardrails: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    fallback_message: Mapped[str] = mapped_column(
        Text,
        default="Üzgünüm, bu konuda size yardımcı olamıyorum. Lütfen bizimle iletişime geçin.",
        nullable=False
    )
    uncertainty_threshold: Mapped[float] = mapped_column(
        default=0.7,  # Confidence threshold for redirecting to human
        nullable=False
    )
    # Redirect settings
    human_handoff_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    human_handoff_message: Mapped[str] = mapped_column(
        Text,
        default="Sizi bir müşteri temsilcimize bağlıyorum. Lütfen bekleyin.",
        nullable=False
    )
    # Rate limiting
    rate_limit_per_minute: Mapped[int] = mapped_column(
        Integer,
        default=20,
        nullable=False
    )
    rate_limit_per_hour: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False
    )
    # Custom instructions
    system_prompt_override: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    # Prohibited topics (JSON array)
    prohibited_topics: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False
    )
    # Extra settings
    extra_settings: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
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
    
    # Relationships
    bot: Mapped["Bot"] = relationship(
        "Bot",
        back_populates="settings"
    )
    
    def __repr__(self) -> str:
        return f"<BotSettings {self.bot_id}>"


# Default settings template
DEFAULT_BOT_SETTINGS = {
    "response_tone": ResponseTone.FRIENDLY.value,
    "emoji_usage": EmojiUsage.LIGHT.value,
    "max_response_length": 500,
    "memory_window": 10,
    "enable_guardrails": True,
    "uncertainty_threshold": 0.7,
    "human_handoff_enabled": True,
    "rate_limit_per_minute": 20,
    "rate_limit_per_hour": 100,
    "prohibited_topics": [
        "illegal activities",
        "violence",
        "adult content"
    ]
}

