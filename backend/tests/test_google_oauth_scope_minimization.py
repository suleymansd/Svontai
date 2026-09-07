import pytest

from app.core.config import settings
from app.services.google_calendar_service import GoogleCalendarError, GoogleCalendarService


def test_google_calendar_oauth_requests_only_calendar_scopes():
    scopes = set(GoogleCalendarService.SCOPES)

    assert GoogleCalendarService.CALENDAR_EVENTS_SCOPE in scopes
    assert GoogleCalendarService.CALENDAR_FREEBUSY_SCOPE in scopes
    assert "openid" in scopes
    assert "email" in scopes
    assert "profile" in scopes
    assert not any("gmail" in scope for scope in scopes)
    assert not any("drive" in scope for scope in scopes)
    assert not any("spreadsheets" in scope for scope in scopes)


def test_unverified_production_google_oauth_is_not_exposed(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_PUBLIC_ENABLED", False)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "production-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "production-client-secret")
    monkeypatch.setattr(
        settings,
        "GOOGLE_REDIRECT_URI",
        "https://api.svontai.test/real-estate/calendar/google/callback",
    )
    monkeypatch.setattr(settings, "BACKEND_URL", "https://api.svontai.test")

    with pytest.raises(GoogleCalendarError, match="production doğrulaması"):
        GoogleCalendarService(None).get_oauth_start(  # type: ignore[arg-type]
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        )
