"""Persist before dispatch; reconcile uncertain outcomes explicitly, never resend."""

import logging
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.db import session as db_session
from app.models.conversation import Conversation
from app.models.demo_access import DemoAccess
from app.models.message import Message
from app.models.operator_delivery import OperatorDelivery
from app.models.tenant import Tenant
from app.models.whatsapp_account import WhatsAppAccount
from app.services.whatsapp_gateway_service import whatsapp_gateway_service

logger = logging.getLogger(__name__)


def enqueue_operator_message(db: Session, tenant_id: UUID, conversation: Conversation, content: str, request_id: UUID) -> UUID:
    db.query(Tenant).filter_by(id=tenant_id).with_for_update().one()
    existing = db.query(OperatorDelivery).filter_by(tenant_id=tenant_id, request_id=request_id).first()
    if existing:
        message = db.get(Message, existing.message_id)
        if message.conversation_id != conversation.id or message.content != content:
            raise HTTPException(status_code=409, detail="Bu istek kimligi farkli bir mesaj icin kullanildi.")
        return existing.message_id
    message = Message(conversation_id=conversation.id, sender="operator", content=content)
    db.add(message)
    db.flush()
    db.add(OperatorDelivery(message_id=message.id, tenant_id=tenant_id, request_id=request_id))
    conversation.updated_at = utc_now_naive()
    db.flush()
    return message.id


def delivery_result(db: Session, message_id: UUID) -> dict:
    delivery = db.get(OperatorDelivery, message_id)
    message = db.get(Message, message_id)
    notes = {
        "queued": "Mesaj gonderim kuyrugunda; tekrar gondermeyin.",
        "dispatching": "Gonderim devam ediyor; tekrar gondermeyin.",
        "uncertain": "Teslimat dogrulanamadi. WhatsApp konusmasini kontrol ederek sonucu isaretleyin.",
        "failed": "Mesaj gonderilemedi. Baglantiyi kontrol ettikten sonra yeni bir mesaj gonderebilirsiniz.",
    }
    return {"success": True, "message_id": str(message.id), "sent_at": message.created_at.isoformat(),
            "delivered": delivery.status == "sent", "delivery_status": delivery.status,
            "note": notes.get(delivery.status)}


async def dispatch_operator_message(message_id: UUID) -> None:
    with db_session.SessionLocal() as db:
        row = db.query(OperatorDelivery).filter_by(message_id=message_id).with_for_update().first()
        if row is None or row.status != "queued":
            return
        message = db.get(Message, message_id)
        conversation = db.get(Conversation, message.conversation_id)
        if db.query(DemoAccess.id).filter_by(tenant_id=row.tenant_id).first():
            row.status = "failed"
            db.commit()
            return
        if conversation.source != "whatsapp":
            row.status = "sent"
            db.commit()
            return
        account = db.query(WhatsAppAccount).filter_by(tenant_id=row.tenant_id, is_active=True).first()
        if account is None:
            row.status = "failed"
            db.commit()
            return
        content, recipient = message.content, conversation.external_user_id
        # Detach loaded account fields so network I/O does not retain a DB transaction.
        db.expunge(account)
        token = uuid4().hex
        row.status, row.attempt_token, row.updated_at = "dispatching", token, utc_now_naive()
        db.commit()

    try:
        result = await whatsapp_gateway_service.send_text(account, to=recipient, text=content)
        external_id = result.get("message_id")
        outcome = "sent" if external_id else "uncertain"
    except Exception as exc:
        logger.warning("Operator delivery uncertain (%s)", type(exc).__name__)
        external_id, outcome = None, "uncertain"
    with db_session.SessionLocal() as db:
        row = db.query(OperatorDelivery).filter_by(message_id=message_id).with_for_update().one()
        if row.attempt_token != token or row.status not in {"dispatching", "uncertain"}:
            return
        row.status, row.updated_at = outcome, utc_now_naive()
        if external_id:
            db.get(Message, message_id).external_id = external_id
        db.commit()


def mark_stale_deliveries(db: Session) -> int:
    result = db.execute(update(OperatorDelivery).where(
        OperatorDelivery.status == "dispatching",
        OperatorDelivery.updated_at < utc_now_naive() - timedelta(minutes=5),
    ).values(status="uncertain", updated_at=utc_now_naive()))
    db.commit()
    return result.rowcount
