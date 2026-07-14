import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

from app.api.routers.webhooks_alias import _verify_webhook_basic_auth
from app.core.config import settings


def test_webhook_alias_is_unavailable_when_credentials_are_missing(monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_USERNAME", "")
    monkeypatch.setattr(settings, "WEBHOOK_PASSWORD", "")

    with pytest.raises(HTTPException) as exc_info:
        _verify_webhook_basic_auth(None)

    assert exc_info.value.status_code == 503


def test_webhook_alias_accepts_valid_credentials(monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_USERNAME", "webhook-user")
    monkeypatch.setattr(settings, "WEBHOOK_PASSWORD", "webhook-password")

    result = _verify_webhook_basic_auth(
        HTTPBasicCredentials(username="webhook-user", password="webhook-password")
    )

    assert result is None
