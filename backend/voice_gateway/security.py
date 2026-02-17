import json
import time
import hmac
import hashlib
from typing import Tuple


def sign_payload(payload: dict, secret: str) -> Tuple[str, int]:
    ts = int(time.time())
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    message = f"{ts}.{payload_str}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature, ts

