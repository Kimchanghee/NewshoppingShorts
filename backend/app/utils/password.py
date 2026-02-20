import bcrypt
from app.configuration import get_settings


def hash_password(password: str) -> str:
    """Hash password using bcrypt with configured rounds"""
    _settings = get_settings()
    salt = bcrypt.gensalt(rounds=_settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


# Pre-computed dummy hash for timing attack prevention
# This is a bcrypt hash of a random string, used when user doesn't exist
_DUMMY_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G6tHnCvWNeQvKy"


def get_dummy_hash() -> str:
    """Return a dummy bcrypt hash for timing attack prevention.

    When a user doesn't exist, we still need to perform bcrypt verification
    to prevent timing attacks that could reveal whether a username exists.
    """
    return _DUMMY_HASH
