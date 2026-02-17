"""
Security layer for Voice Gateway -> SvontAI communication.

We use HMAC-SHA256 signature with timestamp to prevent replay attacks.

Important:
We verify against canonical JSON (sorted keys) so the sender can use stable signing.
"""

import json

from fastapi import Request, HTTPException, status

from app.core.config import settings
from app.core.n8n_security import verify_signature


async def verify_voice_gateway_request_dependency(request: Request) -> dict:
    signature = request.headers.get("X-Voice-Signature")
    timestamp_str = request.headers.get("X-Voice-Timestamp")

    if not signature or not timestamp_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing voice signature headers",
        )

    try:
        timestamp = int(timestamp_str)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid voice timestamp",
        )

    body = await request.body()
    try:
        payload_str = body.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request body encoding",
        )

    # Prefer canonical JSON verification for stability across clients.
    canonical_payload: dict | None = None
    if payload_str.strip():
        try:
            canonical_payload = json.loads(payload_str)
        except json.JSONDecodeError:
            canonical_payload = None

    ok, error_msg = verify_signature(
        canonical_payload if canonical_payload is not None else payload_str,
        signature=signature,
        timestamp=timestamp,
        secret=settings.VOICE_GATEWAY_TO_SVONTAI_SECRET,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Voice request verification failed: {error_msg}",
        )

    return {"verified": True}
