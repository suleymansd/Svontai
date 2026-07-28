"""Distributed rate limiting with a safe in-process fallback."""

from collections import defaultdict, deque
from datetime import timedelta
import hashlib
import ipaddress
import logging
from threading import Lock
from typing import Iterable

from fastapi import HTTPException, Request, status

from app.core.time import utc_now_naive
from app.core.config import settings

try:
    import redis
except ImportError:  # pragma: no cover - dependency is present in production
    redis = None


logger = logging.getLogger(__name__)

_REDIS_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


class RateLimiter:
    """Rate limiter shared through Redis when configured."""

    def __init__(self, max_attempts: int, window_seconds: int, name: str = "generic") -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.window = timedelta(seconds=window_seconds)
        self.name = name
        self.attempts = defaultdict(deque)
        self._lock = Lock()
        self._redis_client = None
        self._redis_warning_logged = False

    def allow(self, key: str) -> bool:
        """Return True if request is allowed."""
        if settings.RATE_LIMIT_BACKEND == "redis":
            redis_result = self._allow_redis(key)
            if redis_result is not None:
                return redis_result
            if settings.RATE_LIMIT_FAIL_CLOSED:
                return False

        return self._allow_memory(key)

    def _allow_redis(self, key: str) -> bool | None:
        if redis is None:
            self._warn_redis_fallback("redis dependency is unavailable")
            return None
        try:
            if self._redis_client is None:
                self._redis_client = redis.Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
            redis_key = f"{settings.RATE_LIMIT_REDIS_PREFIX}:{self.name}:{digest}"
            current = int(self._redis_client.eval(
                _REDIS_RATE_LIMIT_SCRIPT,
                1,
                redis_key,
                self.window_seconds,
            ))
            return current <= self.max_attempts
        except Exception as exc:
            self._redis_client = None
            self._warn_redis_fallback(str(exc))
            return None

    def _warn_redis_fallback(self, reason: str) -> None:
        if self._redis_warning_logged:
            return
        self._redis_warning_logged = True
        behavior = "rejecting requests" if settings.RATE_LIMIT_FAIL_CLOSED else "using memory fallback"
        logger.error("Redis rate limiter unavailable; %s (%s)", behavior, reason)

    def _allow_memory(self, key: str) -> bool:
        now = utc_now_naive()
        window_start = now - self.window
        with self._lock:
            bucket = self.attempts[key]

            while bucket and bucket[0] < window_start:
                bucket.popleft()

            if len(bucket) >= self.max_attempts:
                return False

            bucket.append(now)
            return True

    def clear(self) -> None:
        """Clear limiter state. Intended for tests and local diagnostics."""
        with self._lock:
            self.attempts.clear()
        self._redis_warning_logged = False


def client_ip(request: Request) -> str:
    """Return a client IP without trusting attacker-supplied forwarding headers."""
    peer = request.client.host if request.client else "unknown"

    if settings.ENVIRONMENT == "prod":
        try:
            peer_address = ipaddress.ip_address(peer)
        except ValueError:
            return "unknown"

        trusted_networks = []
        for value in settings.TRUSTED_PROXY_CIDRS.split(","):
            try:
                trusted_networks.append(ipaddress.ip_network(value.strip(), strict=False))
            except ValueError:
                continue

        def is_trusted(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
            return any(address in network for network in trusted_networks)

        if not is_trusted(peer_address):
            return str(peer_address)

        forwarded_addresses = []
        for value in request.headers.get("X-Forwarded-For", "").split(",")[-20:]:
            try:
                forwarded_addresses.append(ipaddress.ip_address(value.strip()))
            except ValueError:
                continue
        for address in reversed(forwarded_addresses):
            if not is_trusted(address):
                return str(address)

        real_ip = (request.headers.get("X-Real-IP") or "").strip()
        try:
            real_address = ipaddress.ip_address(real_ip)
            if not is_trusted(real_address):
                return str(real_address)
        except ValueError:
            pass
        return str(peer_address)

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def rate_limit_key(request: Request, *parts: object) -> str:
    safe_parts = [str(part).strip().lower() for part in parts if part is not None and str(part).strip()]
    return ":".join([client_ip(request), *safe_parts])


def require_rate_limit(
    limiter: RateLimiter,
    key: str,
    detail: str = "Çok fazla istek. Lütfen daha sonra tekrar deneyin.",
) -> None:
    if not limiter.allow(key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


def clear_rate_limiters(limiters: Iterable[RateLimiter]) -> None:
    for limiter in limiters:
        limiter.clear()


login_rate_limiter = RateLimiter(5, 60, "login")
register_rate_limiter = RateLimiter(5, 300, "register")
refresh_rate_limiter = RateLimiter(20, 300, "refresh")
password_reset_rate_limiter = RateLimiter(3, 300, "password-reset")
email_verification_rate_limiter = RateLimiter(5, 300, "email-verification")
email_confirm_rate_limiter = RateLimiter(20, 300, "email-confirm")
global_ip_rate_limiter = RateLimiter(5000, 60, "global-ip")
webhook_rate_limiter = RateLimiter(300, 60, "webhook")
openwa_webhook_rate_limiter = RateLimiter(300, 60, "openwa-webhook")
whatsapp_connect_rate_limiter = RateLimiter(10, 600, "whatsapp-connect")
whatsapp_send_minute_rate_limiter = RateLimiter(20, 60, "whatsapp-send-minute")
whatsapp_send_hour_rate_limiter = RateLimiter(200, 3600, "whatsapp-send-hour")
public_chat_init_rate_limiter = RateLimiter(30, 60, "public-chat-init")
public_chat_send_rate_limiter = RateLimiter(60, 60, "public-chat-send")
public_lead_rate_limiter = RateLimiter(20, 600, "public-lead")
public_contact_rate_limiter = RateLimiter(5, 600, "public-contact")
assistant_rate_limiter = RateLimiter(60, 60, "assistant")
tool_run_rate_limiter = RateLimiter(60, 60, "tool-run")
voice_test_call_rate_limiter = RateLimiter(10, 600, "voice-test-call")
