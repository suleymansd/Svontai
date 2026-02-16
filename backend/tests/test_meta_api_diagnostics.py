from __future__ import annotations

import asyncio
from unittest.mock import patch

from app.core.config import settings
from app.services.meta_api import meta_api_service


def _snapshot_state() -> dict:
    return {
        "service_app_id": meta_api_service.app_id,
        "service_app_secret": meta_api_service.app_secret,
        "service_redirect_uri": meta_api_service.redirect_uri,
        "service_api_version": meta_api_service.api_version,
        "service_graph_base": meta_api_service.graph_base,
        "settings_environment": settings.ENVIRONMENT,
        "settings_backend_url": settings.BACKEND_URL,
        "settings_webhook_public_url": settings.WEBHOOK_PUBLIC_URL,
        "settings_meta_config_id": settings.META_CONFIG_ID,
    }


def _restore_state(snapshot: dict) -> None:
    meta_api_service.app_id = snapshot["service_app_id"]
    meta_api_service.app_secret = snapshot["service_app_secret"]
    meta_api_service.redirect_uri = snapshot["service_redirect_uri"]
    meta_api_service.api_version = snapshot["service_api_version"]
    meta_api_service.graph_base = snapshot["service_graph_base"]
    settings.ENVIRONMENT = snapshot["settings_environment"]
    settings.BACKEND_URL = snapshot["settings_backend_url"]
    settings.WEBHOOK_PUBLIC_URL = snapshot["settings_webhook_public_url"]
    settings.META_CONFIG_ID = snapshot["settings_meta_config_id"]


def test_onboarding_diagnostics_flags_invalid_config():
    snapshot = _snapshot_state()
    try:
        settings.ENVIRONMENT = "prod"
        settings.BACKEND_URL = "https://api.svontai.test"
        settings.WEBHOOK_PUBLIC_URL = "https://api.svontai.test"
        settings.META_CONFIG_ID = "YOUR_CONFIG"

        meta_api_service.app_id = "YOUR_APP_ID"
        meta_api_service.app_secret = ""
        meta_api_service.redirect_uri = "http://wrong-domain.test/callback"

        diagnostics = meta_api_service.get_onboarding_diagnostics()
        check_map = {item["key"]: item["ok"] for item in diagnostics["checks"]}

        assert diagnostics["meta_app_id_set"] is False
        assert diagnostics["meta_app_secret_set"] is False
        assert diagnostics["meta_config_id_set"] is False
        assert check_map["meta_redirect_uri"] is False
        assert "META_APP_ID eksik" in diagnostics["issues"]
        assert "META_REDIRECT_URI '/api/onboarding/whatsapp/callback' ile bitmelidir" in diagnostics["issues"]
    finally:
        _restore_state(snapshot)


def test_probe_oauth_dialog_reports_meta_error_reason():
    snapshot = _snapshot_state()
    try:
        settings.ENVIRONMENT = "prod"
        settings.BACKEND_URL = "https://api.svontai.test"
        settings.WEBHOOK_PUBLIC_URL = "https://api.svontai.test"
        settings.META_CONFIG_ID = "123456789"

        meta_api_service.app_id = "1234567890"
        meta_api_service.app_secret = "secret-value"
        meta_api_service.redirect_uri = "https://api.svontai.test/api/onboarding/whatsapp/callback"
        meta_api_service.api_version = "v18.0"
        meta_api_service.graph_base = "https://graph.facebook.com/v18.0"

        class FakeResponse:
            status_code = 302
            headers = {
                "location": "https://www.facebook.com/login.php?error_reason=invalid_request&error_description=Invalid+Page"
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

        with patch("app.services.meta_api.httpx.AsyncClient", new=FakeAsyncClient):
            probe = asyncio.run(meta_api_service.probe_oauth_dialog())

        assert probe["status"] == "error"
        assert probe["error_reason"] == "invalid_request"
        assert probe["error_description"] == "Invalid Page"
    finally:
        _restore_state(snapshot)
