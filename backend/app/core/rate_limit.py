"""
Simple in-memory rate limiting utilities.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta


class RateLimiter:
    """Basic sliding-window rate limiter."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self.attempts = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Return True if request is allowed."""
        now = datetime.utcnow()
        window_start = now - self.window
        bucket = self.attempts[key]

        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= self.max_attempts:
            return False

        bucket.append(now)
        return True


login_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)
register_rate_limiter = RateLimiter(max_attempts=5, window_seconds=300)
refresh_rate_limiter = RateLimiter(max_attempts=20, window_seconds=300)
