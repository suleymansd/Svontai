import base64
import hashlib
import hmac
import json
import time
from typing import Tuple


def dump_canonical_json(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def sign_payload(payload: dict, secret: str) -> Tuple[str, int, str]:
    ts = int(time.time())
    payload_str = dump_canonical_json(payload)
    message = f"{ts}.{payload_str}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature, ts, payload_str


def sign_websocket_session(payload: dict, secret: str, timestamp: int | None = None) -> Tuple[str, int]:
    """Sign the immutable identity of a ConversationRelay WebSocket session."""
    ts = int(timestamp or time.time())
    message = f"{ts}.{dump_canonical_json(payload)}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature, ts


def verify_websocket_session(
    payload: dict,
    signature: str,
    timestamp: int,
    secret: str,
    ttl_seconds: int,
) -> bool:
    now = int(time.time())
    if not signature or timestamp > now + 30 or now - timestamp > max(60, ttl_seconds):
        return False
    expected, _ = sign_websocket_session(payload, secret, timestamp)
    return hmac.compare_digest(expected, signature)


def verify_twilio_webhook_signature(
    url: str,
    form_items: list[tuple[str, str]],
    signature: str,
    auth_token: str,
) -> bool:
    """Verify Twilio's HMAC-SHA1 webhook signature without adding the Twilio SDK."""
    if not signature or not auth_token:
        return False
    message = url + "".join(
        f"{key}{value}"
        for key, value in sorted(form_items, key=lambda item: (item[0], item[1]))
    )
    expected = base64.b64encode(
        hmac.new(auth_token.encode("utf-8"), message.encode("utf-8"), hashlib.sha1).digest()
    ).decode("ascii")
    return hmac.compare_digest(expected, signature)
