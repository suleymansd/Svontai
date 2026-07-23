"""Small TwiML helpers shared by the voice gateway adapters."""

import re
import unicodedata
from xml.sax.saxutils import escape

from voice_gateway.config import settings


def xml_text(value: str) -> str:
    return escape(value or "")


def xml_attr(value: str) -> str:
    return escape(value or "", {'"': "&quot;"})


def normalize_spoken_text(value: str) -> str:
    """Normalize product and technical terms for Turkish text-to-speech."""
    text = str(value or "")
    replacements = (
        (r"\bSvontAI\b", "Svont Ay"),
        (r"\bWhatsApp\b", "Vatsap"),
        (r"\bQR\b", "kare kod"),
        (r"\bAI\b", "yapay zekâ"),
        (r"\bURL\b", "internet adresi"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"[*_`#]+", "", text)
    text = "".join(
        char for char in text
        if unicodedata.category(char) not in {"So", "Cs"}
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def say(value: str) -> str:
    voice = xml_attr(settings.TWILIO_TTS_VOICE)
    language = xml_attr(settings.TWILIO_TTS_LANGUAGE)
    return f'<Say voice="{voice}" language="{language}">{xml_text(normalize_spoken_text(value))}</Say>'


def gather(value: str, action_url: str) -> str:
    model = xml_attr(settings.TWILIO_GATHER_SPEECH_MODEL)
    speech_timeout = xml_attr(settings.TWILIO_GATHER_SPEECH_TIMEOUT)
    hints = xml_attr(settings.TWILIO_SPEECH_HINTS)
    return (
        f'<Gather input="speech" language="tr-TR" speechModel="{model}" '
        f'speechTimeout="{speech_timeout}" actionOnEmptyResult="true" '
        f'hints="{hints}" action="{xml_attr(action_url)}" method="POST">'
        f'{say(value)}</Gather>'
    )
