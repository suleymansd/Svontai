from app.services.google_calendar_service import GoogleCalendarService


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
