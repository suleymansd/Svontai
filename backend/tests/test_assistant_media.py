from __future__ import annotations

import asyncio
import re
import uuid
from unittest.mock import AsyncMock

from app.core import rate_limit as rate_limit_module
from app.core.config import settings
from app.models.assistant_media import AssistantMediaAsset
from app.models.conversation import Conversation, ConversationSource
from app.models.message import Message, MessageSender
from app.models.whatsapp_account import WhatsAppAccount
from app.services.assistant_media_service import AssistantMediaService
from app.services.openwa_client import openwa_client
from app.services.whatsapp_gateway_service import whatsapp_gateway_service


def _create_tenant(client, email: str) -> tuple[str, str]:
    password = "Password123!"
    assert client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Media User"},
    ).status_code == 201
    code_message = client.post("/auth/email-verification/request", json={"email": email}).json()["message"]
    code = re.search(r"(\d{6})", code_message).group(1)
    assert client.post(
        "/auth/email-verification/confirm", json={"email": email, "code": code}
    ).status_code == 200
    token = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    tenant = client.post(
        "/tenants",
        json={"name": f"Media {email}"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    return token, tenant["id"]


def _headers(token: str, tenant_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}


def test_media_upload_is_private_tenant_scoped_and_deletable(client, monkeypatch, tmp_path):
    previous_provider = settings.ARTIFACT_STORAGE_PROVIDER
    previous_path = settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_PROVIDER", "local")
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_LOCAL_BASE_PATH", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    try:
        token, tenant_id = _create_tenant(client, "media-owner@example.com")
        headers = _headers(token, tenant_id)
        response = client.post(
            "/media",
            headers=headers,
            data={
                "title": "Yeni sezon görseli",
                "description": "Müşteri yeni sezon ürünlerini istediğinde gönder.",
                "keywords": "yeni sezon, ürün, mavi",
            },
            files={"file": ("season.png", b"\x89PNG\r\n\x1a\nmedia-content", "image/png")},
        )
        assert response.status_code == 201, response.text
        asset = response.json()
        assert asset["media_type"] == "image"
        assert asset["keywords"][:3] == ["yeni sezon", "ürün", "mavi"]
        assert "/tools/artifacts/" in asset["preview_url"]

        profile = client.get("/bots/assistant-profile", headers=headers)
        media_capability = next(item for item in profile.json()["capabilities"] if item["key"] == "media_catalog")
        assert media_capability["enabled"] is True
        assert media_capability["ready"] is True

        other_token, other_tenant_id = _create_tenant(client, "media-other@example.com")
        other_headers = _headers(other_token, other_tenant_id)
        assert client.get("/media", headers=other_headers).json() == []
        assert client.patch(
            f"/media/{asset['id']}", json={"is_active": False}, headers=other_headers
        ).status_code == 404
        assert client.delete(f"/media/{asset['id']}", headers=other_headers).status_code == 404

        deleted = client.delete(f"/media/{asset['id']}", headers=headers)
        assert deleted.status_code == 204, deleted.text
        assert client.get("/media", headers=headers).json() == []
    finally:
        settings.ARTIFACT_STORAGE_PROVIDER = previous_provider
        settings.ARTIFACT_STORAGE_LOCAL_BASE_PATH = previous_path


def test_media_upload_rejects_spoofed_content_type(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_PROVIDER", "local")
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_LOCAL_BASE_PATH", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    token, tenant_id = _create_tenant(client, "media-spoof@example.com")
    response = client.post(
        "/media",
        headers=_headers(token, tenant_id),
        data={"title": "Sahte dosya"},
        files={"file": ("fake.png", b"<script>alert(1)</script>", "image/png")},
    )
    assert response.status_code == 400
    assert "desteklenen" in response.json()["detail"]


def test_ai_media_action_validates_tenant_and_prevents_repeat(client, monkeypatch, tmp_path):
    from app.db.session import SessionLocal
    from app.models.bot import Bot

    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_PROVIDER", "local")
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_LOCAL_BASE_PATH", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    token, tenant_id = _create_tenant(client, "media-action@example.com")
    headers = _headers(token, tenant_id)
    client.get("/bots/assistant-profile", headers=headers)
    asset_id = client.post(
        "/media",
        headers=headers,
        data={"title": "Fiyat kataloğu", "keywords": "fiyat, katalog"},
        files={"file": ("catalog.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
    ).json()["id"]

    db = SessionLocal()
    try:
        bot = db.query(Bot).filter(Bot.tenant_id == uuid.UUID(tenant_id)).first()
        conversation = Conversation(
            bot_id=bot.id,
            external_user_id="905551112233",
            source=ConversationSource.WHATSAPP.value,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        service = AssistantMediaService(db)
        tagged = (
            "Kataloğu paylaşıyorum.\n"
            f'<svontai_action>{{"type":"send_media","asset_id":"{asset_id}","caption":"Güncel katalog"}}</svontai_action>'
        )
        clean, selected = service.extract_action(
            tenant_id=uuid.UUID(tenant_id), conversation=conversation, reply=tagged
        )
        assert clean == "Kataloğu paylaşıyorum."
        assert selected is not None
        assert str(selected.asset.id) == asset_id

        db.add(Message(
            conversation_id=conversation.id,
            sender=MessageSender.BOT.value,
            content="[catalog:Fiyat kataloğu]",
            raw_payload={"media_asset_id": asset_id},
        ))
        db.commit()
        _clean, repeated = service.extract_action(
            tenant_id=uuid.UUID(tenant_id), conversation=conversation, reply=tagged
        )
        assert repeated is None

        foreign_reply = tagged.replace(asset_id, str(uuid.uuid4()))
        _clean, foreign = service.extract_action(
            tenant_id=uuid.UUID(tenant_id), conversation=conversation, reply=foreign_reply
        )
        assert foreign is None
    finally:
        db.close()


def test_whatsapp_gateway_sends_image_through_openwa(monkeypatch):
    rate_limit_module.whatsapp_send_minute_rate_limiter.clear()
    rate_limit_module.whatsapp_send_hour_rate_limiter.clear()
    send_media = AsyncMock(return_value={"messageId": "openwa-media-1"})
    monkeypatch.setattr(openwa_client, "send_media", send_media)
    account = WhatsAppAccount(
        tenant_id=uuid.uuid4(),
        provider="openwa",
        provider_session_id="session-1",
        token_status="active",
        webhook_status="verified",
        is_active=True,
        is_verified=True,
    )
    result = asyncio.run(whatsapp_gateway_service.send_media(
        account,
        to="905551112233",
        media_type="image",
        content_bytes=b"image-bytes",
        mime_type="image/jpeg",
        filename="product.jpg",
        caption="Ürün",
    ))
    assert result["message_id"] == "openwa-media-1"
    assert send_media.await_args.kwargs["base64_data"]


def test_whatsapp_gateway_uploads_media_before_meta_send(monkeypatch):
    from app.services import whatsapp_gateway_service as gateway_module
    from app.services.meta_api import meta_api_service

    rate_limit_module.whatsapp_send_minute_rate_limiter.clear()
    rate_limit_module.whatsapp_send_hour_rate_limiter.clear()
    upload = AsyncMock(return_value={"id": "meta-media-id"})
    send = AsyncMock(return_value={"messages": [{"id": "meta-message-id"}]})
    monkeypatch.setattr(gateway_module, "decrypt_token", lambda _value: "meta-token")
    monkeypatch.setattr(meta_api_service, "upload_media", upload)
    monkeypatch.setattr(meta_api_service, "send_media_message", send)
    account = WhatsAppAccount(
        tenant_id=uuid.uuid4(),
        provider="meta_cloud",
        phone_number_id="phone-number-id",
        access_token_encrypted="encrypted",
        token_status="active",
        webhook_status="verified",
        is_active=True,
        is_verified=True,
    )
    result = asyncio.run(whatsapp_gateway_service.send_media(
        account,
        to="905551112233",
        media_type="video",
        content_bytes=b"video-bytes",
        mime_type="video/mp4",
        filename="product.mp4",
        caption="Tanıtım",
    ))
    assert result["message_id"] == "meta-message-id"
    assert upload.await_args.kwargs["mime_type"] == "video/mp4"
    assert send.await_args.kwargs["media_id"] == "meta-media-id"
