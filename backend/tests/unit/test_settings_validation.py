import pytest
from pydantic import ValidationError

from app.configuration import Settings


def _required_base_env() -> dict:
    return {
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "DB_HOST": "127.0.0.1",
        "DB_NAME": "test_db",
        "JWT_SECRET_KEY": "a" * 64,
    }


def test_production_requires_security_keys():
    kwargs = _required_base_env()
    kwargs.update(
        {
            "ENVIRONMENT": "production",
            "ADMIN_API_KEY": "",
            "APP_VERSION_UPDATE_API_KEY": "",
            "BILLING_KEY_ENCRYPTION_KEY": "",
        }
    )

    with pytest.raises(ValidationError):
        Settings(**kwargs)


def test_billing_key_must_be_valid_fernet():
    kwargs = _required_base_env()
    kwargs.update(
        {
            "ENVIRONMENT": "development",
            "ADMIN_API_KEY": "b" * 64,
            "APP_VERSION_UPDATE_API_KEY": "c" * 64,
            "BILLING_KEY_ENCRYPTION_KEY": "not-a-valid-fernet-key",
        }
    )

    with pytest.raises(ValidationError):
        Settings(**kwargs)


def test_production_accepts_valid_configuration():
    kwargs = _required_base_env()
    kwargs.update(
        {
            "ENVIRONMENT": "production",
            "ADMIN_API_KEY": "b" * 64,
            "APP_VERSION_UPDATE_API_KEY": "c" * 64,
            "BILLING_KEY_ENCRYPTION_KEY": "uKVciQZlzUKtZPwuiKHl3wVCJJhQrWL6TqrFRClcEOI=",
        }
    )

    settings = Settings(**kwargs)
    assert settings.ENVIRONMENT == "production"
