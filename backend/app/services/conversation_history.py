"""Bounded history reads without populating or replacing ORM relationships."""

from sqlalchemy import inspect
from sqlalchemy.orm import load_only, object_session

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.operator_delivery import OperatorDelivery


def recent_messages(
    conversation: Conversation, limit: int, *, sender: str | None = None,
) -> list[Message]:
    if limit <= 0:
        return []
    db = object_session(conversation)
    if db is not None and inspect(conversation).persistent:
        query = db.query(Message).options(load_only(
            Message.id, Message.conversation_id, Message.sender,
            Message.content, Message.created_at,
        )).filter(Message.conversation_id == conversation.id)
        # An outbox intent is not conversation history until delivery is confirmed.
        unconfirmed = db.query(OperatorDelivery.message_id).filter(
            OperatorDelivery.message_id == Message.id,
            OperatorDelivery.status != "sent",
        ).exists()
        query = query.filter(~unconfirmed)
        if sender is not None:
            query = query.filter(Message.sender == sender)
        return list(reversed(query.order_by(
            Message.created_at.desc(), Message.id.desc(),
        ).limit(limit).all()))

    # The bot simulator deliberately supplies an in-memory conversation.
    messages = conversation.messages or []
    if sender is not None:
        messages = [message for message in messages if message.sender == sender]
    return messages[-limit:]
