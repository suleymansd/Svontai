import base64
import hashlib
import html
import hmac
import re
from urllib.parse import urlsplit
from unittest.mock import AsyncMock
from uuid import UUID

import pytest


def _extract_6_digit_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match, f"Could not extract verification code from message: {message!r}"
    return match.group(1)


def _auth_headers(access_token: str, tenant_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id
    return headers


def test_twilio_webhook_signature_verification():
    from voice_gateway.security import verify_twilio_webhook_signature

    url = "https://voice.example.com/twilio/voice/intent?tenantId=tenant-1"
    items = [("CallSid", "CA123"), ("SpeechResult", "Randevu almak istiyorum")]
    token = "test-auth-token"
    signed_value = url + "CallSidCA123SpeechResultRandevu almak istiyorum"
    signature = base64.b64encode(
        hmac.new(token.encode(), signed_value.encode(), hashlib.sha1).digest()
    ).decode()

    assert verify_twilio_webhook_signature(url, items, signature, token) is True
    assert verify_twilio_webhook_signature(url, items, "invalid", token) is False
    assert verify_twilio_webhook_signature(url, items, signature, "") is False


@pytest.mark.parametrize(
    "path",
    [
        "/twilio/voice/inbound",
        "/twilio/voice/outbound?tenantId=tenant-1&jobId=job-1",
        "/twilio/voice/intent?tenantId=tenant-1&callSid=CA123",
        "/twilio/voice/status?tenantId=tenant-1&callSid=CA123",
    ],
)
def test_twilio_webhooks_reject_unsigned_requests(monkeypatch, path):
    from fastapi.testclient import TestClient
    from voice_gateway.config import settings
    from voice_gateway.main import app as voice_gateway_app

    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "test-auth-token")
    with TestClient(voice_gateway_app) as gateway_client:
        response = gateway_client.post(path, data={"CallSid": "CA123"})

    assert response.status_code == 403


def _create_tenant_session(client, email: str = "voice@example.com") -> tuple[str, str]:
    password = "Password123!"
    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Voice User", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-07-22", "privacy_version": "2026-07-22", "kvkk_notice_version": "2026-07-22"},
    )
    assert register_resp.status_code == 201, register_resp.text

    request_code = client.post("/auth/email-verification/request", json={"email": email})
    assert request_code.status_code == 200, request_code.text
    code = _extract_6_digit_code(request_code.json().get("message", ""))

    confirm_code = client.post("/auth/email-verification/confirm", json={"email": email, "code": code})
    assert confirm_code.status_code == 200, confirm_code.text

    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    access_token = login_resp.json()["access_token"]

    tenant_resp = client.post(
        "/tenants",
        json={"name": "Voice Tenant"},
        headers=_auth_headers(access_token),
    )
    assert tenant_resp.status_code == 201, tenant_resp.text
    return access_token, tenant_resp.json()["id"]


