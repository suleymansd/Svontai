"""A16: retention purge, legal hold and export cover every tenant personal-data table."""

import uuid
from datetime import timedelta

from app.core.time import utc_now, utc_now_naive
from tests.test_admin_tools_endpoints import _create_and_login_super_admin
from tests.test_product_realtime_retention import _headers, _tenant_session


def _seed(db, tenant_id: uuid.UUID, bot_id: uuid.UUID, owner_id: uuid.UUID, *, old: bool) -> dict:
    from app.models.call import Call, CallSummary, CallTranscript
    from app.models.conversation import Conversation, ConversationSource, ConversationStatus
    from app.models.demo_access import DemoAccess
    from app.models.lead import Lead
    from app.models.lead_note import LeadNote
    from app.models.message import Message
    from app.models.operator_delivery import OperatorDelivery
    from app.models.reply_reservation import ReplyReservation
    from app.models.webhook_inbox import WebhookInboxEvent

    when = utc_now_naive() - (timedelta(days=800) if old else timedelta(minutes=1))
    tag = "old" if old else "fresh"
    conversation = Conversation(
        bot_id=bot_id, external_user_id=f"9055500{tag}", source=ConversationSource.WHATSAPP.value,
        status=ConversationStatus.AI_ACTIVE.value, created_at=when, updated_at=when,
    )
    db.add(conversation)
    db.flush()
    message = Message(conversation_id=conversation.id, sender="user", content=tag, created_at=when)
    db.add(message)
    db.flush()
    db.add(ReplyReservation(message_id=message.id, tenant_id=tenant_id, period="2024-01", state="released", created_at=when))
    db.add(OperatorDelivery(message_id=message.id, tenant_id=tenant_id, request_id=uuid.uuid4(), status="sent", updated_at=when))
    call = Call(
        tenant_id=tenant_id, provider="test", provider_call_id=f"call-{tag}", direction="outbound", status="completed",
        from_number="+905550000001", to_number="+905550000002", created_at=when, updated_at=when,
    )
    db.add(call)
    db.flush()
    db.add(CallTranscript(tenant_id=tenant_id, call_id=call.id, segment_index=0, speaker="user", text="hello", created_at=when))
    db.add(CallSummary(tenant_id=tenant_id, call_id=call.id, summary="talked", created_at=when, updated_at=when))
    lead = Lead(
        tenant_id=tenant_id, bot_id=bot_id, name=f"Lead {tag}", phone="+905550000002", status="new", source="whatsapp",
        is_deleted=True, deleted_at=when, created_at=when, updated_at=when,
    )
    db.add(lead)
    db.flush()
    db.add(LeadNote(tenant_id=tenant_id, lead_id=lead.id, content="private note", created_at=when, updated_at=when))
    db.add(WebhookInboxEvent(
        tenant_id=tenant_id, provider="openwa", event_type="message", deduplication_key=f"dedup-{tag}-{tenant_id}",
        payload_json={"from": "+905550000002", "body": "hi"}, status="processed",
        received_at=utc_now() - (timedelta(days=800) if old else timedelta(minutes=1)),
    ))
    if old:
        from app.models.user import User

        demo_user = User(
            email=f"demo-{tenant_id}@example.com", full_name="Demo visitor", password_hash="x",
            is_active=True, email_verified=True,
        )
        db.add(demo_user)
        db.flush()
        db.add(DemoAccess(
            name="Expired demo", token_hash=f"hash-{tenant_id}", user_id=demo_user.id, tenant_id=tenant_id,
            created_by=owner_id, created_at=when, expires_at=when + timedelta(days=1),
        ))
    db.commit()
    return {"message_id": message.id, "call_id": call.id, "lead_id": lead.id}


def _workspace(client, email: str):
    from app.db.session import SessionLocal
    from app.models.tenant import Tenant

    token, tenant_id = _tenant_session(client, email)
    headers = _headers(token, tenant_id)
    bot_id = client.post("/bots", headers=headers, json={"name": "Retention Bot"}).json()["id"]
    with SessionLocal() as db:
        owner_id = db.get(Tenant, uuid.UUID(tenant_id)).owner_id
    return headers, uuid.UUID(tenant_id), uuid.UUID(bot_id), owner_id


