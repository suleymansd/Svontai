"""Tenant-scoped browser/PWA push notifications."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now_naive
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Manage subscriptions and deliver free standards-based Web Push messages."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def endpoint_hash(endpoint: str) -> str:
        return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()

    @staticmethod
    def is_configured() -> bool:
        return bool(
            settings.WEB_PUSH_VAPID_PUBLIC_KEY.strip()
            and settings.WEB_PUSH_VAPID_PRIVATE_KEY_B64.strip()
            and settings.WEB_PUSH_SUBJECT.strip()
        )

    def upsert(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: str | None,
    ) -> PushSubscription:
        digest = self.endpoint_hash(endpoint)
        row = self.db.query(PushSubscription).filter(
            PushSubscription.endpoint_hash == digest
        ).first()
        if row is None:
            row = PushSubscription(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint=endpoint,
                endpoint_hash=digest,
                p256dh=p256dh,
                auth=auth,
                user_agent=user_agent,
            )
            self.db.add(row)
        else:
            row.tenant_id = tenant_id
            row.user_id = user_id
            row.endpoint = endpoint
            row.p256dh = p256dh
            row.auth = auth
            row.user_agent = user_agent
            row.enabled = True
            row.failure_count = 0
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_preferences(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        values: dict[str, bool],
    ) -> int:
        rows = self.db.query(PushSubscription).filter(
            PushSubscription.tenant_id == tenant_id,
            PushSubscription.user_id == user_id,
        ).all()
        for row in rows:
            for field, value in values.items():
                setattr(row, field, bool(value))
        self.db.commit()
        return len(rows)

    def disable(self, *, tenant_id: UUID, user_id: UUID, endpoint: str | None = None) -> int:
        query = self.db.query(PushSubscription).filter(
            PushSubscription.tenant_id == tenant_id,
            PushSubscription.user_id == user_id,
        )
        if endpoint:
            query = query.filter(PushSubscription.endpoint_hash == self.endpoint_hash(endpoint))
        rows = query.all()
        for row in rows:
            row.enabled = False
        self.db.commit()
        return len(rows)

    @staticmethod
    def _event_enabled(row: PushSubscription, event_type: str) -> bool:
        mapping = {
            "ai_reply": row.notify_ai_reply,
            "new_lead": row.notify_new_lead,
            "appointment": row.notify_appointment,
            "weekly_report": row.notify_weekly_report,
        }
        return bool(mapping.get(event_type, True))

    @staticmethod
    def _private_key():
        from py_vapid import Vapid

        return Vapid.from_pem(
            base64.b64decode(settings.WEB_PUSH_VAPID_PRIVATE_KEY_B64.encode("ascii"))
        )

    async def send_to_tenant(
        self,
        *,
        tenant_id: UUID,
        event_type: str,
        title: str,
        body: str,
        url: str = "/dashboard",
        tag: str = "svontai-activity",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, int]:
        if not self.is_configured():
            return {"sent": 0, "failed": 0, "disabled": 0}

        rows = self.db.query(PushSubscription).filter(
            PushSubscription.tenant_id == tenant_id,
            PushSubscription.enabled.is_(True),
        ).all()
        rows = [row for row in rows if self._event_enabled(row, event_type)]
        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url,
            "tag": tag,
            "event_type": event_type,
            **(extra or {}),
        })

        sent = 0
        failed = 0
        disabled = 0
        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            logger.error("pywebpush is not installed; Web Push delivery is disabled")
            return {"sent": 0, "failed": len(rows), "disabled": 0}

        private_key = self._private_key()
        for row in rows:
            try:
                await asyncio.to_thread(
                    webpush,
                    subscription_info={
                        "endpoint": row.endpoint,
                        "keys": {"p256dh": row.p256dh, "auth": row.auth},
                    },
                    data=payload,
                    vapid_private_key=private_key,
                    vapid_claims={"sub": settings.WEB_PUSH_SUBJECT},
                    ttl=300,
                )
                row.last_success_at = utc_now_naive()
                row.failure_count = 0
                sent += 1
            except WebPushException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                row.last_failure_at = utc_now_naive()
                row.failure_count = int(row.failure_count or 0) + 1
                failed += 1
                if status_code in {404, 410} or row.failure_count >= 5:
                    row.enabled = False
                    disabled += 1
                logger.warning(
                    "Web Push delivery failed subscription=%s status=%s error=%s",
                    row.id,
                    status_code,
                    exc,
                )
            except Exception as exc:
                row.last_failure_at = utc_now_naive()
                row.failure_count = int(row.failure_count or 0) + 1
                failed += 1
                logger.warning("Web Push delivery failed subscription=%s error=%s", row.id, exc)

        self.db.commit()
        return {"sent": sent, "failed": failed, "disabled": disabled}


async def send_tenant_push_notification(
    *,
    tenant_id: UUID,
    event_type: str,
    title: str,
    body: str,
    url: str = "/dashboard",
    tag: str = "svontai-activity",
    extra: dict[str, Any] | None = None,
) -> None:
    """Background-task entry point with an isolated database session."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        await PushNotificationService(db).send_to_tenant(
            tenant_id=tenant_id,
            event_type=event_type,
            title=title,
            body=body,
            url=url,
            tag=tag,
            extra=extra,
        )
    finally:
        db.close()
