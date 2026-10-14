"""Durable reply ownership and ambiguous-delivery protection on inbound messages.

Provider sends are not transactional. A crash after dispatch must be reviewed,
not automatically resent, unless the provider supports an idempotency key.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.time import utc_now_naive
from app.db import session as db_session
from app.models.message import Message
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.services.reply_quota_service import lock_subscription, release_reply


class ReplyDeliveryUncertain(RuntimeError):
    pass


def can_reconcile_reply(message: Message) -> bool:
    state = (message.raw_payload or {}).get("reply_delivery", {})
    if state.get("status") not in {"dispatching", "uncertain"}:
        return False
    try:
        changed = datetime.fromisoformat(state["updated_at"]) if state.get("updated_at") else message.created_at
        if changed.tzinfo:
            changed = changed.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError, AttributeError):
        return False
    return changed < utc_now_naive() - timedelta(minutes=5)


class ReplyDeliveryGuard:
    def __init__(self, conversation_id, external_id):
        self.conversation_id = conversation_id
        self.external_id = external_id
        self.owner = uuid4().hex

    def _row(self, db):
        return db.query(Message).filter(
            Message.conversation_id == self.conversation_id,
            Message.external_id == self.external_id,
            Message.sender == "user",
        ).populate_existing().with_for_update().one()

    def _lock_tenant(self, db):
        tenant_id = db.query(Bot.tenant_id).join(Conversation).filter(Conversation.id == self.conversation_id).scalar()
        if tenant_id:
            lock_subscription(db, tenant_id)
        return tenant_id

    def claim(self) -> bool:
        with db_session.SessionLocal() as db:
            row = self._row(db)
            state = (row.raw_payload or {}).get("reply_delivery", {})
            if state.get("status") == "completed":
                return False
            if state.get("status") in {"dispatching", "uncertain"}:
                raise ReplyDeliveryUncertain("Reply delivery needs reconciliation; automatic resend blocked")
            if state.get("status") == "generating" and state.get("expires_at", "") > utc_now_naive().isoformat():
                raise RuntimeError("Reply already claimed by another worker")
            row.raw_payload = {**(row.raw_payload or {}), "reply_delivery": {
                "status": "generating", "owner": self.owner,
                "expires_at": (utc_now_naive() + timedelta(minutes=5)).isoformat(),
            }}
            db.commit()
            return True

    def set_status(self, status: str) -> None:
        with db_session.SessionLocal() as db:
            tenant_id = self._lock_tenant(db)
            row = self._row(db)
            state = (row.raw_payload or {}).get("reply_delivery", {})
            if state.get("owner") != self.owner:
                raise RuntimeError("Reply lease ownership lost")
            if status == "dispatching" and state.get("expires_at", "") <= utc_now_naive().isoformat():
                raise RuntimeError("Reply lease expired before dispatch")
            if status == "completed" and state.get("status") == "generating":
                release_reply(db, tenant_id, row.id)
            row.raw_payload = {**(row.raw_payload or {}), "reply_delivery": {
                **state, "status": status, "updated_at": utc_now_naive().isoformat(),
            }}
            db.commit()

    def prepare(self, text: str, media_asset_id: str | None = None) -> None:
        with db_session.SessionLocal() as db:
            row = self._row(db)
            state = (row.raw_payload or {}).get("reply_delivery", {})
            if state.get("owner") != self.owner or state.get("status") != "generating":
                raise RuntimeError("Reply preparation ownership lost")
            row.raw_payload = {**(row.raw_payload or {}), "reply_delivery": {
                **state, "prepared_reply": {"text": text, "media_asset_id": media_asset_id},
            }}
            db.commit()

    def failed(self) -> None:
        with db_session.SessionLocal() as db:
            tenant_id = self._lock_tenant(db)
            row = self._row(db)
            state = (row.raw_payload or {}).get("reply_delivery", {})
            if state.get("owner") != self.owner or state.get("status") == "completed":
                return
            status = "uncertain" if state.get("status") in {"dispatching", "uncertain"} else "retrying"
            if status == "retrying":
                release_reply(db, tenant_id, row.id)
            row.raw_payload = {**(row.raw_payload or {}), "reply_delivery": {**state, "status": status}}
            db.commit()
