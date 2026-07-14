from unittest.mock import patch


def test_gemini_provider_uses_google_compatible_endpoint(monkeypatch):
    from app.core.config import settings
    from app.services.ai_service import AIService

    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-test-key")

    with patch("app.services.ai_service.AsyncOpenAI") as client_class:
        service = AIService()

    client_class.assert_called_once_with(
        api_key="gemini-test-key",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    assert service.provider == "gemini"
    assert service.model == "gemini-2.5-flash-lite"


def test_openai_provider_remains_backwards_compatible(monkeypatch):
    from app.core.config import settings
    from app.services.ai_service import AIService

    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "AI_MODEL", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    with patch("app.services.ai_service.AsyncOpenAI") as client_class:
        service = AIService()

    client_class.assert_called_once_with(api_key="openai-test-key")
    assert service.provider == "openai"
    assert service.model == "gpt-4o-mini"
