"""Meter a confirmed AI reply once, in the same transaction as its message."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.automation import AutomationRun
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.subscription import TenantSubscription
from app.services.usage_counter_service import UsageCounterService


def record_delivered_reply(
    db: Session, tenant_id: UUID, reply: Message, *, source_message_id: UUID | None = None,
) -> bool:
    """Caller commits. Text and media answering the same inbound share one unit."""
    db.flush()
    inbound_id = reply.reply_to_external_id
    if not inbound_id and reply.automation_run_id:
        run = db.query(AutomationRun).filter(
            AutomationRun.id == reply.automation_run_id,
            AutomationRun.tenant_id == str(tenant_id),
        ).first()
        inbound_id = run.message_id if run else None

    anchor_id = reply.id
    if source_message_id or inbound_id:
        query = db.query(Message.id).join(Conversation).join(Bot).filter(
            Bot.tenant_id == tenant_id, Message.sender == "user",
            Message.conversation_id == reply.conversation_id,
        )
        query = query.filter(Message.id == source_message_id) if source_message_id else query.filter(Message.external_id == inbound_id)
        source = query.first()
        if source:
            anchor_id = source.id

    anchor = db.query(Message).filter(Message.id == anchor_id).populate_existing().with_for_update().one()
    payload = dict(anchor.raw_payload or {})
    if payload.get("reply_usage"):
        return False

    now = utc_now_naive()
    period = now.strftime("%Y-%m")
    db.execute(update(TenantSubscription).where(
        TenantSubscription.tenant_id == tenant_id,
    ).values(messages_used_this_month=TenantSubscription.messages_used_this_month + 1))
    UsageCounterService(db).increment(tenant_id=tenant_id, message_count=1, period_key=period, commit=False)
    anchor.raw_payload = {**payload, "reply_usage": {
        "period": period, "charged_at": now.isoformat(), "reply_message_id": str(reply.id),
    }}
    db.flush()
    return True
