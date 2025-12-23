"""
Application configuration using Pydantic Settings.
All environment variables are loaded and validated here.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    # Database (SQLite for development, PostgreSQL for production)
    DATABASE_URL: str = "sqlite:///./smartwa.db"
    
    # JWT Configuration
    JWT_SECRET_KEY: str = "your-super-secret-jwt-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # WhatsApp Cloud API (Legacy - for direct integration)
    WHATSAPP_BASE_URL: str = "https://graph.facebook.com/v17.0"
    
    # Meta API Configuration (Embedded Signup)
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_REDIRECT_URI: str = "http://localhost:8000/api/onboarding/whatsapp/callback"
    META_CONFIG_ID: str = ""  # WhatsApp Embedded Signup Config ID
    GRAPH_API_VERSION: str = "v18.0"
    
    # Webhook Configuration
    WEBHOOK_PUBLIC_URL: str = "http://localhost:8000"  # Your public URL for webhooks
    
    # Encryption
    ENCRYPTION_KEY: str = ""  # 32-byte base64 encoded key, generated if not set
    
    # Application URLs
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Environment
    ENVIRONMENT: Literal["dev", "prod"] = "dev"
    
    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

