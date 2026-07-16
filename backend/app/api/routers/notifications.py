"""Web Push subscription and preference endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.push_subscription import PushSubscription
from app.models.tenant import Tenant
from app.models.user import User
from app.services.push_notification_service import PushNotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: PushKeys


class NotificationPreferences(BaseModel):
    notify_ai_reply: bool = True
    notify_new_lead: bool = True
    notify_appointment: bool = True
    notify_weekly_report: bool = True


class UnsubscribeRequest(BaseModel):
    endpoint: str | None = None


@router.get("/settings")
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> dict:
    rows = db.query(PushSubscription).filter(
        PushSubscription.tenant_id == current_tenant.id,
        PushSubscription.user_id == current_user.id,
        PushSubscription.enabled.is_(True),
    ).order_by(PushSubscription.updated_at.desc()).all()
    latest = rows[0] if rows else None
    return {
        "configured": PushNotificationService.is_configured(),
        "public_key": settings.WEB_PUSH_VAPID_PUBLIC_KEY if PushNotificationService.is_configured() else "",
        "subscribed": bool(rows),
        "device_count": len(rows),
        "preferences": {
            "notify_ai_reply": latest.notify_ai_reply if latest else True,
            "notify_new_lead": latest.notify_new_lead if latest else True,
            "notify_appointment": latest.notify_appointment if latest else True,
            "notify_weekly_report": latest.notify_weekly_report if latest else True,
        },
    }


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe_notifications(
    payload: PushSubscriptionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"])),
) -> dict:
    row = PushNotificationService(db).upsert(
        tenant_id=current_tenant.id,
        user_id=current_user.id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=request.headers.get("User-Agent"),
    )
    return {"subscribed": True, "subscription_id": str(row.id)}


@router.patch("/settings")
async def update_notification_settings(
    payload: NotificationPreferences,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"])),
) -> dict:
    updated = PushNotificationService(db).update_preferences(
        tenant_id=current_tenant.id,
        user_id=current_user.id,
        values=payload.model_dump(),
    )
    return {"updated": updated, "preferences": payload.model_dump()}


@router.delete("/subscribe")
async def unsubscribe_notifications(
    payload: UnsubscribeRequest,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"])),
) -> dict:
    disabled = PushNotificationService(db).disable(
        tenant_id=current_tenant.id,
        user_id=current_user.id,
        endpoint=payload.endpoint,
    )
    return {"subscribed": False, "disabled": disabled}
