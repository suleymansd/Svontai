"""
Compatibility webhook aliases.

Provides /webhooks/whatsapp in addition to /whatsapp/webhook.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.routers.whatsapp_webhook import webhook_events, webhook_verification


router = APIRouter(prefix="/webhooks", tags=["Webhook Alias"])


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
    db: Session = Depends(get_db)
):
    return await webhook_events(request=request, background_tasks=background_tasks, db=db)
