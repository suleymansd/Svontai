"""
Audit log service for recording sensitive actions.
"""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.onboarding import AuditLog

logger = logging.getLogger(__name__)


class AuditLogService:
    """Service for creating audit log entries."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: str,
        tenant_id: UUID | str | None = None,
        user_id: UUID | str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        payload: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> AuditLog | None:
        """Create a new audit log entry."""
        parsed_tenant_id = self._parse_uuid(tenant_id)
        parsed_user_id = self._parse_uuid(user_id)

        try:
            entry = AuditLog(
                tenant_id=parsed_tenant_id,
                user_id=parsed_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                payload_json=payload,
                ip_address=ip_address,
                user_agent=user_agent
            )
            self.db.add(entry)
            self.db.commit()
            self.db.refresh(entry)
            return entry
        except Exception:
            self.db.rollback()
            logger.warning(
                "Audit log write failed",
                extra={
                    "action": action,
                    "tenant_id": str(tenant_id) if tenant_id else None,
                    "user_id": str(user_id) if user_id else None,
                },
                exc_info=True
            )
        return None

    def safe_log(
        self,
        action: str,
        tenant_id: UUID | str | None = None,
        user_id: UUID | str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        payload: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Fire-and-forget style audit logging.

        Never raises; intended for webhook/gateway paths.
        """
        self.log(
            action=action,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def _parse_uuid(value: UUID | str | None) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            return None
