import asyncio

from app.core.config import settings
from app.services.media_enrichment_service import MediaEnrichmentService


def test_media_enrichment_uses_safe_local_metadata_without_gemini(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    result = asyncio.run(MediaEnrichmentService().enrich(
        data=b"\x89PNG\r\n\x1a\ncontent",
        mime_type="image/png",
        media_type="image",
        title="Mavi koltuk takımı",
        description="",
        filename="mavi-koltuk.png",
        keywords=[],
    ))
    assert result.ai_analyzed is False
    assert "Mavi koltuk takımı" in result.description
    assert "Mavi" in result.keywords
    assert "koltuk" in result.keywords


def test_media_enrichment_accepts_structured_gemini_result(monkeypatch):
    from app.services import media_enrichment_service as module

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [{
                    "content": {"parts": [{"text": '{"description":"Ahşap yemek masası.","keywords":["masa","ahşap","mobilya"]}'}]}
                }]
            }

    class _Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return _Response()

    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(module.httpx, "AsyncClient", _Client)
    result = asyncio.run(MediaEnrichmentService().enrich(
        data=b"\xff\xd8\xffcontent",
        mime_type="image/jpeg",
        media_type="image",
        title="Ürün fotoğrafı",
        description="",
        filename="product.jpg",
        keywords=[],
    ))
    assert result.ai_analyzed is True
    assert result.description == "Ahşap yemek masası."
    assert "mobilya" in result.keywords
