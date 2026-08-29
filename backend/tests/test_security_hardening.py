"""Regression tests for production security boundaries."""

from __future__ import annotations

import hashlib
import socket
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers.channels import _update_run_failed, _update_run_success
from app.api.routers.whatsapp import create_whatsapp_integration
from app.core.encryption import decrypt_token
from app.core.egress import UnsafeOutboundURLError, validate_outbound_https_url
from app.core.request_limits import RequestBodyLimitMiddleware
from app.core.time import utc_now_naive
from app.core.widget_session import (
    InvalidWidgetSession,
    issue_widget_session,
    verify_widget_session,
)
from app.db.base import Base
from app.models.automation import AutomationRun, AutomationRunStatus
from app.models.bot import Bot
from app.models.oauth_state import OAuthState
from app.models.tenant import Tenant
from app.models.user import User
from app.models.whatsapp import WhatsAppIntegration
from app.schemas.whatsapp import WhatsAppIntegrationCreate, WhatsAppIntegrationResponse
from app.services.onboarding_service import OnboardingService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.oauth_state_service import InvalidOAuthState, OAuthStateService


def _session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _user_and_tenant(db, suffix: str) -> tuple[User, Tenant]:
    user = User(
        email=f"security-{suffix}@test.local",
        password_hash="hash",
        full_name="Security Test",
    )
    db.add(user)
    db.flush()
    tenant = Tenant(name=f"Tenant {suffix}", owner_id=user.id, settings={})
    db.add(tenant)
    db.commit()
    return user, tenant


def test_meta_oauth_state_is_single_use_and_tenant_bound():
    db = _session()
    user, tenant = _user_and_tenant(db, "oauth")
    raw_state = "opaque-state-value"
    db.add(
        OAuthState(
            provider="meta",
            state_hash=hashlib.sha256(raw_state.encode()).hexdigest(),
            tenant_id=tenant.id,
            user_id=user.id,
            expires_at=utc_now_naive() + timedelta(minutes=10),
        )
    )
    db.commit()

    consumed = OnboardingService(db).consume_oauth_state(raw_state)
    assert consumed.tenant_id == tenant.id
    assert consumed.user_id == user.id
    assert consumed.consumed_at is not None

    with pytest.raises(ValueError):
        OnboardingService(db).consume_oauth_state(raw_state)
    with pytest.raises(ValueError):
        OnboardingService(db).consume_oauth_state(f"{tenant.id}:forged")


def test_google_oauth_state_is_opaque_single_use_and_user_bound(monkeypatch):
    db = _session()
    user, tenant = _user_and_tenant(db, "google-oauth")
    service = GoogleCalendarService(db)
    monkeypatch.setattr(service, "validate_config", lambda: None)

    result = service.get_oauth_start(tenant.id, user.id)
    assert str(tenant.id) not in result["state"]
    assert str(user.id) not in result["state"]

    consumed = OAuthStateService(db).consume(
        provider="google",
        state=result["state"],
    )
    assert consumed.tenant_id == tenant.id
    assert consumed.user_id == user.id

    with pytest.raises(InvalidOAuthState):
        OAuthStateService(db).consume(provider="google", state=result["state"])


