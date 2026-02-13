"""Service for creating system events."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.system_event import SystemEvent
from app.models.incident import Incident


class SystemEventService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        *,
        tenant_id: str | None,
        source: str,
        level: str,
        code: str,
        message: str,
        meta_json: dict | None = None,
        correlation_id: str | None = None,
    ) -> SystemEvent:
        event = SystemEvent(
            tenant_id=tenant_id,
            source=source,
            level=level,
            code=code,
            message=message,
            meta_json=meta_json,
            correlation_id=correlation_id,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        self._maybe_create_incident(event)
        return event

    def _maybe_create_incident(self, event: SystemEvent) -> None:
        if event.level != "error":
            return

        window_start = datetime.utcnow() - timedelta(minutes=10)
        recent_count = self.db.query(SystemEvent).filter(
            SystemEvent.code == event.code,
            SystemEvent.created_at >= window_start,
            SystemEvent.tenant_id == event.tenant_id
        ).count()

        if recent_count < 5:
            return

        title = f"{event.code} spike detected"
        existing = self.db.query(Incident).filter(
            Incident.title == title,
            Incident.status == "open",
            Incident.tenant_id == event.tenant_id
        ).first()

        if existing:
            return

        incident = Incident(
            tenant_id=event.tenant_id,
            title=title,
            severity="sev2",
            status="open",
        )
        self.db.add(incident)
        self.db.commit()
