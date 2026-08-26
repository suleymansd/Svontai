"""Shared deterministic policies for customer conversation routing."""

from __future__ import annotations

import re


HUMAN_SUPPORT_REQUEST_RE = re.compile(
    r"\b(?:(?:müşteri\s+)?temsilci(?:si)?(?:yle|ye)?|canlı\s+deste(?:k|ğe)|"
    r"yetkili(?:yle|ye)?|insanla|birisiyle|biriyle)\b"
    r".{0,32}\b(?:istiyorum|isterim|görüşmek|görüşeyim|konuşmak|konuşayım|bağla|aktar)\w*\b",
    re.IGNORECASE,
)


def requests_human_support(message: str | None) -> bool:
    """Return true only for an explicit request to speak with a human."""
    return bool(HUMAN_SUPPORT_REQUEST_RE.search(message or ""))
