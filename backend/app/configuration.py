import logging
import os
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from functools import lru_cache
from typing import Union
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # Database
    # Preferred for serverless platforms (for example, a managed MySQL URL).
    # When omitted, the legacy Cloud SQL socket/TCP configuration is used.
    DATABASE_URL: str = ""
    DB_HOST: str = "127.0.0.1"  # Default for local, ignored when using Cloud SQL socket
    DB_PORT: int = 3306
    # A managed PostgreSQL URL (for example, Supabase) does not need the
    # legacy MySQL credential fields.
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: str = "ssmaker_auth"

    # Cloud SQL Unix Socket (for Cloud Run deployment)
    # Format: PROJECT:REGION:INSTANCE (without /cloudsql/ prefix)
    CLOUD_SQL_CONNECTION_NAME: str = ""

    # JWT
    JWT_SECRET_KEY: str  # Generate with: openssl rand -hex 32
    JWT_ALGORITHM: str = "HS256"
    # Security: Reduced from 72h to 24h to limit exposure window if token is compromised
    # For longer sessions, consider implementing refresh tokens
    # 보안: 토큰 탈취 시 노출 기간을 줄이기 위해 72시간에서 24시간으로 단축
    JWT_EXPIRATION_HOURS: int = 24

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v):
        """JWT secret must be at least 32 characters for security"""
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters. Generate with: openssl rand -hex 32"
            )
        return v

    # Security
    BCRYPT_ROUNDS: int = 12
    MAX_LOGIN_ATTEMPTS: int = 3
    MAX_IP_ATTEMPTS: int = 10  # Higher threshold for IP-based limiting
    LOGIN_ATTEMPT_WINDOW_MINUTES: int = 15
    # Session considered stale when heartbeat is older than this threshold.
    # Helps recover from client crashes where logout is never sent.
    # Prefer seconds for tighter duplicate-login recovery; keep minutes for
    # backward compatibility with older deployments.
    SESSION_STALE_SECONDS: int = 30
    SESSION_STALE_MINUTES: int = 2
    ENFORCE_SESSION_IP_BINDING: bool = False
    SESSION_RETENTION_DAYS: int = 7
    LOGIN_ATTEMPT_RETENTION_DAYS: int = 30
    MAINTENANCE_TASK_INTERVAL_MINUTES: int = 60

    # API Key for client authentication
    SSMAKER_API_KEY: str = ""

    # Admin API Key for protected endpoints
    # Generate with: openssl rand -hex 32
    ADMIN_API_KEY: str = ""
    ADMIN_PASSWORD_HASH: str = ""
    ADMIN_SESSION_PEPPER: str = ""
    ADMIN_SESSION_TTL_HOURS: int = 8

    @field_validator("ADMIN_API_KEY")
    @classmethod
    def validate_admin_api_key(cls, v):
        """Normalize API key value."""
        return v

    @field_validator("ADMIN_SESSION_TTL_HOURS")
    @classmethod
    def validate_admin_session_ttl(cls, v):
        value = int(v or 0)
        if value < 1 or value > 24:
            raise ValueError("ADMIN_SESSION_TTL_HOURS must be between 1 and 24")
        return value

    # Dedicated key for CI/CD app-version metadata updates.
    # Keep separate from ADMIN_API_KEY to reduce blast radius if leaked.
    APP_VERSION_UPDATE_API_KEY: str = ""

    @field_validator("APP_VERSION_UPDATE_API_KEY")
    @classmethod
    def validate_update_api_key(cls, v):
        """Normalize update API key value."""
        return v

    # Optional HMAC key for update metadata payload signing.
    # If set, /app/version/update requires a matching X-Update-Signature header.
    APP_VERSION_UPDATE_HMAC_KEY: str = ""

    # Required bridge key for centralized Computer Use job intake. If it is
    # empty, the bridge endpoint fails closed even for authenticated users.
    COMPUTER_USE_BRIDGE_API_KEY: str = ""

    @field_validator("COMPUTER_USE_BRIDGE_API_KEY")
    @classmethod
    def validate_computer_use_bridge_api_key(cls, v):
        """Normalize bridge API key value."""
        return v

    # Centralized Computer Use worker settings
    COMPUTER_USE_WORKER_ENABLED: bool = False
    COMPUTER_USE_WORKER_POLL_SECONDS: int = 3
    COMPUTER_USE_WORKER_TIMEOUT_SECONDS: int = 900
    COMPUTER_USE_WORKER_OUTPUT_LIMIT_CHARS: int = 4000
    COMPUTER_USE_WORKER_CLI_PATH: str = "codex"
    COMPUTER_USE_WORKER_MODEL: str = ""
    COMPUTER_USE_WORKER_WORKDIR: str = ""
    COMPUTER_USE_WORKER_SANDBOX: str = "read-only"
    COMPUTER_USE_ALLOW_FREEFORM_PROMPTS: bool = False
    COMPUTER_USE_PROMPT_TEMPLATES_JSON: str = "{}"

    @field_validator(
        "COMPUTER_USE_WORKER_POLL_SECONDS",
        "COMPUTER_USE_WORKER_TIMEOUT_SECONDS",
        "COMPUTER_USE_WORKER_OUTPUT_LIMIT_CHARS",
    )
    @classmethod
    def validate_computer_use_worker_positive_ints(cls, v):
        value = int(v or 0)
        if value <= 0:
            raise ValueError("Computer Use worker numeric settings must be > 0")
        return value

    @field_validator("COMPUTER_USE_WORKER_SANDBOX")
    @classmethod
    def validate_computer_use_sandbox(cls, v):
        value = str(v or "").strip()
        if value not in {"read-only", "workspace-write"}:
            raise ValueError("COMPUTER_USE_WORKER_SANDBOX must be read-only or workspace-write")
        return value

    # Billing key encryption (Fernet key)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    BILLING_KEY_ENCRYPTION_KEY: str = ""

    @field_validator("BILLING_KEY_ENCRYPTION_KEY")
    @classmethod
    def validate_billing_key_encryption_key(cls, v):
        """Validate Fernet key format when provided."""
        key = (v or "").strip()
        if not key:
            return ""
        try:
            Fernet(key.encode("utf-8"))
        except Exception as exc:
            raise ValueError("BILLING_KEY_ENCRYPTION_KEY must be a valid Fernet key") from exc
        return key

    # Environment
    ENVIRONMENT: str = "development"

    # CORS - MUST be explicitly configured in production
    # Use comma-separated list: "https://app.example.com,https://admin.example.com"
    ALLOWED_ORIGINS: Union[str, list[str]] = "http://localhost:3000"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse ALLOWED_ORIGINS from string or list"""
        if isinstance(v, str):
            # Allow wildcard (desktop app needs this)
            if v == "*":
                logger.warning(
                    "CORS wildcard '*' enabled. Consider restricting for web apps."
                )
                return ["*"]
            # Single URL
            if v.startswith("http"):
                return [v]
            # Comma-separated list
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_requirements(self):
        database_url = (self.DATABASE_URL or os.getenv("POSTGRES_URL", "")).strip()
        if not database_url:
            if not (self.DB_USER or "").strip() or not (self.DB_PASSWORD or "").strip():
                raise ValueError(
                    "Set DATABASE_URL, or set both DB_USER and DB_PASSWORD for legacy MySQL"
                )

        if self.COMPUTER_USE_WORKER_ENABLED:
            if len((self.COMPUTER_USE_BRIDGE_API_KEY or "").strip()) < 32:
                raise ValueError("Computer Use worker requires a 32+ character bridge API key")
            workdir = (self.COMPUTER_USE_WORKER_WORKDIR or "").strip()
            if not workdir or not os.path.isabs(workdir):
                raise ValueError("Computer Use worker requires an absolute work directory")
            try:
                templates = json.loads(self.COMPUTER_USE_PROMPT_TEMPLATES_JSON or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError("COMPUTER_USE_PROMPT_TEMPLATES_JSON must be valid JSON") from exc
            if not isinstance(templates, dict):
                raise ValueError("Computer Use prompt templates must be a JSON object")
            if not self.COMPUTER_USE_ALLOW_FREEFORM_PROMPTS and not templates:
                raise ValueError("Computer Use requires server templates or explicit freeform opt-in")

        env = (self.ENVIRONMENT or "development").lower().strip()
        if env != "production":
            return self

        admin_key = (self.ADMIN_API_KEY or "").strip()
        if len(admin_key) < 32:
            raise ValueError("ADMIN_API_KEY must be at least 32 characters in production")

        if not (self.ADMIN_PASSWORD_HASH or "").startswith(("$2a$", "$2b$", "$2y$")):
            raise ValueError("ADMIN_PASSWORD_HASH must be a bcrypt hash in production")
        if len((self.ADMIN_SESSION_PEPPER or "").strip()) < 32:
            raise ValueError("ADMIN_SESSION_PEPPER must be at least 32 characters in production")

        update_key = (self.APP_VERSION_UPDATE_API_KEY or "").strip()
        if len(update_key) < 32:
            raise ValueError(
                "APP_VERSION_UPDATE_API_KEY must be at least 32 characters in production"
            )

        if not (self.BILLING_KEY_ENCRYPTION_KEY or "").strip():
            raise ValueError("BILLING_KEY_ENCRYPTION_KEY is required in production")

        return self

@lru_cache()
def get_settings() -> Settings:
    return Settings()
