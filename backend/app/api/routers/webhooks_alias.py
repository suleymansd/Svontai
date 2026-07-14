"""
Compatibility webhook aliases.

Provides /webhooks/whatsapp in addition to /whatsapp/webhook.
"""

import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.api.routers.whatsapp_webhook import webhook_events, webhook_verification


router = APIRouter(prefix="/webhooks", tags=["Webhook Alias"])

def _get_webhook_credentials() -> tuple[str, str]:
    username = (settings.WEBHOOK_USERNAME or "").strip()
    password = (settings.WEBHOOK_PASSWORD or "").strip()
    return username, password

_basic_security = HTTPBasic(auto_error=False)


def _verify_webhook_basic_auth(
    credentials: HTTPBasicCredentials | None = Depends(_basic_security),
) -> None:
    username = credentials.username if credentials else ""
    password = credentials.password if credentials else ""

    expected_username, expected_password = _get_webhook_credentials()
    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook credentials are not configured",
        )
    username_ok = secrets.compare_digest(username or "", expected_username)
    password_ok = secrets.compare_digest(password or "", expected_password)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get("/whatsapp")
async def whatsapp_verify_alias(
    request: Request,
    db: Session = Depends(get_db)
):
    return await webhook_verification(request=request, db=db)


@router.post("/whatsapp")
async def whatsapp_events_alias(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_webhook_basic_auth),
):
    return await webhook_events(request=request, background_tasks=background_tasks, db=db)
