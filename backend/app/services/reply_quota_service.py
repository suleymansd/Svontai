"""Serialize quota reservations and metering on the tenant subscription row.

An ambiguous send retains its reservation: releasing on a timeout can overspend
quota while a provider is still processing the request. Caller owns the commit.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.reply_reservation import ReplyReservation
from app.models.subscription import TenantSubscription


def lock_subscription(db: Session, tenant_id: UUID) -> TenantSubscription | None:
    subscription = db.query(TenantSubscription).filter_by(tenant_id=tenant_id).populate_existing().with_for_update().first()
    now = utc_now_naive()
    if subscription and subscription.usage_reset_at.strftime("%Y-%m") != now.strftime("%Y-%m"):
        subscription.messages_used_this_month = 0
        subscription.usage_reset_at = now
        db.flush()
    return subscription


def reserve_reply(db: Session, tenant_id: UUID, message_id: UUID) -> tuple[bool, str]:
    subscription = lock_subscription(db, tenant_id)
    if not subscription or not subscription.is_active():
        return False, "Abonelik aktif degil."
    source = db.query(Message).join(Conversation).join(Bot).filter(
        Message.id == message_id, Message.sender == "user", Bot.tenant_id == tenant_id,
    ).first()
    if not source:
        return False, "Mesaj bulunamadi."
    reservation = db.get(ReplyReservation, message_id)
    period = utc_now_naive().strftime("%Y-%m")
    if reservation and reservation.tenant_id != tenant_id:
        return False, "Mesaj bulunamadi."
    if (source.raw_payload or {}).get("reply_usage"):
        return True, "Already metered"
    if reservation and reservation.state == "reserved" and reservation.period == period:
        return True, "Reserved"
    held = db.query(ReplyReservation).filter_by(tenant_id=tenant_id, period=period, state="reserved").count()
    if subscription.messages_used_this_month + held >= subscription.plan.message_limit:
        return False, "Aylik mesaj haklariniz kullanildi veya devam eden islemlere ayrildi."
    if reservation is None:
        reservation = ReplyReservation(message_id=message_id, tenant_id=tenant_id, period=period)
        db.add(reservation)
    reservation.period = period
    reservation.state = "reserved"
    db.flush()
    return True, "Reserved"


def release_reply(db: Session, tenant_id: UUID, message_id: UUID) -> None:
    lock_subscription(db, tenant_id)
    reservation = db.get(ReplyReservation, message_id)
    if reservation and reservation.tenant_id == tenant_id and reservation.state == "reserved":
        reservation.state = "released"
        db.flush()
