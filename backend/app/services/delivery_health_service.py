"""Payload-free operational signals for external monitoring."""

from datetime import timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.time import utc_now, utc_now_naive
from app.models.message import Message
from app.models.operator_delivery import OperatorDelivery
from app.models.webhook_inbox import WebhookInboxEvent


def delivery_health(db: Session) -> dict[str, str]:
    inbox_blocked = db.query(WebhookInboxEvent.id).filter(or_(
        WebhookInboxEvent.status == "dead_letter",
        and_(WebhookInboxEvent.status.in_(["pending", "retrying", "processing"]),
             WebhookInboxEvent.received_at < utc_now() - timedelta(minutes=10)),
    )).first() is not None
    outbox_blocked = db.query(OperatorDelivery.message_id).filter(or_(
        OperatorDelivery.status == "uncertain",
        and_(OperatorDelivery.status.in_(["queued", "dispatching"]),
             OperatorDelivery.updated_at < utc_now_naive() - timedelta(minutes=5)),
    )).first() is not None
    ai_blocked = db.query(Message.id).filter(
        Message.sender == "user",
        Message.created_at < utc_now_naive() - timedelta(minutes=10),
        Message.raw_payload["reply_delivery"]["status"].as_string().in_(["generating", "dispatching", "uncertain"]),
    ).first() is not None
    return {"webhook_inbox": "attention" if inbox_blocked else "ok",
            "operator_outbox": "attention" if outbox_blocked else "ok",
            "ai_delivery": "attention" if ai_blocked else "ok"}
