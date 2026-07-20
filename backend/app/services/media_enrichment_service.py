"""Best-effort, privacy-conscious metadata enrichment for assistant media."""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_STOP_WORDS = {
    "bir", "bu", "icin", "için", "ile", "ve", "veya", "the", "and", "pdf", "jpg", "jpeg",
    "png", "webp", "mp4", "dosya", "medya", "gorsel", "görsel",
}


@dataclass(slots=True)
class MediaEnrichment:
    description: str
    keywords: list[str]
    ai_analyzed: bool


class MediaEnrichmentService:
    MAX_INLINE_BYTES = 15 * 1024 * 1024

    @staticmethod
    def _heuristic(
        *,
        title: str,
        description: str,
        filename: str,
        media_type: str,
        keywords: list[str],
    ) -> MediaEnrichment:
        source = " ".join((title, description, filename.rsplit(".", 1)[0]))
        tokens = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]{3,}", source, flags=re.UNICODE)
        combined = [*keywords, media_type]
        combined.extend(token for token in tokens if token.casefold() not in _STOP_WORDS)
        normalized: list[str] = []
        seen: set[str] = set()
        for value in combined:
            item = str(value).strip()[:60]
            key = item.casefold()
            if item and key not in seen:
                normalized.append(item)
                seen.add(key)
            if len(normalized) >= 12:
                break
        type_name = {"image": "görsel", "video": "video", "catalog": "PDF katalog"}[media_type]
        return MediaEnrichment(
            description=description.strip() or f"{title.strip()} için yüklenen {type_name} içeriği.",
            keywords=normalized,
            ai_analyzed=False,
        )

    async def enrich(
        self,
        *,
        data: bytes,
        mime_type: str,
        media_type: str,
        title: str,
        description: str,
        filename: str,
        keywords: list[str],
    ) -> MediaEnrichment:
        fallback = self._heuristic(
            title=title,
            description=description,
            filename=filename,
            media_type=media_type,
            keywords=keywords,
        )
        if (
            settings.AI_PROVIDER != "gemini"
            or not settings.GEMINI_API_KEY.strip()
            or len(data) > self.MAX_INLINE_BYTES
        ):
            return fallback

        model = quote(settings.ai_model.strip(), safe="-._")
        if not model:
            return fallback
        prompt = (
            "Bu işletme medyasını müşteriye doğru zamanda gönderecek bir asistan için analiz et. "
            "Yalnızca dosyada açıkça görülen veya okunan bilgileri kullan; fiyat, özellik veya marka uydurma. "
            "Türkçe JSON döndür: description alanı en fazla 300 karakterlik nesnel açıklama, "
            "keywords alanı en fazla 10 kısa arama niyeti/ürün/hizmet etiketi olsun."
        )
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(data).decode()}},
                    {"text": prompt},
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 350,
                "responseMimeType": "application/json",
            },
        }
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": settings.GEMINI_API_KEY.strip()},
                    json=payload,
                )
            response.raise_for_status()
            result = response.json()
            text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
            parsed = json.loads(text)
            ai_description = str(parsed.get("description") or "").strip()[:300]
            ai_keywords = parsed.get("keywords") if isinstance(parsed.get("keywords"), list) else []
            merged = self._heuristic(
                title=title,
                description=description.strip() or ai_description,
                filename=filename,
                media_type=media_type,
                keywords=[*keywords, *(str(value) for value in ai_keywords)],
            )
            merged.ai_analyzed = bool(ai_description or ai_keywords)
            return merged
        except Exception as exc:
            logger.warning("Media metadata enrichment skipped: %s", type(exc).__name__)
            return fallback
