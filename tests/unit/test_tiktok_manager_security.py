from managers.tiktok_manager import TikTokManager


def test_tiktok_token_encrypt_decrypt_roundtrip():
    token = "test-access-token-12345"
    encrypted = TikTokManager._encrypt_secret(token)

    assert encrypted
    assert encrypted != token
    assert encrypted.startswith("fernet:")
    assert TikTokManager._decrypt_secret(encrypted) == token


def test_tiktok_token_decrypt_accepts_legacy_plaintext():
    token = "legacy-plain-token"
    assert TikTokManager._decrypt_secret(token) == token
