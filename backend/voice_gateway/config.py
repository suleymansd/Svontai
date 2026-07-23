from pydantic_settings import BaseSettings, SettingsConfigDict


class VoiceGatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Public base URL for this voice gateway (used for WS urls in TwiML)
    VOICE_GATEWAY_PUBLIC_URL: str = "http://localhost:9001"

    # SvontAI backend base url
    SVONTAI_BACKEND_URL: str = "http://localhost:8000"

    # Shared secret (must match backend VOICE_GATEWAY_TO_SVONTAI_SECRET)
    VOICE_GATEWAY_TO_SVONTAI_SECRET: str = "change-this-to-a-secure-random-string-voice-gateway-to-svontai"
    TWILIO_AUTH_TOKEN: str = ""

    # Resolve endpoint + ingest endpoint paths (backend)
    SVONTAI_TELEPHONY_RESOLVE_PATH: str = "/api/v1/telephony/resolve"
    SVONTAI_VOICE_INGEST_PATH: str = "/api/v1/voice/events"
    SVONTAI_VOICE_INTENT_PATH: str = "/api/v1/voice/intent"

    # Twilio voice mode:
    # - gather: IVR-style STT via Twilio <Gather input="speech"> (production friendly, low complexity)
    # - conversation_relay: realtime STT/TTS with interruption support (Twilio onboarding required)
    # - stream: legacy Media Streams websocket fallback
    TWILIO_VOICE_MODE: str = "gather"
    TWILIO_TTS_VOICE: str = "Google.tr-TR-Wavenet-D"
    TWILIO_TTS_LANGUAGE: str = "tr-TR"
    TWILIO_GATHER_SPEECH_MODEL: str = "googlev2_telephony_short"
    TWILIO_GATHER_SPEECH_TIMEOUT: str = "1"
    TWILIO_SPEECH_HINTS: str = "randevu,rezervasyon,fiyat,adres,çalışma saatleri,WhatsApp,evet,hayır"

    # ConversationRelay accepts provider-specific voice IDs without the <Say> prefix.
    TWILIO_RELAY_TTS_PROVIDER: str = "Google"
    TWILIO_RELAY_TTS_VOICE: str = "tr-TR-Wavenet-D"
    TWILIO_RELAY_TRANSCRIPTION_PROVIDER: str = "Google"
    TWILIO_RELAY_SPEECH_MODEL: str = "long"
    TWILIO_RELAY_SPEECH_TIMEOUT_MS: int = 800
    TWILIO_RELAY_INTERRUPT_SENSITIVITY: str = "medium"
    TWILIO_RELAY_WS_TOKEN_TTL_SECONDS: int = 600


settings = VoiceGatewaySettings()
