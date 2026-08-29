"""Signed, short-lived authorization tokens for the public web widget."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings


class InvalidWidgetSession(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WidgetSession:
    conversation_id: UUID
    bot_id: UUID
    external_user_id: str


def _secret() -> bytes:
    value = settings.API_KEY_HASH_SECRET.strip() or settings.JWT_SECRET_KEY.strip()
    return hmac.new(value.encode("utf-8"), b"svontai-public-widget-session-v1", hashlib.sha256).digest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_widget_session(
    *,
    conversation_id: UUID,
    bot_id: UUID,
    external_user_id: str,
    ttl_seconds: int = 24 * 60 * 60,
) -> str:
    payload = {
        "v": 1,
        "cid": str(conversation_id),
        "bid": str(bot_id),
        "eid": external_user_id,
        "exp": int(time.time()) + ttl_seconds,
    }
    encoded = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _encode(hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_widget_session(token: str) -> WidgetSession:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = _encode(hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, supplied_signature):
            raise InvalidWidgetSession("Geçersiz widget oturumu")
        payload = json.loads(_decode(encoded))
        if payload.get("v") != 1 or int(payload.get("exp", 0)) <= int(time.time()):
            raise InvalidWidgetSession("Widget oturumunun süresi dolmuş")
        external_user_id = str(payload.get("eid") or "")
        if not external_user_id or len(external_user_id) > 255:
            raise InvalidWidgetSession("Geçersiz widget oturumu")
        return WidgetSession(
            conversation_id=UUID(str(payload["cid"])),
            bot_id=UUID(str(payload["bid"])),
            external_user_id=external_user_id,
        )
    except InvalidWidgetSession:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidWidgetSession("Geçersiz widget oturumu") from exc
