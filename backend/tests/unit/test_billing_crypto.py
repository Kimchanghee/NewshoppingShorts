import importlib

import pytest

from app.configuration import get_settings


def _set_required_env(monkeypatch):
    monkeypatch.setenv("DB_USER", "test")
    monkeypatch.setenv("DB_PASSWORD", "test")
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("JWT_SECRET_KEY", "a" * 64)
    monkeypatch.setenv("ADMIN_API_KEY", "b" * 64)
    monkeypatch.setenv("ENVIRONMENT", "development")


def _reload_crypto_module():
    import app.utils.billing_crypto as billing_crypto

    return importlib.reload(billing_crypto)


def test_encrypt_decrypt_roundtrip(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("BILLING_KEY_ENCRYPTION_KEY", "uKVciQZlzUKtZPwuiKHl3wVCJJhQrWL6TqrFRClcEOI=")
    get_settings.cache_clear()
    billing_crypto = _reload_crypto_module()

    plain = "encBill_token_123"
    encrypted = billing_crypto.encrypt_billing_key(plain)

    assert encrypted != plain
    assert billing_crypto.is_encrypted(encrypted) is True
    assert billing_crypto.decrypt_billing_key(encrypted) == plain


def test_legacy_plaintext_is_supported_without_key(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("BILLING_KEY_ENCRYPTION_KEY", raising=False)
    get_settings.cache_clear()
    billing_crypto = _reload_crypto_module()

    legacy = "legacy_plain_encbill"
    assert billing_crypto.is_encrypted(legacy) is False
    assert billing_crypto.decrypt_billing_key(legacy) == legacy


def test_encrypt_requires_key(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("BILLING_KEY_ENCRYPTION_KEY", raising=False)
    get_settings.cache_clear()
    billing_crypto = _reload_crypto_module()

    with pytest.raises(RuntimeError):
        billing_crypto.encrypt_billing_key("encBill_token_123")


def test_validate_startup_requires_key(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("BILLING_KEY_ENCRYPTION_KEY", raising=False)
    get_settings.cache_clear()
    billing_crypto = _reload_crypto_module()

    with pytest.raises(RuntimeError):
        billing_crypto.validate_billing_crypto_startup(require_key=True)


def test_billing_key_model_uses_hash_for_uniqueness():
    from app.models.billing import BillingKey

    constraints = {
        tuple(constraint.columns.keys())
        for constraint in BillingKey.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("user_id", "enc_bill_hash") in constraints
    assert "enc_bill_hash" in BillingKey.__table__.columns


def test_enc_bill_hash_is_stable_and_not_plaintext():
    from app.routers.payment import _calc_enc_bill_hash

    raw = "encBill_token_123"
    digest = _calc_enc_bill_hash(raw)

    assert digest == _calc_enc_bill_hash(raw)
    assert digest != raw
    assert len(digest) == 64
