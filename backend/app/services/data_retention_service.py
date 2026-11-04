"""Tenant-scoped automatic data retention."""

from __future__ import annotations

from datetime import timedelta
import logging
from uuid import UUID

from sqlalchemy import and_, inspect as sa_inspect, or_, select
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.bot import Bot
from app.models.artifact import Artifact
from app.models.assistant_media import AssistantMediaAsset
from app.models.appointment import Appointment
from app.models.call import Call, CallSummary, CallTranscript
from app.models.demo_access import DemoAccess
from app.models.lead import Lead
from app.models.lead_note import LeadNote
from app.models.note import WorkspaceNote
from app.models.operator_delivery import OperatorDelivery
from app.models.reply_reservation import ReplyReservation
from app.models.telephony import TelephonyNumber
from app.models.tenant import Tenant
from app.models.conversation import Conversation, ConversationStatus
from app.models.data_retention import DataRetentionPolicy
from app.models.message import Message
from app.models.webhook_inbox import WebhookInboxEvent
from app.models.assistant_training_session import AssistantTrainingSession
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
TERMINAL_DELIVERY_STATUSES = {"sent", "failed"}
# Column names whose values never leave the database in an export.
EXPORT_REDACTED_COLUMN_MARKERS = ("token", "secret", "password", "hash", "api_key", "credential")


