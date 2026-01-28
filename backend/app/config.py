import os
import logging
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Union

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database
    DB_HOST: str
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str = "ssmaker_auth"

    # Cloud SQL Unix Socket (for Cloud Run deployment)
    # Format: /cloudsql/PROJECT:REGION:INSTANCE
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
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters. Generate with: openssl rand -hex 32")
        return v

    # Security
    BCRYPT_ROUNDS: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    MAX_IP_ATTEMPTS: int = 20  # Higher threshold for IP-based limiting
    LOGIN_ATTEMPT_WINDOW_MINUTES: int = 15

    # Environment
    ENVIRONMENT: str = "development"

    # CORS - MUST be explicitly configured in production
    # Use comma-separated list: "https://app.example.com,https://admin.example.com"
    ALLOWED_ORIGINS: Union[str, list[str]] = "http://localhost:3000"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse ALLOWED_ORIGINS from string or list - blocks wildcard in production"""
        if isinstance(v, str):
            # Block wildcard in production
            if v == "*":
                env = os.getenv("ENVIRONMENT", "development")
                if env == "production":
                    raise ValueError(
                        "ALLOWED_ORIGINS cannot be '*' in production. "
                        "Specify explicit origins: 'https://app.example.com,https://admin.example.com'"
                    )
                logger.warning("CORS wildcard '*' is insecure. Configure explicit origins for production.")
                return [v]
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
