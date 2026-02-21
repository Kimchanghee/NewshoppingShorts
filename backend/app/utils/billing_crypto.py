"""
Billing key crypto helpers.

Encrypts/decrypts billing keys (encBill) before storing them in DB.
"""

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.configuration import get_settings

logger = logging.getLogger(__name__)

_VERSION_PREFIX = "v1:"
_FERNET: Optional[Fernet] = None
_FERNET_INITIALIZED = False


def _get_fernet() -> Optional[Fernet]:
    global _FERNET, _FERNET_INITIALIZED
    if _FERNET_INITIALIZED:
        return _FERNET

    settings = get_settings()
    key = (settings.BILLING_KEY_ENCRYPTION_KEY or "").strip()
    if not key:
        _FERNET = None
        _FERNET_INITIALIZED = True
        return None

    try:
        _FERNET = Fernet(key.encode("utf-8"))
    except Exception as e:
        logger.error("[BillingCrypto] Invalid BILLING_KEY_ENCRYPTION_KEY format", exc_info=True)
        raise RuntimeError("Invalid BILLING_KEY_ENCRYPTION_KEY format") from e

    _FERNET_INITIALIZED = True
    return _FERNET


def is_encrypted(value: str) -> bool:
    return isinstance(value, str) and value.startswith(_VERSION_PREFIX)


def has_encryption_key() -> bool:
    return _get_fernet() is not None


def validate_billing_crypto_startup(require_key: bool = False) -> None:
    """
    Validate billing crypto configuration during server startup.

    Raises RuntimeError when Fernet key format is invalid or missing while required.
    """
    fernet = _get_fernet()
    if require_key and fernet is None:
        raise RuntimeError("BILLING_KEY_ENCRYPTION_KEY is required")


def encrypt_billing_key(value: str) -> str:
    """
    Encrypt billing key for DB storage.

    Raises RuntimeError when encryption key is not configured.
    """
    if not value:
        return value
    if is_encrypted(value):
        return value

    fernet = _get_fernet()
    if not fernet:
        raise RuntimeError("Billing key encryption is not configured")

    token = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_VERSION_PREFIX}{token}"


def decrypt_billing_key(value: str) -> str:
    """
    Decrypt billing key from DB.

    - New records: "v1:<fernet_token>" -> decrypted.
    - Legacy records: plain text -> returned as-is for backward compatibility.
    """
    if not value:
        return value
    if not is_encrypted(value):
        return value

    fernet = _get_fernet()
    if not fernet:
        raise RuntimeError("Billing key encryption is not configured")

    token = value[len(_VERSION_PREFIX):]
    try:
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError("Stored billing key decryption failed") from e
