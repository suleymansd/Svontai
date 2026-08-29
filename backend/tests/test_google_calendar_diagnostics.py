from __future__ import annotations

import asyncio
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from app.core.config import settings
from app.services.google_calendar_service import GoogleCalendarService


def test_google_oauth_requests_event_and_freebusy_scopes():
    snapshot = _snapshot_state()
    try:
        settings.BACKEND_URL = "https://api.svontai.test"
        settings.WEBHOOK_PUBLIC_URL = "https://api.svontai.test"
        settings.GOOGLE_CLIENT_ID = "client-id"
        settings.GOOGLE_CLIENT_SECRET = "client-secret"
        settings.GOOGLE_REDIRECT_URI = (
            "https://api.svontai.test/real-estate/calendar/google/callback"
        )

        auth_url = GoogleCalendarService(None)._build_auth_url("test-state")
        params = parse_qs(urlparse(auth_url).query)
        scopes = set(params["scope"][0].split())

        assert GoogleCalendarService.CALENDAR_EVENTS_SCOPE in scopes
        assert GoogleCalendarService.CALENDAR_FREEBUSY_SCOPE in scopes
        assert params["prompt"] == ["consent"]
        assert params["include_granted_scopes"] == ["true"]
        assert GoogleCalendarService.has_required_calendar_scopes(scopes)
        assert not GoogleCalendarService.has_required_calendar_scopes(
            {GoogleCalendarService.CALENDAR_EVENTS_SCOPE}
        )
    finally:
        _restore_state(snapshot)


def _snapshot_state() -> dict:
    return {
        "environment": settings.ENVIRONMENT,
        "backend_url": settings.BACKEND_URL,
        "webhook_public_url": settings.WEBHOOK_PUBLIC_URL,
        "google_client_id": settings.GOOGLE_CLIENT_ID,
        "google_client_secret": settings.GOOGLE_CLIENT_SECRET,
        "google_redirect_uri": settings.GOOGLE_REDIRECT_URI,
    }


def _restore_state(snapshot: dict) -> None:
    settings.ENVIRONMENT = snapshot["environment"]
    settings.BACKEND_URL = snapshot["backend_url"]
    settings.WEBHOOK_PUBLIC_URL = snapshot["webhook_public_url"]
    settings.GOOGLE_CLIENT_ID = snapshot["google_client_id"]
    settings.GOOGLE_CLIENT_SECRET = snapshot["google_client_secret"]
    settings.GOOGLE_REDIRECT_URI = snapshot["google_redirect_uri"]


def test_google_calendar_diagnostics_flags_invalid_redirect():
    snapshot = _snapshot_state()
    try:
        settings.ENVIRONMENT = "prod"
        settings.BACKEND_URL = "https://api.svontai.test"
        settings.WEBHOOK_PUBLIC_URL = "https://api.svontai.test"
        settings.GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
        settings.GOOGLE_CLIENT_SECRET = ""
        settings.GOOGLE_REDIRECT_URI = "http://wrong-domain.test/callback"

        service = GoogleCalendarService(db=None)  # type: ignore[arg-type]
        diagnostics = service.get_diagnostics()
        check_map = {item["key"]: item["ok"] for item in diagnostics["checks"]}

        assert diagnostics["google_client_id_set"] is False
        assert diagnostics["google_client_secret_set"] is False
        assert check_map["google_redirect_uri"] is False
        assert "GOOGLE_CLIENT_ID eksik" in diagnostics["issues"]
        assert "GOOGLE_REDIRECT_URI '/real-estate/calendar/google/callback' ile bitmelidir" in diagnostics["issues"]
    finally:
        _restore_state(snapshot)


def test_google_calendar_probe_reports_oauth_error():
    snapshot = _snapshot_state()
    try:
        settings.ENVIRONMENT = "prod"
        settings.BACKEND_URL = "https://api.svontai.test"
        settings.WEBHOOK_PUBLIC_URL = "https://api.svontai.test"
        settings.GOOGLE_CLIENT_ID = "google-client-id"
        settings.GOOGLE_CLIENT_SECRET = "google-secret"
        settings.GOOGLE_REDIRECT_URI = "https://api.svontai.test/real-estate/calendar/google/callback"

        service = GoogleCalendarService(db=None)  # type: ignore[arg-type]

        class FakeResponse:
            status_code = 302
            headers = {
                "location": "https://accounts.google.com/signin/oauth/error?error=invalid_request&error_description=redirect_uri_mismatch"
            }

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, *args, **kwargs):
                return FakeResponse()

        with patch("app.services.google_calendar_service.httpx.AsyncClient", new=FakeAsyncClient):
            probe = asyncio.run(service.probe_oauth_dialog())

        assert probe["status"] == "error"
        assert probe["error"] == "invalid_request"
        assert probe["error_description"] == "redirect_uri_mismatch"
    finally:
        _restore_state(snapshot)