def test_voice_settings_and_test_call_job_flow(client):
    access_token, tenant_id = _create_tenant_session(client)
    headers = _auth_headers(access_token, tenant_id)

    settings_resp = client.get("/voice-automation/settings", headers=headers)
    assert settings_resp.status_code == 200, settings_resp.text
    assert settings_resp.json()["enabled"] is False
    assert settings_resp.json()["provider"] == "vapi"

    update_resp = client.patch(
        "/voice-automation/settings",
        json={"enabled": True, "provider": "vapi", "from_number": "+905551112233"},
        headers=headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["enabled"] is True
    assert update_resp.json()["from_number"] == "+905551112233"

    intent_resp = client.post(
        "/voice-automation/test-call",
        json={"customer_phone": "+905559998877", "customer_name": "Test Lead", "consent_confirmed": True},
        headers=headers,
    )
    assert intent_resp.status_code == 200, intent_resp.text
    assert intent_resp.json()["status"] == "queued"

    jobs_resp = client.get("/voice-automation/jobs", headers=headers)
    assert jobs_resp.status_code == 200, jobs_resp.text
    jobs = jobs_resp.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "pending"

    from app.db.session import SessionLocal
    from app.services.voice_automation_service import VoiceAutomationService

    db = SessionLocal()
    try:
        result = VoiceAutomationService(db).run_due_outbound_jobs()
    finally:
        db.close()
    assert result["started"] == 1

    calls_resp = client.get("/calls", headers=headers)
    assert calls_resp.status_code == 200, calls_resp.text
    calls = calls_resp.json()
    assert len(calls) == 1
    assert calls[0]["direction"] == "outbound"
    assert calls[0]["provider"] == "vapi"


def test_voice_live_twilio_job_uses_real_provider_contract(client, monkeypatch):
    from app.core.config import settings

    access_token, tenant_id = _create_tenant_session(client, email="voice-live@example.com")
    headers = _auth_headers(access_token, tenant_id)

    update_resp = client.patch(
        "/voice-automation/settings",
        json={"enabled": True, "provider": "twilio", "from_number": "+15005550006"},
        headers=headers,
    )
    assert update_resp.status_code == 200, update_resp.text

    intent_resp = client.post(
        "/voice-automation/test-call",
        json={"customer_phone": "+905559998877", "customer_name": "Live Test Lead", "consent_confirmed": True},
        headers=headers,
    )
    assert intent_resp.status_code == 200, intent_resp.text

    captured = {}

    class FakeResponse:
        status_code = 201
        text = ""

        def json(self):
            return {"sid": "CA1234567890", "status": "queued"}

    class FakeHttpClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, data, auth):
            captured["url"] = url
            captured["data"] = data
            captured["auth"] = auth
            return FakeResponse()

    old_mode = settings.VOICE_OUTBOUND_MODE
    old_gateway = settings.VOICE_GATEWAY_PUBLIC_URL
    old_sid = settings.TWILIO_ACCOUNT_SID
    old_token = settings.TWILIO_AUTH_TOKEN
    settings.VOICE_OUTBOUND_MODE = "live"
    settings.VOICE_GATEWAY_PUBLIC_URL = "https://voice.example.com"
    settings.TWILIO_ACCOUNT_SID = "AC123"
    settings.TWILIO_AUTH_TOKEN = "secret"
    monkeypatch.setattr("app.services.voice_automation_service.httpx.Client", FakeHttpClient)

    from app.db.session import SessionLocal
    from app.services.voice_automation_service import VoiceAutomationService

    db = SessionLocal()
    try:
        result = VoiceAutomationService(db).run_due_outbound_jobs()
    finally:
        db.close()
        settings.VOICE_OUTBOUND_MODE = old_mode
        settings.VOICE_GATEWAY_PUBLIC_URL = old_gateway
        settings.TWILIO_ACCOUNT_SID = old_sid
        settings.TWILIO_AUTH_TOKEN = old_token

    assert result["started"] == 1
    assert captured["url"] == "https://api.twilio.com/2010-04-01/Accounts/AC123/Calls.json"
    assert captured["auth"] == ("AC123", "secret")
    assert captured["data"]["To"] == "+905559998877"
    assert captured["data"]["From"] == "+15005550006"
    assert captured["data"]["Url"].startswith("https://voice.example.com/twilio/voice/outbound")
    assert captured["data"]["StatusCallback"].startswith("https://voice.example.com/twilio/voice/status")
    assert captured["data"]["TimeLimit"] == "300"

    jobs_resp = client.get("/voice-automation/jobs", headers=headers)
    assert jobs_resp.status_code == 200, jobs_resp.text
    jobs = jobs_resp.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "running"
    assert jobs[0]["provider"] == "twilio"
    assert jobs[0]["provider_call_id"] == "CA1234567890"

    calls_resp = client.get("/calls", headers=headers)
    assert calls_resp.status_code == 200, calls_resp.text
    calls = calls_resp.json()
    assert len(calls) == 1
    assert calls[0]["provider"] == "twilio"
    assert calls[0]["provider_call_id"] == "CA1234567890"


