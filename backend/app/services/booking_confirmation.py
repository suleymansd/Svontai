"""Only an unambiguous affirmative response confirms a proposed booking."""

import re


def is_explicit_confirmation(text: str) -> bool:
    normalized = text.casefold().translate(str.maketrans("ıİşğüöç", "iİsguoc"))
    normalized = re.sub(r"[.,!\s]+", " ", normalized).strip()
    return normalized in {
        "evet", "tamam", "olur", "uygun", "onayliyorum", "onayla",
        "evet onayliyorum", "evet uygun", "tamam onayliyorum",
        "randevuyu onayliyorum", "onayliyorum tesekkurler",
        "yes", "confirm", "confirmed", "yes please", "i confirm",
    }
