"""
Minimal TOTP implementation (RFC 6238 compatible) without external dependencies.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote


def generate_secret(length_bytes: int = 20) -> str:
    """
    Generate a base32 secret suitable for authenticator apps.
    """
    raw = secrets.token_bytes(length_bytes)
    return base64.b32encode(raw).decode("utf-8").replace("=", "")


def provisioning_uri(secret: str, account_name: str, issuer: str = "SvontAI") -> str:
    """
    Build otpauth URI for authenticator app setup.
    """
    issuer_q = quote(issuer)
    label = quote(f"{issuer}:{account_name}")
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret}&issuer={issuer_q}&algorithm=SHA1&digits=6&period=30"
    )


def _totp_at(secret: str, for_time: int, period_seconds: int = 30, digits: int = 6) -> str:
    normalized_secret = secret.strip().replace(" ", "").upper()
    secret_padded = normalized_secret + "=" * ((8 - len(normalized_secret) % 8) % 8)
    secret_bytes = base64.b32decode(secret_padded, casefold=True)

    counter = int(for_time // period_seconds)
    counter_bytes = counter.to_bytes(8, "big")

    digest = hmac.new(secret_bytes, counter_bytes, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = (
        ((digest[offset] & 0x7F) << 24)
        | ((digest[offset + 1] & 0xFF) << 16)
        | ((digest[offset + 2] & 0xFF) << 8)
        | (digest[offset + 3] & 0xFF)
    )
    code = binary % (10 ** digits)
    return str(code).zfill(digits)


def generate_code(secret: str, now_ts: int | None = None) -> str:
    """
    Generate current 6-digit TOTP code.
    """
    now = now_ts if now_ts is not None else int(time.time())
    return _totp_at(secret=secret, for_time=now, period_seconds=30, digits=6)


def verify_code(
    secret: str,
    code: str,
    valid_window: int = 1,
    period_seconds: int = 30,
    now_ts: int | None = None,
) -> bool:
    """
    Verify 6-digit TOTP code with ±window support.
    """
    normalized_code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(normalized_code) != 6:
        return False

    now = now_ts if now_ts is not None else int(time.time())
    for delta in range(-valid_window, valid_window + 1):
        check_time = now + (delta * period_seconds)
        expected = _totp_at(secret=secret, for_time=check_time, period_seconds=period_seconds, digits=6)
        if hmac.compare_digest(expected, normalized_code):
            return True
    return False
