"""Tenant-scoped automatic data retention."""

from __future__ import annotations

from datetime import timedelta
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.bot import Bot
from app.models.artifact import Artifact
from app.models.assistant_media import AssistantMediaAsset
from app.models.call import Call
from app.models.conversation import Conversation, ConversationStatus
from app.models.data_retention import DataRetentionPolicy
from app.models.message import Message
from app.models.product_event import ProductEvent
from app.models.system_event import SystemEvent
from app.models.ticket import Ticket
from app.models.usage_log import UsageLog
from app.models.voice_automation import CallIntent, OutboundCallJob
from app.services.artifact_service import ArtifactService


logger = logging.getLogger(__name__)

TERMINAL_CALL_STATUSES = {"completed", "failed", "no_answer", "busy", "cancelled"}
TERMINAL_CALL_INTENT_STATUSES = {"completed", "failed", "skipped"}
TERMINAL_CALL_JOB_STATUSES = {"completed", "failed", "cancelled"}
TERMINAL_TICKET_STATUSES = {"solved", "closed"}


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
            "media_days": policy.media_days,
            "call_data_days": policy.call_data_days,
            "ticket_days": policy.ticket_days,
            "artifact_days": policy.artifact_days,
            "last_run_at": policy.last_run_at,
            "last_result": policy.last_result_json or {},
            "updated_at": policy.updated_at,
        }

    def preview(self, tenant_id: UUID, policy: DataRetentionPolicy | None = None) -> dict[str, int]:
        policy = policy or self.get_or_create(tenant_id)
        now = utc_now_naive()
        conversation_ids = select(Conversation.id).join(Bot).where(Bot.tenant_id == tenant_id)
        media_artifact_ids = select(AssistantMediaAsset.artifact_id).where(
            AssistantMediaAsset.tenant_id == tenant_id
        )
        call_cutoff = now - timedelta(days=policy.call_data_days)
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
            "media_assets": self.db.query(AssistantMediaAsset).filter(
                AssistantMediaAsset.tenant_id == tenant_id,
                AssistantMediaAsset.created_at < now - timedelta(days=policy.media_days),
            ).count(),
            "calls": self.db.query(Call).filter(
                Call.tenant_id == tenant_id,
                Call.status.in_(TERMINAL_CALL_STATUSES),
                Call.created_at < call_cutoff,
            ).count(),
            "voice_jobs": self.db.query(OutboundCallJob).filter(
                OutboundCallJob.tenant_id == tenant_id,
                OutboundCallJob.status.in_(TERMINAL_CALL_JOB_STATUSES),
                OutboundCallJob.created_at < call_cutoff,
            ).count(),
            "voice_intents": self.db.query(CallIntent).filter(
                CallIntent.tenant_id == tenant_id,
                CallIntent.status.in_(TERMINAL_CALL_INTENT_STATUSES),
                CallIntent.created_at < call_cutoff,
            ).count(),
            "solved_tickets": self.db.query(Ticket).filter(
                Ticket.tenant_id == str(tenant_id),
                Ticket.status.in_(TERMINAL_TICKET_STATUSES),
                Ticket.updated_at < now - timedelta(days=policy.ticket_days),
            ).count(),
            "artifacts": self.db.query(Artifact).filter(
                Artifact.tenant_id == tenant_id,
                Artifact.id.notin_(media_artifact_ids),
                Artifact.created_at < now - timedelta(days=policy.artifact_days),
            ).count(),
        }

    def _delete_artifacts(self, artifacts: list[Artifact]) -> tuple[int, int]:
        storage = ArtifactService(self.db)
        deleted = 0
        failures = 0
        for artifact in artifacts:
            try:
                storage.delete_artifact_bytes(artifact)
                media = self.db.query(AssistantMediaAsset).filter(
                    AssistantMediaAsset.artifact_id == artifact.id
                ).first()
                if media is not None:
                    self.db.delete(media)
                self.db.delete(artifact)
                self.db.commit()
                deleted += 1
            except Exception as exc:
                self.db.rollback()
                failures += 1
                logger.warning(
                    "retention artifact delete failed tenant=%s artifact=%s error=%s",
                    artifact.tenant_id,
                    artifact.id,
                    type(exc).__name__,
                )
        return deleted, failures

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
        media_cutoff = now - timedelta(days=policy.media_days)
        artifact_cutoff = now - timedelta(days=policy.artifact_days)
        expired_media_artifacts = self.db.query(Artifact).join(
            AssistantMediaAsset,
            AssistantMediaAsset.artifact_id == Artifact.id,
        ).filter(
            AssistantMediaAsset.tenant_id == tenant_id,
            AssistantMediaAsset.created_at < media_cutoff,
        ).all()
        deleted["media_assets"], deleted["media_delete_failures"] = self._delete_artifacts(
            expired_media_artifacts
        )

        protected_media_artifact_ids = select(AssistantMediaAsset.artifact_id).where(
            AssistantMediaAsset.tenant_id == tenant_id
        )
        expired_artifacts = self.db.query(Artifact).filter(
            Artifact.tenant_id == tenant_id,
            Artifact.id.notin_(protected_media_artifact_ids),
            Artifact.created_at < artifact_cutoff,
        ).all()
        deleted["artifacts"], deleted["artifact_delete_failures"] = self._delete_artifacts(
            expired_artifacts
        )
        artifact_failures = deleted["media_delete_failures"] + deleted["artifact_delete_failures"]
        if artifact_failures:
            raise RuntimeError(
                f"Retention could not delete {artifact_failures} artifact object(s); retry required"
            )

        call_cutoff = now - timedelta(days=policy.call_data_days)
        deleted["voice_jobs"] = self.db.query(OutboundCallJob).filter(
            OutboundCallJob.tenant_id == tenant_id,
            OutboundCallJob.status.in_(TERMINAL_CALL_JOB_STATUSES),
            OutboundCallJob.created_at < call_cutoff,
        ).delete(synchronize_session=False)
        active_intent_ids = select(OutboundCallJob.call_intent_id).where(
            OutboundCallJob.tenant_id == tenant_id,
            OutboundCallJob.call_intent_id.isnot(None),
            OutboundCallJob.status.notin_(TERMINAL_CALL_JOB_STATUSES),
        )
        deleted["voice_intents"] = self.db.query(CallIntent).filter(
            CallIntent.tenant_id == tenant_id,
            CallIntent.status.in_(TERMINAL_CALL_INTENT_STATUSES),
            CallIntent.id.notin_(active_intent_ids),
            CallIntent.created_at < call_cutoff,
        ).delete(synchronize_session=False)
        deleted["calls"] = self.db.query(Call).filter(
            Call.tenant_id == tenant_id,
            Call.status.in_(TERMINAL_CALL_STATUSES),
            Call.created_at < call_cutoff,
        ).delete(synchronize_session=False)
        deleted["solved_tickets"] = self.db.query(Ticket).filter(
            Ticket.tenant_id == str(tenant_id),
            Ticket.status.in_(TERMINAL_TICKET_STATUSES),
            Ticket.updated_at < now - timedelta(days=policy.ticket_days),
        ).delete(synchronize_session=False)
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
