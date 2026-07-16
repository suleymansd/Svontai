"""Simple in-memory rate limiting utilities."""

from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock
from typing import Iterable

from fastapi import HTTPException, Request, status

from app.core.time import utc_now_naive


class RateLimiter:
    """Basic sliding-window rate limiter."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self.attempts = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        """Return True if request is allowed."""
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


def client_ip(request: Request) -> str:
    """Return the best-effort public client IP behind trusted platform proxies."""
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


login_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)
register_rate_limiter = RateLimiter(max_attempts=5, window_seconds=300)
refresh_rate_limiter = RateLimiter(max_attempts=20, window_seconds=300)
password_reset_rate_limiter = RateLimiter(max_attempts=3, window_seconds=300)
email_verification_rate_limiter = RateLimiter(max_attempts=5, window_seconds=300)
email_confirm_rate_limiter = RateLimiter(max_attempts=20, window_seconds=300)
global_ip_rate_limiter = RateLimiter(max_attempts=5000, window_seconds=60)
webhook_rate_limiter = RateLimiter(max_attempts=300, window_seconds=60)
openwa_webhook_rate_limiter = RateLimiter(max_attempts=300, window_seconds=60)
whatsapp_connect_rate_limiter = RateLimiter(max_attempts=10, window_seconds=600)
whatsapp_send_minute_rate_limiter = RateLimiter(max_attempts=20, window_seconds=60)
whatsapp_send_hour_rate_limiter = RateLimiter(max_attempts=200, window_seconds=3600)
public_chat_init_rate_limiter = RateLimiter(max_attempts=30, window_seconds=60)
public_chat_send_rate_limiter = RateLimiter(max_attempts=60, window_seconds=60)
public_lead_rate_limiter = RateLimiter(max_attempts=20, window_seconds=600)
assistant_rate_limiter = RateLimiter(max_attempts=60, window_seconds=60)
tool_run_rate_limiter = RateLimiter(max_attempts=60, window_seconds=60)
voice_test_call_rate_limiter = RateLimiter(max_attempts=10, window_seconds=600)
