"""External error reporting with a no-op local fallback."""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def configure_observability(service: str) -> bool:
    dsn = settings.SENTRY_DSN.strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.error("Sentry DSN is configured but sentry-sdk is not installed")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=max(0.0, min(1.0, settings.SENTRY_TRACES_SAMPLE_RATE)),
        send_default_pii=False,
        release="svontai@1.0.0",
        server_name=service,
    )
    sentry_sdk.set_tag("service", service)
    return True


def capture_exception(exc: Exception) -> None:
    if not settings.SENTRY_DSN.strip():
        return
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except ImportError:
        return
