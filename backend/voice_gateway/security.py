import json
import time
import hmac
import hashlib
from typing import Tuple


def dump_canonical_json(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def sign_payload(payload: dict, secret: str) -> Tuple[str, int, str]:
    ts = int(time.time())
    payload_str = dump_canonical_json(payload)
    message = f"{ts}.{payload_str}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature, ts, payload_str
