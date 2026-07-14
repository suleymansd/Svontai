import re


def _extract_6_digit_code(message: str) -> str:
    match = re.search(r"(\d{6})", message or "")
    assert match, f"Could not extract verification code from message: {message!r}"
    return match.group(1)


def _auth_headers(access_token: str, tenant_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id
    return headers


def _create_tenant_session(client, email: str = "voice@example.com") -> tuple[str, str]:
    password = "Password123!"
    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Voice User"},
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
        json={"customer_phone": "+905559998877", "customer_name": "Test Lead"},
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
        json={"customer_phone": "+905559998877", "customer_name": "Live Test Lead"},
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
