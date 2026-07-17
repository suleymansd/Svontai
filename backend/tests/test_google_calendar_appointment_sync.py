from __future__ import annotations

import uuid
from datetime import timedelta

from app.core.time import utc_now_naive
from app.models.appointment import Appointment
from app.models.tenant import Tenant
from app.models.user import User
from app.models.google_oauth_token import GoogleOAuthToken
from app.services.google_calendar_service import GoogleCalendarService


class _GoogleResponse:
    def __init__(self, *, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""
        self.is_success = 200 <= status_code < 300

    def json(self) -> dict:
        return self._payload


def test_google_calendar_sync_creates_and_cancels_appointment(client, monkeypatch):
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        user = User(
            email=f"calendar-sync-{uuid.uuid4().hex}@example.com",
            password_hash="unused",
            full_name="Calendar Sync Test",
        )
        db.add(user)
        db.flush()
        tenant = Tenant(
            name="Calendar Sync Tenant",
            slug=f"calendar-sync-{uuid.uuid4().hex}",
            owner_id=user.id,
        )
        db.add(tenant)
        db.flush()
        appointment = Appointment(
            tenant_id=tenant.id,
            created_by=user.id,
            customer_name="Müşteri",
            customer_email="customer@example.com",
            subject="Tanışma görüşmesi",
            notes="Kısa ürün demosu",
            starts_at=utc_now_naive() + timedelta(days=1),
        )
        db.add(appointment)
        db.commit()

        service = GoogleCalendarService(db)
        monkeypatch.setattr(service, "_tenant_access_token", lambda _: "access-token")
        post_calls = []

        def fake_post(url, **kwargs):
            post_calls.append((url, kwargs))
            return _GoogleResponse(payload={"id": "google-event-1"})

        monkeypatch.setattr("app.services.google_calendar_service.httpx.post", fake_post)
        assert service.sync_appointment(appointment) == "synced"
        assert appointment.calendar_event_id == "google-event-1"
        assert appointment.calendar_sync_status == "synced"
        assert post_calls[0][1]["params"] == {"sendUpdates": "none"}
        assert post_calls[0][1]["json"]["extendedProperties"]["private"]["svontai_appointment_id"] == str(
            appointment.id
        )

        delete_calls = []
        monkeypatch.setattr(
            "app.services.google_calendar_service.httpx.delete",
            lambda url, **kwargs: delete_calls.append((url, kwargs)) or _GoogleResponse(status_code=204),
        )
        appointment.status = "cancelled"
        appointment.calendar_sync_status = "pending"
        db.commit()
        assert service.sync_appointment(appointment) == "cancelled"
        assert appointment.calendar_sync_status == "cancelled"
        assert delete_calls[0][0].endswith("/google-event-1")
    finally:
        db.close()


def test_google_calendar_pull_updates_local_appointment(client, monkeypatch):
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        user = User(
            email=f"calendar-pull-{uuid.uuid4().hex}@example.com",
            password_hash="unused",
            full_name="Calendar Pull Test",
        )
        db.add(user)
        db.flush()
        tenant = Tenant(
            name="Calendar Pull Tenant",
            slug=f"calendar-pull-{uuid.uuid4().hex}",
            owner_id=user.id,
        )
        db.add(tenant)
        db.flush()
        appointment = Appointment(
            tenant_id=tenant.id,
            created_by=user.id,
            customer_name="Müşteri",
            subject="Eski başlık",
            starts_at=utc_now_naive() + timedelta(days=1),
            calendar_provider="google",
            calendar_event_id="google-event-pull",
            calendar_sync_status="synced",
        )
        db.add(appointment)
        db.add(GoogleOAuthToken(
            tenant_id=tenant.id,
            provider="google",
            scopes_json=[GoogleCalendarService.CALENDAR_EVENTS_SCOPE],
        ))
        db.commit()

        service = GoogleCalendarService(db)
        monkeypatch.setattr(service, "_tenant_access_token", lambda _: "access-token")
        changed_at = (utc_now_naive() + timedelta(days=2)).replace(microsecond=0)
        monkeypatch.setattr(
            "app.services.google_calendar_service.httpx.get",
            lambda *args, **kwargs: _GoogleResponse(payload={
                "items": [{
                    "id": "google-event-pull",
                    "status": "confirmed",
                    "summary": "Google'da güncellendi",
                    "start": {"dateTime": changed_at.isoformat() + "Z"},
                    "extendedProperties": {
                        "private": {"svontai_appointment_id": str(appointment.id)}
                    },
                }],
                "nextSyncToken": "next-sync-token",
            }),
        )

        result = service.pull_appointment_updates()
        db.refresh(appointment)
        db.refresh(tenant)
        assert result == {"tenants": 1, "events": 1, "updated": 1, "failed": 0}
        assert appointment.subject == "Google'da güncellendi"
        assert appointment.starts_at == changed_at
        assert tenant.settings["google_calendar_appointment_sync_token"] == "next-sync-token"
    finally:
        db.close()
