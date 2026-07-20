"""Small TwiML helpers shared by the voice gateway adapters."""

from xml.sax.saxutils import escape

from voice_gateway.config import settings


def xml_text(value: str) -> str:
    return escape(value or "")


def xml_attr(value: str) -> str:
    return escape(value or "", {'"': "&quot;"})


def say(value: str) -> str:
    voice = xml_attr(settings.TWILIO_TTS_VOICE)
    language = xml_attr(settings.TWILIO_TTS_LANGUAGE)
    return f'<Say voice="{voice}" language="{language}">{xml_text(value)}</Say>'
