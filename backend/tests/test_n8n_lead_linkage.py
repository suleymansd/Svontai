from __future__ import annotations

import uuid

from app.core.n8n_security import create_n8n_jwt_token
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationSource
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.models.user import User


def test_n8n_lead_upsert_links_tenant_bot_and_conversation(client):
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        user = User(
            email=f"n8n-link-{uuid.uuid4().hex}@example.com",
            password_hash="unused",
            full_name="n8n Link Test",
        )
        db.add(user)
        db.flush()
        tenant = Tenant(name="n8n Link Tenant", slug=f"n8n-link-{uuid.uuid4().hex}", owner_id=user.id)
        db.add(tenant)
        db.flush()
        bot = Bot(tenant_id=tenant.id, name="n8n Link Bot")
        db.add(bot)
        db.flush()
        conversation = Conversation(
            bot_id=bot.id,
            external_user_id="+905551112233",
            source=ConversationSource.WHATSAPP.value,
        )
        db.add(conversation)
        db.commit()

        token = create_n8n_jwt_token(str(tenant.id))
        response = client.post(
            "/api/v1/n8n/leads/upsert",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
            json={
                "tenantId": str(tenant.id),
                "phone": "+905551112233",
                "source": "whatsapp",
                "botId": str(bot.id),
                "conversationId": str(conversation.id),
            },
        )
        assert response.status_code == 200, response.text

        lead = db.query(Lead).filter(Lead.id == uuid.UUID(response.json()["leadId"])).first()
        assert lead is not None
        assert lead.tenant_id == tenant.id
        assert lead.bot_id == bot.id
        assert lead.conversation_id == conversation.id
    finally:
        db.close()


def test_n8n_lead_upsert_resolves_active_tenant_bot(client):
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        user = User(
            email=f"n8n-bot-fallback-{uuid.uuid4().hex}@example.com",
            password_hash="unused",
            full_name="n8n Bot Fallback Test",
        )
        db.add(user)
        db.flush()
        tenant = Tenant(
            name="n8n Bot Fallback Tenant",
            slug=f"n8n-bot-fallback-{uuid.uuid4().hex}",
            owner_id=user.id,
        )
        db.add(tenant)
        db.flush()
        inactive_bot = Bot(tenant_id=tenant.id, name="Inactive Bot", is_active=False)
        active_bot = Bot(tenant_id=tenant.id, name="Active Bot", is_active=True)
        db.add_all([inactive_bot, active_bot])
        db.commit()

        token = create_n8n_jwt_token(str(tenant.id))
        response = client.post(
            "/api/v1/n8n/leads/upsert",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
            json={
                "tenantId": str(tenant.id),
                "phone": "+905559998877",
                "source": "whatsapp",
            },
        )
        assert response.status_code == 200, response.text

        lead = db.query(Lead).filter(Lead.id == uuid.UUID(response.json()["leadId"])).first()
        assert lead is not None
        assert lead.tenant_id == tenant.id
        assert lead.bot_id == active_bot.id
        assert lead.conversation_id is None
    finally:
        db.close()
