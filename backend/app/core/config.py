"""
Application configuration using Pydantic Settings.
All environment variables are loaded and validated here.
"""

import logging
from functools import lru_cache
from typing import Literal, Optional
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

logger = logging.getLogger(__name__)

# Insecure default secrets that must not be used in production
INSECURE_DEFAULT_SECRETS = [
    "change-this-to-a-secure-random-string-svontai-to-n8n",
    "change-this-to-a-secure-random-string-n8n-to-svontai",
    "change-this-to-a-secure-random-string-voice-gateway-to-svontai",
    "your-super-secret-jwt-key-change-in-production",
]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    # Database (SQLite for development, PostgreSQL for production)
    DATABASE_URL: str = "sqlite:///./smartwa.db"
    PGHOST: str = ""
    PGPORT: str = ""
    PGUSER: str = ""
    PGPASSWORD: str = ""
    PGDATABASE: str = ""
    
    # JWT Configuration
    JWT_SECRET_KEY: str = "your-super-secret-jwt-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    SUPER_ADMIN_REQUIRE_2FA: bool = False

    # API key hashing (separate secret recommended; falls back to JWT_SECRET_KEY)
    API_KEY_HASH_SECRET: str = ""
    
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

    # Email / SMTP
    EMAIL_ENABLED: bool = False
    EMAIL_PROVIDER: Literal["resend", "smtp"] = "resend"

    # Resend
    RESEND_API_KEY: str = ""
    RESEND_API_BASE_URL: str = "https://api.resend.com"
    RESEND_TIMEOUT_SECONDS: int = 20

    # SMTP (optional fallback)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@svontai.com"
    SMTP_FROM_NAME: str = "SvontAI"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: int = 20

    # Password reset
    PASSWORD_RESET_CODE_EXPIRE_MINUTES: int = 10
    PASSWORD_RESET_MAX_ATTEMPTS: int = 5
    EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES: int = 15
    EMAIL_VERIFICATION_MAX_ATTEMPTS: int = 5

    # Appointment reminders (background loop)
    APPOINTMENT_REMINDER_ENABLED: bool = True
    APPOINTMENT_REMINDER_INTERVAL_SECONDS: int = 60

    # Real Estate automation scheduler
    REAL_ESTATE_AUTOMATION_ENABLED: bool = True
    REAL_ESTATE_AUTOMATION_INTERVAL_SECONDS: int = 300
    REAL_ESTATE_WEEKLY_REPORT_DAY: int = 0  # Monday=0 ... Sunday=6
    REAL_ESTATE_WEEKLY_REPORT_HOUR_UTC: int = 8

    # Google Calendar OAuth (Real Estate Pack)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/real-estate/calendar/google/callback"

    # Payments
    PAYMENTS_ENABLED: bool = False
    PAYMENTS_PROVIDER: Literal["stripe"] = "stripe"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_SUCCESS_URL: str = ""
    STRIPE_CANCEL_URL: str = ""
    STRIPE_PORTAL_RETURN_URL: str = ""
    # Convenience envs (optional). If STRIPE_PRICE_IDS is empty these seed monthly map.
    STRIPE_PRICE_ID_PRO: str = ""
    STRIPE_PRICE_ID_PREMIUM: str = ""
    # Example:
    # STRIPE_PRICE_IDS='{"pro":{"monthly":"price_...","yearly":"price_..."}}'
    STRIPE_PRICE_IDS: dict[str, dict[str, str]] = {}

    # Security: allow upgrading to paid plans without payment (dev/demo only)
    ALLOW_UNPAID_PLAN_UPGRADES: bool = True
    
    # Environment
    ENVIRONMENT: Literal["dev", "prod"] = "dev"
    
    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379"
    
    # ===========================================
    # n8n Workflow Engine Integration
    # ===========================================
    # Feature flag: Set to True to enable n8n workflow execution
    USE_N8N: bool = False
    
    # n8n Base URL (internal network or external)
    N8N_BASE_URL: str = "http://n8n:5678"
    
    # Optional n8n API key for authenticated requests
    N8N_API_KEY: Optional[str] = None
    
    # Shared secrets for secure communication between SvontAI and n8n
    # Used for HMAC signature verification
    SVONTAI_TO_N8N_SECRET: str = "change-this-to-a-secure-random-string-svontai-to-n8n"
    N8N_TO_SVONTAI_SECRET: str = "change-this-to-a-secure-random-string-n8n-to-svontai"

    # ===========================================
    # Voice Gateway Integration (HMAC)
    # ===========================================
    VOICE_GATEWAY_TO_SVONTAI_SECRET: str = "change-this-to-a-secure-random-string-voice-gateway-to-svontai"
    
    # Default workflow ID for incoming WhatsApp messages
    N8N_INCOMING_WORKFLOW_ID: str = ""
    
    # Request timeout for n8n API calls (seconds)
    N8N_TIMEOUT_SECONDS: int = 10
    # Tool runner specific timeout (0 = fallback to N8N_TIMEOUT_SECONDS)
    N8N_TOOL_RUNNER_TIMEOUT_SECONDS: int = 0
    
    # Number of retries for failed n8n requests
    N8N_RETRY_COUNT: int = 2
    # Tool runner specific retries (fallback to N8N_RETRY_COUNT when < 0)
    N8N_TOOL_RUNNER_RETRIES: int = -1
    # Exponential backoff base in seconds for tool runner retry
    N8N_TOOL_RUNNER_BACKOFF_SECONDS: float = 0.5
    
    # n8n webhook path pattern (used for triggering workflows)
    N8N_WEBHOOK_PATH: str = "/webhook"
    # Internal API endpoint template for tool runner workflow execution
    N8N_INTERNAL_RUN_ENDPOINT_TEMPLATE: str = "/api/v1/workflows/{workflow_id}/run"
    # Shared runner workflow identifier (can be overridden per-tool with tools.n8n_workflow_id)
    N8N_TOOL_RUNNER_WORKFLOW_ID: str = "svontai-tool-runner"

    # ===========================================
    # Artifact Storage (Tool outputs)
    # ===========================================
    ARTIFACT_STORAGE_PROVIDER: Literal["local", "supabase"] = "local"
    ARTIFACT_STORAGE_LOCAL_BASE_PATH: str = "storage/artifacts"
    ARTIFACT_SIGNED_URL_EXPIRES_SECONDS: int = 3600
    ARTIFACT_SIGNING_SECRET: str = ""

    # Supabase Storage (v1 real provider for Railway)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "svontai-artifacts"

    @model_validator(mode='after')
    def normalize_database_url(self) -> 'Settings':
        """Normalize DATABASE_URL for Railway/Postgres variants."""
        raw_url = (self.DATABASE_URL or "").strip().strip('"').strip("'")

        if (
            (not raw_url or raw_url.startswith("${"))
            and self.PGHOST
            and self.PGPORT
            and self.PGUSER
            and self.PGDATABASE
        ):
            encoded_password = quote_plus(self.PGPASSWORD or "")
            raw_url = (
                "postgresql+psycopg://"
                f"{self.PGUSER}:{encoded_password}@{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"
            )

        if raw_url.startswith("postgres://"):
            raw_url = raw_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif raw_url.startswith("postgresql://"):
            raw_url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif raw_url.startswith("postgresql+psycopg2://"):
            raw_url = raw_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

        self.DATABASE_URL = raw_url or "sqlite:///./smartwa.db"
        return self

    @model_validator(mode="after")
    def validate_prod_payment_settings(self) -> "Settings":
        if self.ENVIRONMENT == "prod":
            self.ALLOW_UNPAID_PLAN_UPGRADES = False
        return self

    @model_validator(mode="after")
    def normalize_stripe_price_ids(self) -> "Settings":
        normalized: dict[str, dict[str, str]] = {
            str(plan).strip(): {
                str(interval).strip(): str(price_id).strip()
                for interval, price_id in (intervals or {}).items()
                if str(price_id).strip()
            }
            for plan, intervals in (self.STRIPE_PRICE_IDS or {}).items()
        }
        normalized = {plan: intervals for plan, intervals in normalized.items() if intervals}

        if not normalized:
            if self.STRIPE_PRICE_ID_PRO.strip():
                normalized["pro"] = {"monthly": self.STRIPE_PRICE_ID_PRO.strip()}
            if self.STRIPE_PRICE_ID_PREMIUM.strip():
                normalized["premium"] = {"monthly": self.STRIPE_PRICE_ID_PREMIUM.strip()}

        self.STRIPE_PRICE_IDS = normalized
        return self

    @model_validator(mode='after')
    def validate_production_secrets(self) -> 'Settings':
        """
        Validate that insecure default secrets are not used in production.
        
        Raises ValueError at startup if:
        - ENVIRONMENT is 'prod' AND
        - Any of the security-sensitive secrets are set to their insecure defaults
        """
        if self.ENVIRONMENT != "prod":
            return self
        
        # Check JWT secret
        if self.JWT_SECRET_KEY in INSECURE_DEFAULT_SECRETS:
            raise ValueError(
                "FATAL: JWT_SECRET_KEY is set to an insecure default value. "
                "You MUST set a secure, randomly generated secret in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        # Only validate n8n secrets if n8n is enabled
        if self.USE_N8N:
            if self.SVONTAI_TO_N8N_SECRET in INSECURE_DEFAULT_SECRETS:
                raise ValueError(
                    "FATAL: SVONTAI_TO_N8N_SECRET is set to an insecure default value. "
                    "You MUST set a secure, randomly generated secret in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            
            if self.N8N_TO_SVONTAI_SECRET in INSECURE_DEFAULT_SECRETS:
                raise ValueError(
                    "FATAL: N8N_TO_SVONTAI_SECRET is set to an insecure default value. "
                    "You MUST set a secure, randomly generated secret in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )

        if self.VOICE_GATEWAY_TO_SVONTAI_SECRET in INSECURE_DEFAULT_SECRETS:
            raise ValueError(
                "FATAL: VOICE_GATEWAY_TO_SVONTAI_SECRET is set to an insecure default value. "
                "You MUST set a secure, randomly generated secret in production."
            )
        
        return self


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
