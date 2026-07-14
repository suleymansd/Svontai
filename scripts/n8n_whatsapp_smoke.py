#!/usr/bin/env python3
"""Exercise the live WhatsApp n8n path without sending an external message."""

from __future__ import annotations

import os
import uuid

import httpx

from app.core.config import settings
from app.core.n8n_security import create_n8n_jwt_token, generate_svontai_to_n8n_headers
from app.db.session import SessionLocal
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationSource, ConversationStatus
from app.models.lead import Lead


def main() -> int:
    db = SessionLocal()
    conversation: Conversation | None = None
    phone = f"+999{uuid.uuid4().int % 10_000_000_000:010d}"
    try:
        bot = db.query(Bot).filter(Bot.is_active.is_(True)).first()
        if bot is None:
            raise RuntimeError("No active bot is available for the smoke test")

        conversation = Conversation(
            bot_id=bot.id,
            external_user_id=phone,
            source=ConversationSource.WHATSAPP.value,
            status=ConversationStatus.HUMAN_TAKEOVER.value,
            is_ai_paused=True,
            extra_data={"smoke_test": True},
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        tenant_id = str(bot.tenant_id)
        token = create_n8n_jwt_token(tenant_id)
        backend_url = settings.BACKEND_URL.rstrip("/")
        payload = {
            "event": "svontai_event",
            "eventType": "incoming_message",
            "runId": None,
            "correlationId": f"smoke-{uuid.uuid4()}",
            "tenantId": tenant_id,
            "channel": "whatsapp",
            "externalEventId": f"smoke-{uuid.uuid4()}",
            "from": phone,
            "to": "smoke-destination",
            "text": "Türkçe n8n güvenli smoke testi",
            "metadata": {
                "bot_id": str(bot.id),
                "conversation_id": str(conversation.id),
            },
            "svontai": {
                "tenantId": tenant_id,
                "token": token,
                "endpoints": {
                    "leads_upsert": f"{backend_url}/api/v1/n8n/leads/upsert",
                    "ai_reply": f"{backend_url}/api/v1/n8n/ai/reply",
                    "whatsapp_send": f"{backend_url}/api/v1/channels/whatsapp/send",
                },
            },
        }
        n8n_url = os.environ["N8N_BASE_URL"].rstrip("/")
        response = httpx.post(
            f"{n8n_url}/webhook/svontai-whatsapp-v2",
            json=payload,
            headers=generate_svontai_to_n8n_headers(payload, tenant_id),
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("success") is not True:
            raise RuntimeError(f"Workflow failed: {result.get('error') or 'unknown error'}")

        db.expire_all()
        lead = db.query(Lead).filter(Lead.tenant_id == bot.tenant_id, Lead.phone == phone).first()
        if lead is None:
            raise RuntimeError("Workflow did not create the lead")
        if lead.bot_id != bot.id or lead.conversation_id != conversation.id:
            raise RuntimeError("Workflow created the lead without bot/conversation linkage")

        print({
            "success": True,
            "execution_id": result.get("executionId"),
            "lead_linked": True,
            "external_send": False,
        })
        return 0
    finally:
        db.rollback()
        lead = db.query(Lead).filter(Lead.phone == phone).first()
        if lead is not None:
            db.delete(lead)
            db.commit()
        if conversation is not None:
            existing = db.query(Conversation).filter(Conversation.id == conversation.id).first()
            if existing is not None:
                db.delete(existing)
                db.commit()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
