"""Tenant-scoped automatic data retention."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationStatus
from app.models.data_retention import DataRetentionPolicy
from app.models.message import Message
from app.models.product_event import ProductEvent
from app.models.system_event import SystemEvent
from app.models.usage_log import UsageLog


class DataRetentionService:
    """Apply bounded, auditable deletion rules for a single tenant."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, tenant_id: UUID) -> DataRetentionPolicy:
        policy = self.db.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.tenant_id == tenant_id
        ).first()
        if policy is None:
            policy = DataRetentionPolicy(tenant_id=tenant_id)
            self.db.add(policy)
            self.db.commit()
            self.db.refresh(policy)
        return policy

    @staticmethod
    def serialize(policy: DataRetentionPolicy) -> dict:
        return {
            "tenant_id": str(policy.tenant_id),
            "enabled": policy.enabled,
            "legal_hold": policy.legal_hold,
            "message_content_days": policy.message_content_days,
            "raw_payload_days": policy.raw_payload_days,
            "product_analytics_days": policy.product_analytics_days,
            "usage_log_days": policy.usage_log_days,
            "system_event_days": policy.system_event_days,
            "last_run_at": policy.last_run_at,
            "last_result": policy.last_result_json or {},
            "updated_at": policy.updated_at,
        }

    def preview(self, tenant_id: UUID, policy: DataRetentionPolicy | None = None) -> dict[str, int]:
        policy = policy or self.get_or_create(tenant_id)
        now = utc_now_naive()
        conversation_ids = select(Conversation.id).join(Bot).where(Bot.tenant_id == tenant_id)
        return {
            "message_content": self.db.query(Message).filter(
                Message.conversation_id.in_(conversation_ids),
                Message.created_at < now - timedelta(days=policy.message_content_days),
            ).count(),
            "raw_payloads": self.db.query(Message).filter(
                Message.conversation_id.in_(conversation_ids),
                Message.raw_payload.isnot(None),
                Message.created_at < now - timedelta(days=policy.raw_payload_days),
            ).count(),
            "product_events": self.db.query(ProductEvent).filter(
                ProductEvent.tenant_id == tenant_id,
                ProductEvent.occurred_at < now - timedelta(days=policy.product_analytics_days),
            ).count(),
            "usage_logs": self.db.query(UsageLog).filter(
                UsageLog.tenant_id == tenant_id,
                UsageLog.created_at < now - timedelta(days=policy.usage_log_days),
            ).count(),
            "system_events": self.db.query(SystemEvent).filter(
                SystemEvent.tenant_id == str(tenant_id),
                SystemEvent.created_at < now - timedelta(days=policy.system_event_days),
            ).count(),
        }

    def run(self, tenant_id: UUID, *, force: bool = False) -> dict:
        policy = self.get_or_create(tenant_id)
        if not policy.enabled:
            return {"status": "disabled", "deleted": {}}
        if policy.legal_hold:
            return {"status": "legal_hold", "deleted": {}}
        now = utc_now_naive()
        if not force and policy.last_run_at and policy.last_run_at > now - timedelta(hours=20):
            return {"status": "not_due", "deleted": policy.last_result_json or {}}

        conversation_ids = select(Conversation.id).join(Bot).where(Bot.tenant_id == tenant_id)
        deleted: dict[str, int] = {}
        deleted["raw_payloads"] = self.db.query(Message).filter(
            Message.conversation_id.in_(conversation_ids),
            Message.raw_payload.isnot(None),
            Message.created_at < now - timedelta(days=policy.raw_payload_days),
        ).update({Message.raw_payload: None}, synchronize_session=False)
        deleted["messages"] = self.db.query(Message).filter(
            Message.conversation_id.in_(conversation_ids),
            Message.created_at < now - timedelta(days=policy.message_content_days),
        ).delete(synchronize_session=False)
        closed_conversation_ids = select(Conversation.id).join(Bot).where(
            Bot.tenant_id == tenant_id,
            Conversation.status == ConversationStatus.CLOSED.value,
            Conversation.updated_at < now - timedelta(days=policy.message_content_days),
        )
        deleted["closed_conversations"] = self.db.query(Conversation).filter(
            Conversation.id.in_(closed_conversation_ids)
        ).delete(synchronize_session=False)
        deleted["product_events"] = self.db.query(ProductEvent).filter(
            ProductEvent.tenant_id == tenant_id,
            ProductEvent.occurred_at < now - timedelta(days=policy.product_analytics_days),
        ).delete(synchronize_session=False)
        deleted["usage_logs"] = self.db.query(UsageLog).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at < now - timedelta(days=policy.usage_log_days),
        ).delete(synchronize_session=False)
        deleted["system_events"] = self.db.query(SystemEvent).filter(
            SystemEvent.tenant_id == str(tenant_id),
            SystemEvent.created_at < now - timedelta(days=policy.system_event_days),
        ).delete(synchronize_session=False)

        policy.last_run_at = now
        policy.last_result_json = deleted
        self.db.commit()
        return {"status": "completed", "deleted": deleted, "completed_at": now}