def test_voice_global_cost_guard_and_destination_allowlist(client):
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.models.voice_automation import OutboundCallJob
    from app.services.voice_automation_service import VoiceAutomationService

    _access_token, tenant_id = _create_tenant_session(client, email="voice-cost-guard@example.com")
    db = SessionLocal()
    old_daily = settings.VOICE_GLOBAL_DAILY_CALL_LIMIT
    old_monthly = settings.VOICE_GLOBAL_MONTHLY_CALL_LIMIT
    old_prefixes = settings.VOICE_ALLOWED_DESTINATION_PREFIXES
    try:
        settings.VOICE_GLOBAL_DAILY_CALL_LIMIT = 1
        settings.VOICE_GLOBAL_MONTHLY_CALL_LIMIT = 10
        settings.VOICE_ALLOWED_DESTINATION_PREFIXES = "+90,+49"
        db.add(OutboundCallJob(
            tenant_id=UUID(tenant_id),
            provider="twilio",
            from_number="+15005550006",
            to_number="+905559998877",
            status="running",
            provider_call_id="CA-cost-guard",
        ))
        db.commit()

        service = VoiceAutomationService(db)
        assert service._global_limit_reason() == "global_daily_limit"
        assert service._destination_allowed("+905559998877") is True
        assert service._destination_allowed("+4915112345678") is True
        assert service._destination_allowed("+441234567890") is False
    finally:
        db.close()
        settings.VOICE_GLOBAL_DAILY_CALL_LIMIT = old_daily
        settings.VOICE_GLOBAL_MONTHLY_CALL_LIMIT = old_monthly
        settings.VOICE_ALLOWED_DESTINATION_PREFIXES = old_prefixes


