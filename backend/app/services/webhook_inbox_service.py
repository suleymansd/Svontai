"""Durable webhook inbox with retry and multi-worker claiming."""

from __future__ import annotations

import hashlib
import socket
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.webhook_inbox import WebhookInboxEvent
from app.models.whatsapp_account import WhatsAppAccount


class WebhookInboxService:
    """Persist provider callbacks before acknowledgement and process them safely."""

    def __init__(self, db: Session, owner: str | None = None):
        self.db = db
        self.owner = owner or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def deduplication_key(provider: str, body: bytes) -> str:
        return hashlib.sha256(provider.encode("utf-8") + b":" + body).hexdigest()

    def enqueue(
        self,
        *,
        provider: str,
        body: bytes,
        payload: dict[str, Any],
        event_type: str,
        tenant_id: uuid.UUID | None = None,
        provider_reference: str | None = None,
    ) -> tuple[WebhookInboxEvent, bool]:
        key = self.deduplication_key(provider, body)
        row = WebhookInboxEvent(
            tenant_id=tenant_id,
            provider=provider,
            provider_reference=provider_reference,
            event_type=event_type,
            deduplication_key=key,
            payload_json=payload,
            max_attempts=max(1, settings.WEBHOOK_INBOX_MAX_ATTEMPTS),
        )
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
            return row, True
        except IntegrityError:
            self.db.rollback()
            existing = self.db.query(WebhookInboxEvent).filter(
                WebhookInboxEvent.provider == provider,
                WebhookInboxEvent.deduplication_key == key,
            ).one()
            return existing, False

    def claim_batch(self, limit: int = 20, lease_seconds: int = 120) -> list[uuid.UUID]:
        now = utc_now()
        rows = self.db.query(WebhookInboxEvent).filter(
            WebhookInboxEvent.status.in_(["pending", "retrying", "processing"]),
            WebhookInboxEvent.available_at <= now,
            (
                WebhookInboxEvent.locked_until.is_(None)
                | (WebhookInboxEvent.locked_until <= now)
            ),
        ).order_by(WebhookInboxEvent.received_at.asc()).with_for_update(skip_locked=True).limit(limit).all()
        claimed: list[uuid.UUID] = []
        for row in rows:
            row.status = "processing"
            row.attempt_count += 1
            row.lock_owner = self.owner
            row.locked_at = now
            row.locked_until = now + timedelta(seconds=max(30, lease_seconds))
            row.updated_at = now
            claimed.append(row.id)
        self.db.commit()
        return claimed

    async def process_claimed(self, event_id: uuid.UUID) -> None:
        row = self.db.query(WebhookInboxEvent).filter(WebhookInboxEvent.id == event_id).first()
        if row is None or row.status != "processing":
            return
        try:
            if row.provider == "meta_cloud":
                from app.api.routers.whatsapp_webhook import process_webhook_event

                await process_webhook_event(row.payload_json, self.db, None)
            elif row.provider == "openwa":
                await self._process_openwa(row)
            else:
                raise ValueError(f"Unsupported webhook inbox provider: {row.provider}")
        except Exception as exc:
            self.db.rollback()
            self.mark_failed(event_id, exc)
            raise
        self.mark_processed(event_id)

    async def _process_openwa(self, row: WebhookInboxEvent) -> None:
        from app.api.routers.whatsapp_webhook import process_openwa_message_event
        from app.services.onboarding_service import OnboardingService

        payload = row.payload_json or {}
        session_id = str(payload.get("sessionId") or row.provider_reference or "")
        event = str(payload.get("event") or row.event_type or "")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        account = self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.provider == "openwa",
            WhatsAppAccount.provider_session_id == session_id,
        ).first()
        if account is None:
            raise LookupError(f"OpenWA account not found for session {session_id}")
        if event in {"session.authenticated", "session.disconnected", "session.status"}:
            OnboardingService(self.db).sync_openwa_webhook_event(account, event, data)
            return
        if event != "message.received":
            return
        await process_openwa_message_event(
            str(account.tenant_id),
            session_id,
            account.display_phone_number or "",
            data,
            payload,
            self.db,
            None,
        )

    def mark_processed(self, event_id: uuid.UUID) -> None:
        row = self.db.query(WebhookInboxEvent).filter(WebhookInboxEvent.id == event_id).first()
        if row is None:
            return
        now = utc_now()
        row.status = "processed"
        row.payload_json = {}
        row.last_error = None
        row.lock_owner = None
        row.locked_at = None
        row.locked_until = None
        row.processed_at = now
        row.updated_at = now
        self.db.commit()

    def mark_failed(self, event_id: uuid.UUID, exc: Exception) -> None:
        row = self.db.query(WebhookInboxEvent).filter(WebhookInboxEvent.id == event_id).first()
        if row is None:
            return
        now = utc_now()
        exhausted = row.attempt_count >= row.max_attempts
        row.status = "dead_letter" if exhausted else "retrying"
        row.available_at = now + timedelta(seconds=min(3600, 15 * (2 ** min(row.attempt_count, 8))))
        row.last_error = str(exc)[:4000]
        row.lock_owner = None
        row.locked_at = None
        row.locked_until = None
        row.updated_at = now
        self.db.commit()
        if exhausted:
            from app.services.system_event_service import SystemEventService

            SystemEventService(self.db).log(
                tenant_id=str(row.tenant_id) if row.tenant_id else None,
                source="webhook_inbox",
                level="error",
                code="WEBHOOK_EVENT_DEAD_LETTERED",
                message="Inbound provider event exhausted automatic retries",
                meta_json={
                    "event_id": str(row.id),
                    "provider": row.provider,
                    "event_type": row.event_type,
                    "attempt_count": row.attempt_count,
                },
            )
