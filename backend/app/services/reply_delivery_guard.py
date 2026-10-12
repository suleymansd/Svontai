"""Durable reply ownership and ambiguous-delivery protection on inbound messages.

Provider sends are not transactional. A crash after dispatch must be reviewed,
not automatically resent, unless the provider supports an idempotency key.
"""

from datetime import timedelta
from uuid import uuid4

from app.core.time import utc_now_naive
from app.db import session as db_session
from app.models.message import Message


class ReplyDeliveryUncertain(RuntimeError):
    pass


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
            row = self._row(db)
            state = (row.raw_payload or {}).get("reply_delivery", {})
            if state.get("owner") != self.owner:
                raise RuntimeError("Reply lease ownership lost")
            if status == "dispatching" and state.get("expires_at", "") <= utc_now_naive().isoformat():
                raise RuntimeError("Reply lease expired before dispatch")
            row.raw_payload = {**(row.raw_payload or {}), "reply_delivery": {
                **state, "status": status, "updated_at": utc_now_naive().isoformat(),
            }}
            db.commit()

    def failed(self) -> None:
        with db_session.SessionLocal() as db:
            row = self._row(db)
            state = (row.raw_payload or {}).get("reply_delivery", {})
            if state.get("owner") != self.owner or state.get("status") == "completed":
                return
            status = "uncertain" if state.get("status") in {"dispatching", "uncertain"} else "retrying"
            row.raw_payload = {**(row.raw_payload or {}), "reply_delivery": {**state, "status": status}}
            db.commit()
