import json


def test_meta_webhook_is_persisted_before_ack_and_deduplicated(client):
    from app.db.session import SessionLocal
    from app.models.webhook_inbox import WebhookInboxEvent
    from app.services.webhook_inbox_service import WebhookInboxService

    payload = {"object": "whatsapp_business_account", "entry": []}
    body = json.dumps(payload, separators=(",", ":")).encode()

    first = client.post("/whatsapp/webhook", content=body, headers={"Content-Type": "application/json"})
    second = client.post("/whatsapp/webhook", content=body, headers={"Content-Type": "application/json"})

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == "accepted"
    assert second.json()["status"] == "duplicate"

    first_db = SessionLocal()
    second_db = SessionLocal()
    try:
        assert first_db.query(WebhookInboxEvent).count() == 1
        claimed = WebhookInboxService(first_db, owner="worker-a").claim_batch()
        assert len(claimed) == 1
        assert WebhookInboxService(second_db, owner="worker-b").claim_batch() == []
    finally:
        first_db.close()
        second_db.close()


def test_webhook_inbox_dead_letters_after_retry_budget(client):
    from app.db.session import SessionLocal
    from app.models.system_event import SystemEvent
    from app.models.webhook_inbox import WebhookInboxEvent
    from app.services.webhook_inbox_service import WebhookInboxService

    db = SessionLocal()
    try:
        service = WebhookInboxService(db, owner="worker-a")
        row, created = service.enqueue(
            provider="meta_cloud",
            body=b'{"event":"bad"}',
            payload={"event": "bad"},
            event_type="bad",
        )
        assert created is True
        row.max_attempts = 1
        db.commit()
        event_id = service.claim_batch()[0]
        service.mark_failed(event_id, RuntimeError("invalid provider payload"))

        db.refresh(row)
        assert row.status == "dead_letter"
        assert row.lock_owner is None
        assert db.query(SystemEvent).filter(
            SystemEvent.code == "WEBHOOK_EVENT_DEAD_LETTERED"
        ).count() == 1
    finally:
        db.close()
