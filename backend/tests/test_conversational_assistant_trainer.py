from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock


def _tenant_session(client, email: str) -> tuple[str, str]:
    password = "Password123!"
    register = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Trainer User",
            "terms_accepted": True,
            "privacy_notice_acknowledged": True,
            "terms_version": "2026-08-04",
            "privacy_version": "2026-08-04",
            "kvkk_notice_version": "2026-08-04",
        },
    )
    assert register.status_code == 201, register.text
    code_message = client.post("/auth/email-verification/request", json={"email": email}).json()["message"]
    code = re.search(r"(\d{6})", code_message).group(1)
    assert client.post(
        "/auth/email-verification/confirm",
        json={"email": email, "code": code},
    ).status_code == 200
    token = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    tenant = client.post(
        "/tenants",
        json={"name": f"Tenant {email}"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    return token, tenant["id"]


def _headers(token: str, tenant_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}


def test_chat_trainer_drafts_and_idempotently_applies_specialist(client, monkeypatch):
    from app.services.ai_service import ai_service

    token, tenant_id = _tenant_session(client, "trainer@example.com")
    headers = _headers(token, tenant_id)
    proposal = {
        "status": "ready",
        "assistant_message": "Kargo soruları için uzman taslağını hazırladım. Onayınıza sunuyorum.",
        "proposal": {
            "name": "Kargo Takip Uzmanı",
            "description": "Kargo durumu sorularında sipariş numarasını alır ve doğrulanmış süreci açıklar.",
            "example_questions": ["Kargom nerede?", "Siparişim ne zaman gelir?"],
            "answer": "Önce sipariş numarasını isteyin; ardından kayıtlı kargo durumunu paylaşın.",
            "behavior_instruction": "Sipariş numarası olmadan kargo durumu uydurma ve tek seferde yalnızca bu bilgiyi iste.",
        },
    }
    monkeypatch.setattr(ai_service, "generate_text", AsyncMock(return_value=json.dumps(proposal)))

    draft = client.post(
        "/bots/assistant-profile/trainer/message",
        headers=headers,
        json={"message": "Kargom nerede diyen müşteriye özel bir bot oluştur."},
    )
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["status"] == "ready"
    assert body["proposal"]["name"] == "Kargo Takip Uzmanı"

    applied = client.post(
        f"/bots/assistant-profile/trainer/{body['session_id']}/apply",
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["bot"]["assistant_type"] == "specialist"
    assert applied.json()["knowledge_items_created"] == 1

    repeated = client.post(
        f"/bots/assistant-profile/trainer/{body['session_id']}/apply",
        headers=headers,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["bot"]["id"] == applied.json()["bot"]["id"]
    assert repeated.json()["knowledge_items_created"] == 0

    bots = client.get("/bots", headers=headers).json()
    assert len([bot for bot in bots if bot["assistant_type"] == "specialist"]) == 1


def test_chat_trainer_collects_missing_information_and_enforces_tenant_scope(client, monkeypatch):
    from app.services.ai_service import ai_service

    token, tenant_id = _tenant_session(client, "trainer-clarify@example.com")
    other_token, other_tenant_id = _tenant_session(client, "trainer-other@example.com")
    monkeypatch.setattr(
        ai_service,
        "generate_text",
        AsyncMock(return_value=json.dumps({
            "status": "needs_info",
            "assistant_message": "Müşteriye verilmesini istediğiniz doğrulanmış cevap nedir?",
            "proposal": None,
        })),
    )

    draft = client.post(
        "/bots/assistant-profile/trainer/message",
        headers=_headers(token, tenant_id),
        json={"message": "Fiyat sorularına özel bot oluştur."},
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["status"] == "collecting"
    assert draft.json()["proposal"] is None

    foreign_apply = client.post(
        f"/bots/assistant-profile/trainer/{draft.json()['session_id']}/apply",
        headers=_headers(other_token, other_tenant_id),
    )
    assert foreign_apply.status_code == 409


def test_primary_assistant_uses_active_specialist_knowledge_only(client, monkeypatch):
    from app.services.ai_service import ai_service

    token, tenant_id = _tenant_session(client, "trainer-effective@example.com")
    headers = _headers(token, tenant_id)
    profile = client.get("/bots/assistant-profile", headers=headers).json()
    primary_id = profile["assistant"]["id"]

    active_bot = client.post("/bots", headers=headers, json={"name": "Aktif Uzman"}).json()
    inactive_bot = client.post("/bots", headers=headers, json={"name": "Pasif Uzman"}).json()
    client.put(f"/bots/{inactive_bot['id']}", headers=headers, json={"is_active": False})
    client.post(
        f"/bots/{active_bot['id']}/knowledge",
        headers=headers,
        json={"title": "Aktif bilgi", "question": "Teslimat?", "answer": "İki iş günü."},
    )
    client.post(
        f"/bots/{inactive_bot['id']}/knowledge",
        headers=headers,
        json={"title": "Pasif bilgi", "question": "Eski teslimat?", "answer": "On gün."},
    )

    generate_reply = AsyncMock(return_value="Teslimat iki iş günüdür.")
    monkeypatch.setattr(ai_service, "generate_reply", generate_reply)
    response = client.post(
        f"/bots/{primary_id}/simulate",
        headers=headers,
        json={"message": "Teslimat ne kadar sürer?", "history": []},
    )
    assert response.status_code == 200, response.text
    knowledge = generate_reply.await_args.kwargs["knowledge_items"]
    assert "Aktif bilgi" in {item.title for item in knowledge}
    assert "Pasif bilgi" not in {item.title for item in knowledge}