def test_retention_purges_new_tables_past_retention_and_keeps_fresh_rows(client):
    from app.db.session import SessionLocal
    from app.models.call import Call, CallSummary, CallTranscript
    from app.models.demo_access import DemoAccess
    from app.models.lead import Lead
    from app.models.lead_note import LeadNote
    from app.models.operator_delivery import OperatorDelivery
    from app.models.reply_reservation import ReplyReservation
    from app.models.webhook_inbox import WebhookInboxEvent
    from app.services.data_retention_service import DataRetentionService

    headers, tenant_id, bot_id, owner_id = _workspace(client, "coverage@example.com")
    with SessionLocal() as db:
        old = _seed(db, tenant_id, bot_id, owner_id, old=True)
        fresh = _seed(db, tenant_id, bot_id, owner_id, old=False)

        service = DataRetentionService(db)
        preview = service.preview(tenant_id)
        for key in ("reply_reservations", "operator_deliveries", "deleted_leads", "demo_access"):
            assert preview[key] == 1, (key, preview)

        result = service.run(tenant_id, force=True)
        assert result["status"] == "completed"
        deleted = result["deleted"]
        for key in (
            "reply_reservations", "operator_deliveries", "call_transcripts", "call_summaries", "calls",
            "deleted_lead_notes", "deleted_leads", "demo_access", "terminal_webhooks", "messages",
        ):
            assert deleted[key] == 1, (key, deleted)

        assert db.query(ReplyReservation).filter_by(message_id=old["message_id"]).first() is None
        assert db.query(OperatorDelivery).filter_by(message_id=old["message_id"]).first() is None
        assert db.query(CallTranscript).filter_by(call_id=old["call_id"]).count() == 0
        assert db.query(CallSummary).filter_by(call_id=old["call_id"]).count() == 0
        assert db.get(Lead, old["lead_id"]) is None
        assert db.query(LeadNote).filter_by(lead_id=old["lead_id"]).count() == 0
        assert db.query(DemoAccess).filter_by(tenant_id=tenant_id).count() == 0

        assert db.query(ReplyReservation).filter_by(message_id=fresh["message_id"]).first() is not None
        assert db.query(OperatorDelivery).filter_by(message_id=fresh["message_id"]).first() is not None
        assert db.query(Call).filter_by(id=fresh["call_id"]).first() is not None
        assert db.get(Lead, fresh["lead_id"]) is not None
        assert db.query(WebhookInboxEvent).filter_by(tenant_id=tenant_id).count() == 1


def test_legal_hold_blocks_retention_purge_and_tenant_deletion(client):
    from app.db.session import SessionLocal
    from app.models.lead import Lead
    from app.models.message import Message
    from app.models.tenant import Tenant
    from app.models.webhook_inbox import WebhookInboxEvent
    from app.services.data_retention_service import DataRetentionService, LegalHoldActive

    headers, tenant_id, bot_id, owner_id = _workspace(client, "hold@example.com")
    admin_headers = {"Authorization": f"Bearer {_create_and_login_super_admin(client)}"}
    with SessionLocal() as db:
        _seed(db, tenant_id, bot_id, owner_id, old=True)

    hold = client.post(f"/admin/tenants/{tenant_id}/legal-hold", json={"enabled": True, "reason": "dispute"}, headers=admin_headers)
    assert hold.status_code == 200, hold.text
    assert hold.json()["legal_hold"] is True
    policy_view = client.get("/data-retention", headers=headers)
    assert policy_view.status_code == 200, policy_view.text
    assert policy_view.json()["legal_hold"] is True

    with SessionLocal() as db:
        service = DataRetentionService(db)
        assert service.run(tenant_id, force=True)["status"] == "legal_hold"
        try:
            service.purge_tenant(tenant_id)
        except LegalHoldActive:
            pass
        else:
            raise AssertionError("purge_tenant must refuse while legal hold is active")
        assert db.query(Lead).filter(Lead.tenant_id == tenant_id).count() == 1

    assert client.delete(f"/admin/tenants/{tenant_id}", headers=admin_headers).status_code == 409
    assert client.post(f"/admin/tenants/{tenant_id}/legal-hold", json={"enabled": False}, headers=admin_headers).status_code == 200
    assert client.delete(f"/admin/tenants/{tenant_id}", headers=admin_headers).status_code == 204

    with SessionLocal() as db:
        assert db.get(Tenant, tenant_id) is None
        assert db.query(Lead).filter(Lead.tenant_id == tenant_id).count() == 0
        assert db.query(WebhookInboxEvent).filter(WebhookInboxEvent.tenant_id == tenant_id).count() == 0
        assert db.query(WebhookInboxEvent).filter(WebhookInboxEvent.tenant_id.is_(None)).count() == 0
        assert db.query(Message).count() == 0


def test_tenant_export_includes_every_personal_data_table_and_redacts_secrets(client):
    from app.db.session import SessionLocal

    headers, tenant_id, bot_id, owner_id = _workspace(client, "export@example.com")
    with SessionLocal() as db:
        _seed(db, tenant_id, bot_id, owner_id, old=True)

    response = client.get("/data-retention/export", headers=headers)
    assert response.status_code == 200, response.text
    export = response.json()
    assert export["tenant"]["id"] == str(tenant_id)
    assert export["legal_hold"] is False
    for table in (
        "reply_reservations", "operator_deliveries", "messages", "conversations", "lead_notes", "leads",
        "call_transcripts", "call_summaries", "calls", "webhook_inbox_events", "demo_access",
        "appointments", "workspace_notes", "training_sessions", "media_assets", "artifacts",
    ):
        assert table in export["tables"], table
    assert export["counts"]["leads"] == 1
    assert export["counts"]["webhook_inbox_events"] == 1
    assert export["tables"]["leads"][0]["phone"] == "+905550000002"
    assert export["tables"]["webhook_inbox_events"][0]["payload_json"]["body"] == "hi"
    demo = export["tables"]["demo_access"][0]
    assert "token_hash" not in demo and demo["name"] == "Expired demo"
