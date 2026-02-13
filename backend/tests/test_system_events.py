from unittest.mock import MagicMock

from app.models.system_event import SystemEvent
from app.services.system_event_service import SystemEventService


def test_incident_created_on_spike():
    db = MagicMock()

    event_query = MagicMock()
    event_query.filter.return_value = event_query
    event_query.count.return_value = 5

    incident_query = MagicMock()
    incident_query.filter.return_value = incident_query
    incident_query.first.return_value = None

    db.query.side_effect = [event_query, incident_query]

    service = SystemEventService(db)
    event = SystemEvent(
        tenant_id="tenant-1",
        source="test",
        level="error",
        code="TEST_SPIKE",
        message="Spike detected"
    )

    service._maybe_create_incident(event)

    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_no_incident_for_non_error():
    db = MagicMock()
    service = SystemEventService(db)
    event = SystemEvent(
        tenant_id="tenant-1",
        source="test",
        level="info",
        code="INFO",
        message="All good"
    )

    service._maybe_create_incident(event)

    db.query.assert_not_called()
