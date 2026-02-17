"""
Temporary debug endpoints (development only).

WARNING: Must not be enabled in production.
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/_debug", tags=["Debug (temp)"])


class WebhookAuthDebugResponse(BaseModel):
    has_username: bool
    has_password: bool
    username_len: int
    password_len: int


@router.get("/webhook-auth", response_model=WebhookAuthDebugResponse)
async def debug_webhook_auth() -> WebhookAuthDebugResponse:
    username = (os.getenv("WEBHOOK_USERNAME") or "").strip()
    password = (os.getenv("WEBHOOK_PASSWORD") or "").strip()

    return WebhookAuthDebugResponse(
        has_username=bool(username),
        has_password=bool(password),
        username_len=len(username) if username else 0,
        password_len=len(password) if password else 0,
    )

