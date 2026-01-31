import os
import logging
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Union

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database
    DB_HOST: str = "127.0.0.1"  # Default for local, ignored when using Cloud SQL socket
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
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

    # API Key for client authentication
    SSMAKER_API_KEY: str = ""

    # Admin API Key for protected endpoints
    # Generate with: openssl rand -hex 32
    ADMIN_API_KEY: str = ""

    @field_validator("ADMIN_API_KEY")
    @classmethod
    def validate_admin_api_key(cls, v, info):
        """Admin API key validation - required in production"""
        # Get environment from values if available
        env = (
            info.data.get("ENVIRONMENT", "development") if info.data else "development"
        )
        if env == "production" and (not v or len(v) < 32):
            raise ValueError(
                "ADMIN_API_KEY must be at least 32 characters in production"
            )
        return v

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

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
