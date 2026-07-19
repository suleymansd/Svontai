"""
Application configuration using Pydantic Settings.
All environment variables are loaded and validated here.
"""

import base64
import logging
from functools import lru_cache
from pathlib import Path
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
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    ALLOW_ADMIN_PLAN_OVERRIDE: bool = False
    ALLOW_DEMO_SEED: bool = False

    # API key hashing (separate secret recommended; falls back to JWT_SECRET_KEY)
    API_KEY_HASH_SECRET: str = ""
    
    # AI provider. Gemini uses Google's OpenAI-compatible endpoint so the
    # application keeps a single client contract.
    AI_PROVIDER: Literal["openai", "gemini"] = "openai"
    AI_MODEL: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    
    # WhatsApp Cloud API (Legacy - for direct integration)
    WHATSAPP_BASE_URL: str = "https://graph.facebook.com/v17.0"
    
    # Meta API Configuration (Embedded Signup)
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_REDIRECT_URI: str = "http://localhost:8000/api/onboarding/whatsapp/callback"
    META_CONFIG_ID: str = ""  # WhatsApp Embedded Signup Config ID
    GRAPH_API_VERSION: str = "v18.0"

    # OpenWA QR provider. OpenWA runs as a separate persistent service and
    # connects regular WhatsApp or WhatsApp Business accounts through QR pairing.
    OPENWA_ENABLED: bool = False
    OPENWA_BASE_URL: str = ""
    OPENWA_API_KEY: str = ""
    OPENWA_WEBHOOK_SECRET: str = ""
    OPENWA_WEBHOOK_PUBLIC_URL: str = ""
    OPENWA_TIMEOUT_SECONDS: int = 20
    
    # Webhook Configuration
    WEBHOOK_PUBLIC_URL: str = "http://localhost:8000"  # Your public URL for webhooks
    WEBHOOK_USERNAME: str = ""
    WEBHOOK_PASSWORD: str = ""
    
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
    RUN_SCHEDULED_JOBS_IN_WEB: bool = False

    # Real Estate automation scheduler
    REAL_ESTATE_AUTOMATION_ENABLED: bool = True
    REAL_ESTATE_AUTOMATION_INTERVAL_SECONDS: int = 300
    REAL_ESTATE_WEEKLY_REPORT_DAY: int = 0  # Monday=0 ... Sunday=6
    REAL_ESTATE_WEEKLY_REPORT_HOUR_UTC: int = 8

    # Google Calendar OAuth (Real Estate Pack)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/real-estate/calendar/google/callback"

    # Browser/PWA push notifications (free Web Push protocol)
    WEB_PUSH_VAPID_PUBLIC_KEY: str = ""
    WEB_PUSH_VAPID_PRIVATE_KEY_B64: str = ""
    WEB_PUSH_SUBJECT: str = "mailto:support@svontai.com"

    # Payments
    BILLING_MODE: Literal["manual", "stripe"] = "manual"
    PAYMENTS_ENABLED: bool = False
    PAYMENTS_PROVIDER: Literal["stripe"] = "stripe"
    SALES_CONTACT_EMAIL: str = "sales@svontai.com"
    SALES_CONTACT_URL: str = "/contact"

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
    SERVICE_ROLE: Literal["api", "worker"] = "api"
    
    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379"
    RATE_LIMIT_BACKEND: Literal["memory", "redis"] = "memory"
    RATE_LIMIT_REDIS_PREFIX: str = "svontai:rate-limit"

    # External error tracking (Sentry free tier is sufficient for launch).
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.05

    # Encrypted PostgreSQL backups. The worker dumps over Railway's private
    # network and uploads only AES-256-GCM ciphertext to a private R2 bucket.
    DATABASE_BACKUP_ENABLED: bool = False
    DATABASE_BACKUP_INTERVAL_SECONDS: int = 86400
    DATABASE_BACKUP_RETENTION_DAYS: int = 30
    DATABASE_BACKUP_VERIFY_RESTORE: bool = True
    DATABASE_BACKUP_ENCRYPTION_KEY_B64: str = ""
    DATABASE_BACKUP_R2_ENDPOINT_URL: str = ""
    DATABASE_BACKUP_R2_ACCESS_KEY_ID: str = ""
    DATABASE_BACKUP_R2_SECRET_ACCESS_KEY: str = ""
    DATABASE_BACKUP_R2_BUCKET: str = ""
    DATABASE_BACKUP_R2_PREFIX: str = "postgres"
    
    # ===========================================
    # n8n Workflow Engine Integration
    # ===========================================
    # Feature flag: Set to True to enable n8n workflow execution
    USE_N8N: bool = False
    
    # n8n Base URL (internal network or external)
    N8N_BASE_URL: str = ""
    
    # Optional n8n API key for authenticated requests
    N8N_API_KEY: Optional[str] = None
    
    # Shared secrets for secure communication between SvontAI and n8n
    # Used for HMAC signature verification
    SVONTAI_TO_N8N_SECRET: str = "change-this-to-a-secure-random-string-svontai-to-n8n"
    N8N_TO_SVONTAI_SECRET: str = "change-this-to-a-secure-random-string-n8n-to-svontai"
    N8N_ERROR_WEBHOOK_SECRET: str = ""

    # ===========================================
    # Voice Gateway Integration (HMAC)
    # ===========================================
    VOICE_GATEWAY_TO_SVONTAI_SECRET: str = "change-this-to-a-secure-random-string-voice-gateway-to-svontai"
    VOICE_GATEWAY_PUBLIC_URL: str = ""
    VOICE_OUTBOUND_MODE: Literal["dry_run", "live"] = "dry_run"
    VOICE_OUTBOUND_PROVIDER: Literal["twilio"] = "twilio"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    
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
    # Enables verbose tool runner debug logging (URL/host/env snapshot without raw secrets)
    TOOL_RUNNER_DEBUG: bool = False

    # ===========================================
    # Artifact Storage (Tool outputs)
    # ===========================================
    ARTIFACT_STORAGE_PROVIDER: Literal["local", "railway_volume", "supabase"] = "local"
    ARTIFACT_STORAGE_LOCAL_BASE_PATH: str = "storage/artifacts"
    ARTIFACT_MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024
    ARTIFACT_SIGNED_URL_EXPIRES_SECONDS: int = 300
    ARTIFACT_SIGNING_SECRET: str = ""
    RAILWAY_VOLUME_MOUNT_PATH: str = ""

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

    @property
    def ai_api_key(self) -> str:
        """Return the credential for the selected AI provider."""
        if self.AI_PROVIDER == "gemini":
            return self.GEMINI_API_KEY.strip()
        return self.OPENAI_API_KEY.strip()

    @property
    def ai_model(self) -> str:
        """Return an explicit shared model override or the provider default."""
        if self.AI_MODEL.strip():
            return self.AI_MODEL.strip()
        if self.AI_PROVIDER == "gemini":
            return self.GEMINI_MODEL.strip()
        return self.OPENAI_MODEL.strip()

    @property
    def ai_base_url(self) -> str | None:
        if self.AI_PROVIDER == "gemini":
            return self.GEMINI_BASE_URL.strip()
        return None

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

        missing_real_time_config: list[str] = []
        if not self.ai_api_key:
            required_key = "GEMINI_API_KEY" if self.AI_PROVIDER == "gemini" else "OPENAI_API_KEY"
            missing_real_time_config.append(required_key)
        if not self.WEBHOOK_USERNAME.strip() or not self.WEBHOOK_PASSWORD.strip():
            missing_real_time_config.append("WEBHOOK_USERNAME/WEBHOOK_PASSWORD")
        if self.OPENWA_ENABLED and (
            not self.OPENWA_BASE_URL.strip()
            or not self.OPENWA_API_KEY.strip()
            or not self.OPENWA_WEBHOOK_SECRET.strip()
        ):
            missing_real_time_config.append("OPENWA_BASE_URL/OPENWA_API_KEY/OPENWA_WEBHOOK_SECRET")
        if self.OPENWA_ENABLED and (
            self.OPENWA_WEBHOOK_PUBLIC_URL.startswith("http://localhost")
            or (
                not self.OPENWA_WEBHOOK_PUBLIC_URL.strip()
                and self.WEBHOOK_PUBLIC_URL.startswith("http://localhost")
            )
        ):
            missing_real_time_config.append("public OPENWA_WEBHOOK_PUBLIC_URL")
        if not self.EMAIL_ENABLED:
            missing_real_time_config.append("EMAIL_ENABLED=true")
        if self.EMAIL_PROVIDER == "resend" and not self.RESEND_API_KEY.strip():
            missing_real_time_config.append("RESEND_API_KEY")
        if self.EMAIL_PROVIDER == "smtp" and (
            not self.SMTP_HOST.strip() or not self.SMTP_USERNAME.strip() or not self.SMTP_PASSWORD.strip()
        ):
            missing_real_time_config.append("SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD")
        if self.BILLING_MODE == "stripe":
            if not self.PAYMENTS_ENABLED:
                missing_real_time_config.append("PAYMENTS_ENABLED=true")
            if (
                not self.STRIPE_SECRET_KEY.strip()
                or not self.STRIPE_WEBHOOK_SECRET.strip()
                or not self.STRIPE_SUCCESS_URL.strip()
                or not self.STRIPE_CANCEL_URL.strip()
                or not self.STRIPE_PORTAL_RETURN_URL.strip()
                or not self.STRIPE_PRICE_IDS
            ):
                missing_real_time_config.append("Stripe live checkout/webhook/price envs")
        elif self.PAYMENTS_ENABLED:
            missing_real_time_config.append("PAYMENTS_ENABLED=false when BILLING_MODE=manual")
        if not self.USE_N8N:
            missing_real_time_config.append("USE_N8N=true")
        if not self.N8N_BASE_URL.strip() or not self.N8N_INCOMING_WORKFLOW_ID.strip():
            missing_real_time_config.append("N8N_BASE_URL/N8N_INCOMING_WORKFLOW_ID")
        if not self.N8N_ERROR_WEBHOOK_SECRET.strip():
            missing_real_time_config.append("N8N_ERROR_WEBHOOK_SECRET")
        if self.SERVICE_ROLE == "api":
            if self.ARTIFACT_STORAGE_PROVIDER == "supabase":
                if (
                    not self.SUPABASE_URL.strip()
                    or not self.SUPABASE_SERVICE_ROLE_KEY.strip()
                    or not self.SUPABASE_STORAGE_BUCKET.strip()
                    or not self.ARTIFACT_SIGNING_SECRET.strip()
                ):
                    missing_real_time_config.append("Supabase artifact storage envs")
            elif self.ARTIFACT_STORAGE_PROVIDER == "railway_volume":
                artifact_path = Path(self.ARTIFACT_STORAGE_LOCAL_BASE_PATH).expanduser()
                mount_path = Path(self.RAILWAY_VOLUME_MOUNT_PATH).expanduser() if self.RAILWAY_VOLUME_MOUNT_PATH else None
                if not artifact_path.is_absolute() or not self.ARTIFACT_SIGNING_SECRET.strip():
                    missing_real_time_config.append("absolute ARTIFACT_STORAGE_LOCAL_BASE_PATH/ARTIFACT_SIGNING_SECRET")
                if not mount_path or not mount_path.is_absolute():
                    missing_real_time_config.append("RAILWAY_VOLUME_MOUNT_PATH")
                elif artifact_path != mount_path and mount_path not in artifact_path.parents:
                    missing_real_time_config.append("artifact path must be inside RAILWAY_VOLUME_MOUNT_PATH")
            else:
                missing_real_time_config.append("ARTIFACT_STORAGE_PROVIDER=railway_volume or supabase")
        if self.RATE_LIMIT_BACKEND != "redis" or not self.REDIS_URL.strip():
            missing_real_time_config.append("RATE_LIMIT_BACKEND=redis/REDIS_URL")
        if not self.SENTRY_DSN.strip():
            missing_real_time_config.append("SENTRY_DSN")
        if self.DATABASE_BACKUP_ENABLED:
            if self.DATABASE_BACKUP_INTERVAL_SECONDS < 3600:
                missing_real_time_config.append("DATABASE_BACKUP_INTERVAL_SECONDS>=3600")
            if self.DATABASE_BACKUP_RETENTION_DAYS < 7:
                missing_real_time_config.append("DATABASE_BACKUP_RETENTION_DAYS>=7")
            if not self.DATABASE_BACKUP_R2_ENDPOINT_URL.startswith("https://"):
                missing_real_time_config.append("https DATABASE_BACKUP_R2_ENDPOINT_URL")
            if (
                not self.DATABASE_BACKUP_R2_ACCESS_KEY_ID.strip()
                or not self.DATABASE_BACKUP_R2_SECRET_ACCESS_KEY.strip()
                or not self.DATABASE_BACKUP_R2_BUCKET.strip()
            ):
                missing_real_time_config.append("R2 backup bucket credentials")
            try:
                backup_key = base64.b64decode(
                    self.DATABASE_BACKUP_ENCRYPTION_KEY_B64,
                    validate=True,
                )
            except Exception:
                backup_key = b""
            if len(backup_key) != 32:
                missing_real_time_config.append("32-byte DATABASE_BACKUP_ENCRYPTION_KEY_B64")
        if self.WEBHOOK_PUBLIC_URL.startswith("http://localhost") or self.BACKEND_URL.startswith("http://localhost"):
            missing_real_time_config.append("public WEBHOOK_PUBLIC_URL/BACKEND_URL")
        if self.FRONTEND_URL.startswith("http://localhost"):
            missing_real_time_config.append("public FRONTEND_URL")
        if self.ALLOW_DEMO_SEED:
            missing_real_time_config.append("ALLOW_DEMO_SEED=false")
        if missing_real_time_config:
            raise ValueError(
                "FATAL: Production must use real-time external services and real credentials. "
                "Missing or invalid config: " + ", ".join(missing_real_time_config)
            )
        
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
        if self.VOICE_OUTBOUND_MODE == "live" and (
            not self.VOICE_GATEWAY_PUBLIC_URL.strip()
            or not self.TWILIO_ACCOUNT_SID.strip()
            or not self.TWILIO_AUTH_TOKEN.strip()
        ):
            raise ValueError(
                "FATAL: VOICE_OUTBOUND_MODE=live requires VOICE_GATEWAY_PUBLIC_URL, "
                "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
            )
        
        return self


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