def test_google_callback_redirects_to_trusted_frontend_without_inline_script(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FRONTEND_URL", "https://www.svontai.test")
    monkeypatch.setattr(
        GoogleCalendarService,
        "process_oauth_callback",
        lambda self, code, state: object(),
    )

    response = client.get(
        "/real-estate/calendar/google/callback?code=test-code&state=test-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "https://www.svontai.test/oauth/google/callback?success=1"
    )
    assert "<script" not in response.text.lower()


def test_meta_callback_redirects_to_trusted_frontend_without_inline_script(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FRONTEND_URL", "https://www.svontai.test")
    tenant_id = uuid.uuid4()
    monkeypatch.setattr(
        OnboardingService,
        "consume_oauth_state",
        lambda self, state: SimpleNamespace(tenant_id=tenant_id),
    )

    async def fake_process(self, resolved_tenant_id, code):
        assert resolved_tenant_id == tenant_id
        return object()

    monkeypatch.setattr(OnboardingService, "process_oauth_callback", fake_process)
    response = client.get(
        "/api/onboarding/whatsapp/callback?code=test-code&state=test-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "https://www.svontai.test/oauth/whatsapp/callback?success=1"
    )
    assert "<script" not in response.text.lower()


def test_outbound_url_rejects_private_and_unapproved_hosts(monkeypatch):
    def fake_getaddrinfo(host: str, *_args, **_kwargs):
        address = "10.0.0.8" if host == "internal.example" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UnsafeOutboundURLError):
        validate_outbound_https_url("http://public.example/path")
    with pytest.raises(UnsafeOutboundURLError):
        validate_outbound_https_url("https://internal.example/metadata")
    with pytest.raises(UnsafeOutboundURLError):
        validate_outbound_https_url(
            "https://attacker.example/path",
            allowed_hosts={"connector.example"},
        )
    assert validate_outbound_https_url(
        "https://api.connector.example/listings",
        allowed_hosts={"connector.example"},
    ) == "https://api.connector.example/listings"


def test_widget_session_detects_tampering_and_expiry():
    conversation_id = uuid.uuid4()
    bot_id = uuid.uuid4()
    token = issue_widget_session(
        conversation_id=conversation_id,
        bot_id=bot_id,
        external_user_id="widget-user",
    )
    session = verify_widget_session(token)
    assert session.conversation_id == conversation_id
    assert session.bot_id == bot_id

    with pytest.raises(InvalidWidgetSession):
        verify_widget_session(f"{token[:-1]}x")
    with pytest.raises(InvalidWidgetSession):
        verify_widget_session(
            issue_widget_session(
                conversation_id=conversation_id,
                bot_id=bot_id,
                external_user_id="widget-user",
                ttl_seconds=-1,
            )
        )


def test_request_body_limit_rejects_fixed_and_chunked_payloads():
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware, default_limit=32)

    @app.post("/echo")
    async def echo(request: Request):
        return {"size": len(await request.body())}

    with TestClient(app) as client:
        assert client.post("/echo", content=b"a" * 33).status_code == 413
        assert client.post("/echo", content=(chunk for chunk in [b"a" * 20, b"b" * 20])).status_code == 413
        assert client.post("/echo", content=b"a" * 32).status_code == 200


def test_automation_run_updates_are_tenant_scoped():
    db = _session()
    _, tenant_a = _user_and_tenant(db, "run-a")
    _, tenant_b = _user_and_tenant(db, "run-b")
    run = AutomationRun(
        tenant_id=str(tenant_b.id),
        from_number="+905551112233",
        status=AutomationRunStatus.RECEIVED.value,
    )
    db.add(run)
    db.commit()

    _update_run_success(db, str(run.id), tenant_a.id, {"forged": True})
    db.refresh(run)
    assert run.status == AutomationRunStatus.RECEIVED.value

    _update_run_failed(db, str(run.id), tenant_b.id, "expected failure")
    db.refresh(run)
    assert run.status == AutomationRunStatus.FAILED.value
    assert run.error_message == "expected failure"


@pytest.mark.asyncio
async def test_legacy_whatsapp_credentials_are_encrypted_and_not_serialized():
    db = _session()
    user, tenant = _user_and_tenant(db, "legacy-whatsapp")
    bot = Bot(tenant_id=tenant.id, name="Security Bot", is_active=True)
    db.add(bot)
    db.commit()

    integration = await create_whatsapp_integration(
        bot_id=bot.id,
        integration_data=WhatsAppIntegrationCreate(
            whatsapp_phone_number_id="phone-id",
            whatsapp_business_account_id="waba-id",
            access_token="plain-access-token",
            webhook_verify_token="plain-verify-token",
        ),
        current_tenant=tenant,
        current_user=user,
        db=db,
        request=None,
        _=None,
    )
    stored = db.query(WhatsAppIntegration).filter(WhatsAppIntegration.id == integration.id).one()
    assert stored.access_token_encrypted != "plain-access-token"
    assert stored.webhook_verify_token_encrypted != "plain-verify-token"
    assert decrypt_token(stored.access_token_encrypted) == "plain-access-token"
    assert decrypt_token(stored.webhook_verify_token_encrypted) == "plain-verify-token"
    serialized = WhatsAppIntegrationResponse.model_validate(stored).model_dump()
    assert "access_token" not in serialized
    assert "webhook_verify_token" not in serialized
