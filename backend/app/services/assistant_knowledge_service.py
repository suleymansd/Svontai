"""Resolve the knowledge visible to a primary assistant."""

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.bot import Bot
from app.models.knowledge import BotKnowledgeItem


class AssistantKnowledgeService:
    """Combines primary and active specialist knowledge without crossing tenants."""

    @staticmethod
    def list_effective(db: Session, bot: Bot) -> list[BotKnowledgeItem]:
        if bot.assistant_type != "primary":
            return (
                db.query(BotKnowledgeItem)
                .filter(BotKnowledgeItem.bot_id == bot.id)
                .order_by(BotKnowledgeItem.created_at.asc())
                .all()
            )

        return (
            db.query(BotKnowledgeItem)
            .join(Bot, Bot.id == BotKnowledgeItem.bot_id)
            .filter(
                Bot.tenant_id == bot.tenant_id,
                Bot.is_active.is_(True),
                Bot.assistant_type.in_(("primary", "specialist")),
            )
            .order_by(
                case((Bot.id == bot.id, 0), else_=1),
                BotKnowledgeItem.created_at.asc(),
            )
            .all()
        )
