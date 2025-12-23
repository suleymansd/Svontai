"""
Knowledge base model for bot training data.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BotKnowledgeItem(Base):
    """Knowledge item model for Q&A pairs."""
    
    __tablename__ = "bot_knowledge_items"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    bot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    bot: Mapped["Bot"] = relationship(
        "Bot",
        back_populates="knowledge_items"
    )
    
    def __repr__(self) -> str:
        return f"<BotKnowledgeItem {self.title}>"