class LegalHoldActive(RuntimeError):
    """Raised when a destructive tenant operation is blocked by a legal hold."""


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
            "terminal_webhooks": self.db.query(WebhookInboxEvent).filter(
                WebhookInboxEvent.tenant_id == tenant_id,
                WebhookInboxEvent.status.in_(["processed", "dead_letter"]),
                WebhookInboxEvent.received_at < now - timedelta(days=max(policy.raw_payload_days, policy.system_event_days)),
            ).count(),
            "training_sessions": self.db.query(AssistantTrainingSession).filter(
                AssistantTrainingSession.tenant_id == tenant_id,
                AssistantTrainingSession.updated_at < now - timedelta(days=policy.message_content_days),
            ).count(),
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
            "reply_reservations": self._expired_reply_reservations(tenant_id, policy, now).count(),
            "operator_deliveries": self._expired_operator_deliveries(tenant_id, policy, now).count(),
            "deleted_leads": self._expired_deleted_leads(tenant_id, policy, now).count(),
            "demo_access": self._expired_demo_access(tenant_id, policy, now).count(),
            "artifacts": self.db.query(Artifact).filter(
                Artifact.tenant_id == tenant_id,
                Artifact.id.notin_(media_artifact_ids),
                Artifact.created_at < now - timedelta(days=policy.artifact_days),
            ).count(),
        }

    # -- shared "expired rows" queries -------------------------------------------------

    def _tenant_bot_ids(self, tenant_id: UUID):
        return select(Bot.id).where(Bot.tenant_id == tenant_id)

    def _tenant_lead_filter(self, tenant_id: UUID):
        return or_(Lead.tenant_id == tenant_id, Lead.bot_id.in_(self._tenant_bot_ids(tenant_id)))

    def _expired_reply_reservations(self, tenant_id: UUID, policy: DataRetentionPolicy, now):
        # Reservations drive the monthly reply quota; only clearly past periods are purged.
        return self.db.query(ReplyReservation).filter(
            ReplyReservation.tenant_id == tenant_id,
            ReplyReservation.created_at < now - timedelta(days=policy.usage_log_days),
        )

    def _expired_operator_deliveries(self, tenant_id: UUID, policy: DataRetentionPolicy, now):
        return self.db.query(OperatorDelivery).filter(
            OperatorDelivery.tenant_id == tenant_id,
            OperatorDelivery.status.in_(TERMINAL_DELIVERY_STATUSES),
            OperatorDelivery.updated_at < now - timedelta(days=policy.raw_payload_days),
        )

    def _expired_deleted_leads(self, tenant_id: UUID, policy: DataRetentionPolicy, now):
        return self.db.query(Lead).filter(
            self._tenant_lead_filter(tenant_id),
            Lead.is_deleted.is_(True),
            Lead.deleted_at.isnot(None),
            Lead.deleted_at < now - timedelta(days=policy.message_content_days),
        )

    def _expired_demo_access(self, tenant_id: UUID, policy: DataRetentionPolicy, now):
        cutoff = now - timedelta(days=policy.system_event_days)
        return self.db.query(DemoAccess).filter(
            DemoAccess.tenant_id == tenant_id,
            or_(DemoAccess.expires_at < cutoff, DemoAccess.revoked_at < cutoff),
        )

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
        expired_call_ids = select(Call.id).where(
            Call.tenant_id == tenant_id,
            Call.status.in_(TERMINAL_CALL_STATUSES),
            Call.created_at < call_cutoff,
        )
        deleted["call_transcripts"] = self.db.query(CallTranscript).filter(
            CallTranscript.tenant_id == tenant_id,
            CallTranscript.call_id.in_(expired_call_ids),
        ).delete(synchronize_session=False)
        deleted["call_summaries"] = self.db.query(CallSummary).filter(
            CallSummary.tenant_id == tenant_id,
            CallSummary.call_id.in_(expired_call_ids),
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
        expired_message_ids = select(Message.id).where(
            Message.conversation_id.in_(conversation_ids),
            Message.created_at < now - timedelta(days=policy.message_content_days),
        )
        # Per-message side tables are keyed by message_id; delete them explicitly so the
        # purge does not depend on database-level cascades.
        deleted["reply_reservations"] = self.db.query(ReplyReservation).filter(
            ReplyReservation.tenant_id == tenant_id,
            or_(
                ReplyReservation.message_id.in_(expired_message_ids),
                ReplyReservation.created_at < now - timedelta(days=policy.usage_log_days),
            ),
        ).delete(synchronize_session=False)
        deleted["operator_deliveries"] = self.db.query(OperatorDelivery).filter(
            OperatorDelivery.tenant_id == tenant_id,
            or_(
                OperatorDelivery.message_id.in_(expired_message_ids),
                and_(
                    OperatorDelivery.status.in_(TERMINAL_DELIVERY_STATUSES),
                    OperatorDelivery.updated_at < now - timedelta(days=policy.raw_payload_days),
                ),
            ),
        ).delete(synchronize_session=False)
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

        deleted["terminal_webhooks"] = self.db.query(WebhookInboxEvent).filter(
            WebhookInboxEvent.tenant_id == tenant_id,
            WebhookInboxEvent.status.in_(["processed", "dead_letter"]),
            WebhookInboxEvent.received_at < now - timedelta(days=max(policy.raw_payload_days, policy.system_event_days)),
        ).delete(synchronize_session=False)
        deleted["training_sessions"] = self.db.query(AssistantTrainingSession).filter(
            AssistantTrainingSession.tenant_id == tenant_id,
            AssistantTrainingSession.updated_at < now - timedelta(days=policy.message_content_days),
        ).delete(synchronize_session=False)

        expired_lead_ids = select(Lead.id).where(
            self._tenant_lead_filter(tenant_id),
            Lead.is_deleted.is_(True),
            Lead.deleted_at.isnot(None),
            Lead.deleted_at < now - timedelta(days=policy.message_content_days),
        )
        deleted["deleted_lead_notes"] = self.db.query(LeadNote).filter(
            LeadNote.tenant_id == tenant_id,
            LeadNote.lead_id.in_(expired_lead_ids),
        ).delete(synchronize_session=False)
        deleted["deleted_leads"] = self._expired_deleted_leads(tenant_id, policy, now).delete(
            synchronize_session=False
        )
        deleted["demo_access"] = self._expired_demo_access(tenant_id, policy, now).delete(
            synchronize_session=False
        )

        policy.last_run_at = now
        policy.last_result_json = deleted
        self.db.commit()
        return {"status": "completed", "deleted": deleted, "completed_at": now}

    # -- per-tenant export / erasure ---------------------------------------------------

    @staticmethod
    def _row_to_dict(row) -> dict:
        data: dict = {}
        for attr in sa_inspect(row).mapper.column_attrs:
            name = attr.key
            if any(marker in name.lower() for marker in EXPORT_REDACTED_COLUMN_MARKERS):
                continue
            value = getattr(row, name)
            if isinstance(value, (UUID,)):
                value = str(value)
            elif hasattr(value, "isoformat"):
                value = value.isoformat()
            elif value is not None and not isinstance(value, (str, int, float, bool, dict, list)):
                value = str(value)
            data[name] = value
        return data

    def _tenant_tables(self, tenant_id: UUID) -> list[tuple[str, object]]:
        """Every query holding this tenant's personal data, children before parents."""
        bot_ids = self._tenant_bot_ids(tenant_id)
        conversation_ids = select(Conversation.id).where(Conversation.bot_id.in_(bot_ids))
        return [
            ("reply_reservations", self.db.query(ReplyReservation).filter(ReplyReservation.tenant_id == tenant_id)),
            ("operator_deliveries", self.db.query(OperatorDelivery).filter(OperatorDelivery.tenant_id == tenant_id)),
            ("messages", self.db.query(Message).filter(Message.conversation_id.in_(conversation_ids))),
            ("conversations", self.db.query(Conversation).filter(Conversation.bot_id.in_(bot_ids))),
            ("lead_notes", self.db.query(LeadNote).filter(LeadNote.tenant_id == tenant_id)),
            ("appointments", self.db.query(Appointment).filter(Appointment.tenant_id == tenant_id)),
            ("leads", self.db.query(Lead).filter(self._tenant_lead_filter(tenant_id))),
            ("workspace_notes", self.db.query(WorkspaceNote).filter(WorkspaceNote.tenant_id == tenant_id)),
            ("call_transcripts", self.db.query(CallTranscript).filter(CallTranscript.tenant_id == tenant_id)),
            ("call_summaries", self.db.query(CallSummary).filter(CallSummary.tenant_id == tenant_id)),
            ("voice_jobs", self.db.query(OutboundCallJob).filter(OutboundCallJob.tenant_id == tenant_id)),
            ("voice_intents", self.db.query(CallIntent).filter(CallIntent.tenant_id == tenant_id)),
            ("calls", self.db.query(Call).filter(Call.tenant_id == tenant_id)),
            ("telephony_numbers", self.db.query(TelephonyNumber).filter(TelephonyNumber.tenant_id == tenant_id)),
            ("tickets", self.db.query(Ticket).filter(Ticket.tenant_id == str(tenant_id))),
            ("training_sessions", self.db.query(AssistantTrainingSession).filter(AssistantTrainingSession.tenant_id == tenant_id)),
            ("media_assets", self.db.query(AssistantMediaAsset).filter(AssistantMediaAsset.tenant_id == tenant_id)),
            ("artifacts", self.db.query(Artifact).filter(Artifact.tenant_id == tenant_id)),
            ("webhook_inbox_events", self.db.query(WebhookInboxEvent).filter(WebhookInboxEvent.tenant_id == tenant_id)),
            ("demo_access", self.db.query(DemoAccess).filter(DemoAccess.tenant_id == tenant_id)),
            ("product_events", self.db.query(ProductEvent).filter(ProductEvent.tenant_id == tenant_id)),
            ("usage_logs", self.db.query(UsageLog).filter(UsageLog.tenant_id == tenant_id)),
            ("system_events", self.db.query(SystemEvent).filter(SystemEvent.tenant_id == str(tenant_id))),
        ]

    def export(self, tenant_id: UUID) -> dict:
        """Portable snapshot of every table holding this tenant's personal data."""
        tenant = self.db.get(Tenant, tenant_id)
        policy = self.get_or_create(tenant_id)
        tables = {name: [self._row_to_dict(row) for row in query.all()] for name, query in self._tenant_tables(tenant_id)}
        return {
            "tenant": {"id": str(tenant_id), "name": tenant.name if tenant else None},
            "exported_at": utc_now_naive().isoformat(),
            "legal_hold": policy.legal_hold,
            "tables": tables,
            "counts": {name: len(rows) for name, rows in tables.items()},
        }

    def purge_tenant(self, tenant_id: UUID, *, delete_tenant: bool = True) -> dict[str, int]:
        """Erase every tenant-scoped personal-data row (and optionally the tenant itself).

        Deletes are explicit rather than relying on ON DELETE CASCADE so that tables with
        SET NULL foreign keys (webhook inbox payloads) and message-keyed side tables are
        never left behind. Raises LegalHoldActive while the tenant is under legal hold.
        """
        policy = self.get_or_create(tenant_id)
        if policy.legal_hold:
            raise LegalHoldActive(f"tenant {tenant_id} is under legal hold")

        deleted: dict[str, int] = {}
        artifacts = self.db.query(Artifact).filter(Artifact.tenant_id == tenant_id).all()
        deleted["artifacts"], failures = self._delete_artifacts(artifacts)
        if failures:
            raise RuntimeError(f"Tenant purge could not delete {failures} artifact object(s); retry required")

        for name, query in self._tenant_tables(tenant_id):
            if name in {"artifacts", "media_assets"}:
                continue
            deleted[name] = query.delete(synchronize_session=False)

        if delete_tenant:
            tenant = self.db.get(Tenant, tenant_id)
            if tenant is not None:
                self.db.delete(tenant)
        self.db.commit()
        return deleted