def test_signed_voice_intent_uses_tenant_ai_and_is_idempotent(client, monkeypatch):
    from app.core.config import settings
    from app.core.n8n_security import generate_signature
    from app.api.routers import voice_intent as voice_intent_module

    _access_token, tenant_id = _create_tenant_session(client, email="voice-ai@example.com")
    generate = AsyncMock(return_value="Elbette, hangi hizmet için bilgi almak istersiniz?")
    monkeypatch.setattr(voice_intent_module.ai_service, "generate_voice_reply", generate)
    payload = {
        "tenantId": tenant_id,
        "eventType": "voice_call_intent",
        "eventId": "twilio:CA-test:turn:1",
        "from": "tel:+905559998877",
        "to": "tel:+15005550006",
        "text": "Hizmetleriniz hakkında bilgi almak istiyorum",
        "call": {
            "provider": "twilio",
            "provider_call_id": "CA-test",
            "direction": "outbound",
            "status": "in_progress",
        },
        "metadata": {"turn": 1},
    }
    signature, timestamp = generate_signature(payload, settings.VOICE_GATEWAY_TO_SVONTAI_SECRET)
    headers = {
        "X-Voice-Signature": signature,
        "X-Voice-Timestamp": str(timestamp),
    }

    first = client.post("/api/v1/voice/intent", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["responseText"] == "Elbette, hangi hizmet için bilgi almak istersiniz?"
    assert first.json()["endCall"] is False
    assert first.json()["runId"]

    duplicate = client.post("/api/v1/voice/intent", json=payload, headers=headers)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["responseText"] == first.json()["responseText"]
    assert generate.await_count == 1


def test_signed_voice_intent_books_confirmed_real_slot_once(client, monkeypatch):
    from app.api.routers import voice_intent as voice_intent_module
    from app.core.config import settings
    from app.core.n8n_security import generate_signature
    from app.db.session import SessionLocal
    from app.models.appointment import Appointment
    from app.models.call import Call, CallDirection
    from app.models.tenant import Tenant
    from app.services.appointment_availability_service import default_appointment_settings

    _access_token, tenant_id = _create_tenant_session(client, email="voice-booking@example.com")
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == UUID(tenant_id)).one()
        appointment_settings = default_appointment_settings()
        appointment_settings.update({
            "configured": True,
            "timezone": "UTC",
            "minimum_notice_hours": 0,
        })
        appointment_settings["weekly_hours"] = {
            day: {"enabled": True, "start": "00:00", "end": "23:59"}
            for day in appointment_settings["weekly_hours"]
        }
        tenant.settings = {
            **(tenant.settings or {}),
            "appointment_settings": appointment_settings,
        }
        call = Call(
            tenant_id=tenant.id,
            provider="twilio",
            provider_call_id="CA-booking-test",
            direction=CallDirection.OUTBOUND.value,
            status="in_progress",
            from_number="tel:+12404106113",
            to_number="tel:+905559998877",
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        call_id = call.id
    finally:
        db.close()

    generate = AsyncMock(return_value="Bu akışta yapay zeka çağrılmamalı")
    notify = AsyncMock()
    monkeypatch.setattr(voice_intent_module.ai_service, "generate_voice_reply", generate)
    monkeypatch.setattr(voice_intent_module, "send_tenant_push_notification", notify)

    base_payload = {
        "tenantId": tenant_id,
        "eventType": "voice_call_intent",
        "from": "tel:+12404106113",
        "to": "tel:+905559998877",
        "call": {
            "provider": "twilio",
            "provider_call_id": "CA-booking-test",
            "direction": "outbound",
            "status": "in_progress",
        },
    }

    def post_turn(turn: int, text: str):
        payload = {
            **base_payload,
            "eventId": f"twilio:CA-booking-test:turn:{turn}",
            "text": text,
            "metadata": {"turn": turn},
        }
        signature, timestamp = generate_signature(payload, settings.VOICE_GATEWAY_TO_SVONTAI_SECRET)
        return client.post(
            "/api/v1/voice/intent",
            json=payload,
            headers={
                "X-Voice-Signature": signature,
                "X-Voice-Timestamp": str(timestamp),
            },
        )

    first = post_turn(1, "Randevu almak istiyorum")
    assert first.status_code == 200, first.text
    assert "Uygun saatleri kontrol ettim" in first.json()["responseText"]
    assert first.json()["raw"]["appointmentCreated"] is False

    second = post_turn(2, "Birinci seçeneği istiyorum")
    assert second.status_code == 200, second.text
    assert "onaylıyor musunuz" in second.json()["responseText"]
    assert second.json()["raw"]["appointmentCreated"] is False

    third = post_turn(3, "Evet, onaylıyorum")
    assert third.status_code == 200, third.text
    assert "randevu sistemine kaydettim" in third.json()["responseText"]
    assert third.json()["raw"]["appointmentCreated"] is True
    appointment_id = third.json()["raw"]["appointmentId"]

    duplicate = post_turn(3, "Evet, onaylıyorum")
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["raw"]["appointmentId"] == appointment_id
    assert generate.await_count == 0
    assert notify.await_count == 1

    db = SessionLocal()
    try:
        rows = db.query(Appointment).filter(Appointment.call_id == call_id).all()
        assert len(rows) == 1
        assert str(rows[0].id) == appointment_id
        assert rows[0].source == "ai_voice"
        assert rows[0].calendar_sync_status == "pending"
    finally:
        db.close()


def test_voice_gateway_escapes_twiml_values():
    from voice_gateway.main import _voice_intent_action_url, _xml_attr, _xml_text

    assert _xml_attr('/voice?tenant=1&turn=2') == '/voice?tenant=1&amp;turn=2'
    assert _xml_text('Fiyat < 100 & uygun') == 'Fiyat &lt; 100 &amp; uygun'

    action_url = _voice_intent_action_url(
        tenant_id="tenant-1",
        call_sid="CA-test",
        from_number=" +12404106113 ",
        to_number="+905452196863",
        turn=2,
    )
    assert " " not in action_url
    assert "from=%2B12404106113" in action_url
    assert "to=%2B905452196863" in action_url


@pytest.mark.asyncio
async def test_twilio_stream_fallback_uses_turkish_voice():
    from voice_gateway.config import settings
    from voice_gateway.providers.base import InboundCallRequest
    from voice_gateway.providers.twilio import TwilioAdapter

    twiml = await TwilioAdapter().build_connect_stream_response(
        tenant_id="tenant-1",
        request=InboundCallRequest(
            provider="twilio",
            to_number="+15005550006",
            from_number="+905559998877",
            provider_call_id="CA-test",
            raw={},
        ),
        ws_url="wss://voice.example.com/ws/twilio/media",
    )

    assert settings.TWILIO_TTS_VOICE == "Google.tr-TR-Wavenet-D"
    assert '<Say voice="Google.tr-TR-Wavenet-D" language="tr-TR">' in twiml


def test_turkish_voice_text_and_gather_are_normalized():
    from voice_gateway.twiml import gather, normalize_spoken_text

    assert normalize_spoken_text("SvontAI ile WhatsApp QR bağlantısı") == "Svont Ay ile Vatsap kare kod bağlantısı"
    twiml = gather("WhatsApp randevusu", "/voice?turn=1&tenant=abc")
    assert 'voice="Google.tr-TR-Wavenet-D"' in twiml
    assert 'speechModel="googlev2_telephony_short"' in twiml
    assert 'speechTimeout="1"' in twiml
    assert 'actionOnEmptyResult="true"' in twiml
    assert "Vatsap randevusu" in twiml
    assert "&amp;tenant=abc" in twiml


def test_conversation_relay_twiml_is_turkish_interruptible_and_signed(monkeypatch):
    from voice_gateway.config import settings
    from voice_gateway.main import _conversation_relay_twiml
    from voice_gateway.security import verify_websocket_session

    monkeypatch.setattr(settings, "VOICE_GATEWAY_PUBLIC_URL", "https://voice.example.com")
    monkeypatch.setattr(settings, "VOICE_GATEWAY_TO_SVONTAI_SECRET", "relay-secret")
    twiml = _conversation_relay_twiml(
        tenant_id="tenant-1",
        call_sid="CA-relay",
        from_number="+905551112233",
        to_number="+12404106113",
        direction="inbound",
    )
    assert '<ConversationRelay url="wss://voice.example.com/ws/twilio/conversation?' in twiml
    assert 'language="tr-TR"' in twiml
    assert 'ttsProvider="Google"' in twiml
    assert 'voice="tr-TR-Wavenet-D"' in twiml
    assert 'interruptible="speech"' in twiml
    assert 'reportInputDuringAgentSpeech="speech"' in twiml
    url_match = re.search(r'<ConversationRelay url="([^"]+)"', twiml)
    assert url_match
    parsed = urlsplit(html.unescape(url_match.group(1)))
    params = dict(item.split("=", 1) for item in parsed.query.split("&"))
    from urllib.parse import unquote_plus
    params = {key: unquote_plus(value) for key, value in params.items()}
    payload = {
        "tenant_id": params["tenant_id"],
        "call_sid": params["call_sid"],
        "from": params["from"],
        "to": params["to"],
        "direction": params["direction"],
    }
    assert verify_websocket_session(payload, params["sig"], int(params["ts"]), "relay-secret", 600)


def test_conversation_relay_websocket_forwards_prompt(monkeypatch):
    from fastapi.testclient import TestClient
    from voice_gateway.config import settings
    from voice_gateway import main as gateway

    monkeypatch.setattr(settings, "VOICE_GATEWAY_PUBLIC_URL", "https://voice.example.com")
    monkeypatch.setattr(settings, "VOICE_GATEWAY_TO_SVONTAI_SECRET", "relay-secret")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "twilio-auth-token")
    post_intent = AsyncMock(return_value={
        "responseText": "Tabii. Yarın saat iki uygun görünüyor. Onaylıyor musunuz?",
        "endCall": False,
    })
    monkeypatch.setattr(gateway, "_svontai_post_voice_intent", post_intent)
    ws_url = gateway._conversation_relay_ws_url(
        tenant_id="tenant-1",
        call_sid="CA-relay",
        from_number="+905551112233",
        to_number="+12404106113",
        direction="inbound",
    )
    parsed = urlsplit(ws_url)
    twilio_signature = base64.b64encode(
        hmac.new(
            b"twilio-auth-token",
            ws_url.encode(),
            hashlib.sha1,
        ).digest()
    ).decode()
    with TestClient(gateway.app).websocket_connect(
        f"{parsed.path}?{parsed.query}",
        headers={"x-twilio-signature": twilio_signature},
    ) as websocket:
        websocket.send_json({"type": "setup", "callSid": "CA-relay"})
        websocket.send_json({"type": "prompt", "voicePrompt": "Yarın randevu istiyorum", "last": True})
        messages = []
        while not messages or messages[-1]["last"] is not True:
            messages.append(websocket.receive_json())

    assert all(message["type"] == "text" for message in messages)
    assert messages[0]["last"] is False
    assert messages[-1]["last"] is True
    assert messages[-1]["interruptible"] is True
    payload = post_intent.await_args.args[0]
    assert payload["metadata"] == {"turn": 1, "transport": "conversation_relay"}
    assert payload["call"]["direction"] == "inbound"
