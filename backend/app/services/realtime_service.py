"""Redis-backed tenant realtime event fan-out."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.config import settings
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.message import Message

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None


logger = logging.getLogger(__name__)
_redis_client = None
_redis_warning_logged = False


def realtime_channel(tenant_id: object) -> str:
    return f"smartwa:realtime:{tenant_id}"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _publish(tenant_id: str, payload: dict[str, Any]) -> None:
    global _redis_client, _redis_warning_logged
    if settings.RATE_LIMIT_BACKEND != "redis" or redis is None:
        return
    try:
        if _redis_client is None:
            _redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        _redis_client.publish(
            realtime_channel(tenant_id),
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
        )
    except Exception as exc:  # pragma: no cover - depends on external Redis
        _redis_client = None
        if not _redis_warning_logged:
            _redis_warning_logged = True
            logger.error("Realtime Redis publish unavailable: %s", exc)


@event.listens_for(SQLAlchemySession, "after_flush")
def _collect_realtime_changes(session: SQLAlchemySession, flush_context: object) -> None:
    del flush_context
    pending: list[tuple[str, dict[str, Any]]] = session.info.setdefault("realtime_events", [])
    connection = session.connection()

    for obj in session.new:
        if isinstance(obj, Message):
            tenant_id = connection.execute(
                select(Bot.tenant_id)
                .join(Conversation, Conversation.bot_id == Bot.id)
                .where(Conversation.id == obj.conversation_id)
            ).scalar_one_or_none()
            if tenant_id:
                pending.append((
                    str(tenant_id),
                    {
                        "type": "message.created",
                        "conversation_id": str(obj.conversation_id),
                        "message_id": str(obj.id),
                        "sender": obj.sender,
                        "created_at": _serialize_value(obj.created_at),
                    },
                ))
        elif isinstance(obj, Conversation):
            tenant_id = connection.execute(
                select(Bot.tenant_id).where(Bot.id == obj.bot_id)
            ).scalar_one_or_none()
            if tenant_id:
                pending.append((
                    str(tenant_id),
                    {
                        "type": "conversation.created",
                        "conversation_id": str(obj.id),
                        "updated_at": _serialize_value(obj.updated_at),
                    },
                ))

    for obj in session.dirty:
        if not isinstance(obj, Conversation) or not session.is_modified(obj, include_collections=False):
            continue
        tenant_id = connection.execute(
            select(Bot.tenant_id).where(Bot.id == obj.bot_id)
        ).scalar_one_or_none()
        if tenant_id:
            pending.append((
                str(tenant_id),
                {
                    "type": "conversation.updated",
                    "conversation_id": str(obj.id),
                    "status": obj.status,
                    "updated_at": _serialize_value(obj.updated_at),
                },
            ))


@event.listens_for(SQLAlchemySession, "after_commit")
def _publish_realtime_changes(session: SQLAlchemySession) -> None:
    seen: set[tuple[str, str, str]] = set()
    for tenant_id, payload in session.info.pop("realtime_events", []):
        key = (tenant_id, str(payload.get("type")), str(payload.get("message_id") or payload.get("conversation_id")))
        if key in seen:
            continue
        seen.add(key)
        _publish(tenant_id, payload)


@event.listens_for(SQLAlchemySession, "after_rollback")
def _discard_realtime_changes(session: SQLAlchemySession) -> None:
    session.info.pop("realtime_events", None)
