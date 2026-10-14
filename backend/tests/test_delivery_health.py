from datetime import timedelta
from uuid import uuid4

from tests.test_reliability_regressions import workspace  # noqa: F401


def test_stalled_work_is_visible_without_disclosing_payloads(client, workspace):
    from app.core.time import utc_now, utc_now_naive
    from app.db.session import SessionLocal
    from app.models.message import Message
    from app.models.operator_delivery import OperatorDelivery
    from app.models.webhook_inbox import WebhookInboxEvent
    from app.services.delivery_health_service import delivery_health
    _, tenant_id, _, conversation_id = workspace
    with SessionLocal() as db:
        assert set(delivery_health(db).values()) == {"ok"}
        inbound = Message(conversation_id=conversation_id, sender="user", content="private customer data",
                          created_at=utc_now_naive() - timedelta(minutes=15), raw_payload={"reply_delivery": {"status": "uncertain"}})
        outbound = Message(conversation_id=conversation_id, sender="operator", content="private reply")
        db.add_all([inbound, outbound])
        db.flush()
        db.add(OperatorDelivery(message_id=outbound.id, tenant_id=tenant_id, request_id=uuid4(), status="uncertain"))
        db.add(WebhookInboxEvent(provider="openwa", tenant_id=tenant_id, event_type="message.received", deduplication_key=uuid4().hex,
                                status="pending", received_at=utc_now() - timedelta(minutes=15), payload_json={"secret": "never expose"}))
        db.commit()
        assert set(delivery_health(db).values()) == {"attention"}
    response = client.get("/health/ready")
    assert response.status_code == 200  # One blocked business must not restart the API.
    assert set(response.json()["deployment"]["pipeline_health"].values()) == {"attention"}
    assert "private" not in response.text and "secret" not in response.text
