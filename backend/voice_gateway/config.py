from pydantic_settings import BaseSettings, SettingsConfigDict


class VoiceGatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)

    # Public base URL for this voice gateway (used for WS urls in TwiML)
    VOICE_GATEWAY_PUBLIC_URL: str = "http://localhost:9001"

    # SvontAI backend base url
    SVONTAI_BACKEND_URL: str = "http://localhost:8000"

    # Shared secret (must match backend VOICE_GATEWAY_TO_SVONTAI_SECRET)
    VOICE_GATEWAY_TO_SVONTAI_SECRET: str = "change-this-to-a-secure-random-string-voice-gateway-to-svontai"

    # Resolve endpoint + ingest endpoint paths (backend)
    SVONTAI_TELEPHONY_RESOLVE_PATH: str = "/api/v1/telephony/resolve"
    SVONTAI_VOICE_INGEST_PATH: str = "/api/v1/voice/events"


settings = VoiceGatewaySettings()

