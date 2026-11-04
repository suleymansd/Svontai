"""External error reporting with a no-op local fallback."""

from __future__ import annotations

import logging
import os
import subprocess

from app.core.config import settings

logger = logging.getLogger(__name__)

RELEASE_ENV_VARS = (
    "GIT_COMMIT",
    "GIT_COMMIT_SHA",
    "RAILWAY_GIT_COMMIT_SHA",
    "SOURCE_COMMIT",
    "SOURCE_VERSION",
    "GIT_SHA",
)


def resolve_commit_sha() -> str | None:
    """Return the deployed commit from the platform environment, else from git."""
    for name in RELEASE_ENV_VARS:
        value = str(os.getenv(name) or "").strip()
        if value:
            return value[:64]
    try:
        completed = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = completed.stdout.strip()
    return sha[:64] if completed.returncode == 0 and sha else None


def resolve_release(service: str = "svontai") -> str:
    """Sentry release tag: ``svontai@<commit sha>`` or ``svontai@unknown``."""
    return f"{service}@{resolve_commit_sha() or 'unknown'}"


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
        release=resolve_release(),
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
