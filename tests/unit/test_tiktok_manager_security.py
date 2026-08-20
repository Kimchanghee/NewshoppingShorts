import json
from pathlib import Path

import pytest

from managers.tiktok_manager import TikTokCredentials, TikTokManager


class _TestTikTokManager(TikTokManager):
    def __init__(self, user_dir: Path):
        self._test_dir = user_dir
        super().__init__(gui=None, settings_file="tiktok_security_test.json")

    def _get_settings_path(self) -> str:
        return str(self._test_dir / self.settings_file)


class _MemoryCredentialStore:
    def __init__(self):
        self.values = {}
        self.fail_writes = False

    def set_credential(self, key, value):
        if self.fail_writes:
            return False
        self.values[key] = value
        return True

    def get_credential(self, key):
        return self.values.get(key)

    def delete_credential(self, key):
        self.values.pop(key, None)
        return True


@pytest.fixture
def secure_store(monkeypatch):
    store = _MemoryCredentialStore()
    monkeypatch.setattr(
        "utils.secrets_manager.get_secrets_manager",
        lambda: store,
    )
    return store


def test_tiktok_tokens_round_trip_through_os_store_not_json(tmp_path, secure_store):
    manager = _TestTikTokManager(tmp_path)
    manager._credentials = TikTokCredentials(
        access_token="access-token",
        refresh_token="refresh-token",
        open_id="open-1",
        expires_at=123.0,
        scope="video.publish",
    )

    assert manager._save_settings() is True
    raw = json.loads((tmp_path / "tiktok_security_test.json").read_text(encoding="utf-8"))
    assert "access_token" not in raw["credentials"]
    assert "refresh_token" not in raw["credentials"]
    assert secure_store.values[TikTokManager.ACCESS_TOKEN_KEY] == "access-token"
    assert secure_store.values[TikTokManager.REFRESH_TOKEN_KEY] == "refresh-token"

    reloaded = _TestTikTokManager(tmp_path)
    assert reloaded._credentials.access_token == "access-token"
    assert reloaded._credentials.refresh_token == "refresh-token"


def test_tiktok_refuses_json_write_when_os_store_fails(tmp_path, secure_store):
    manager = _TestTikTokManager(tmp_path)
    manager._credentials = TikTokCredentials(
        access_token="must-not-be-written",
        refresh_token="must-not-be-written-either",
    )
    secure_store.fail_writes = True

    assert manager._save_settings() is False
    assert not (tmp_path / "tiktok_security_test.json").exists()


def test_tiktok_legacy_plaintext_migrates_and_is_scrubbed(tmp_path, secure_store):
    settings_path = tmp_path / "tiktok_security_test.json"
    settings_path.write_text(
        json.dumps({
            "credentials": {
                "access_token": "legacy-access",
                "refresh_token": "legacy-refresh",
                "open_id": "open-1",
                "expires_at": 456.0,
                "scope": "video.publish",
            },
        }),
        encoding="utf-8",
    )

    manager = _TestTikTokManager(tmp_path)

    assert manager._credentials.access_token == "legacy-access"
    assert manager._credentials.refresh_token == "legacy-refresh"
    scrubbed = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "access_token" not in scrubbed["credentials"]
    assert "refresh_token" not in scrubbed["credentials"]
    assert secure_store.values[TikTokManager.ACCESS_TOKEN_KEY] == "legacy-access"
    assert secure_store.values[TikTokManager.REFRESH_TOKEN_KEY] == "legacy-refresh"


def test_tiktok_token_decrypt_accepts_legacy_plaintext():
    token = "legacy-plain-token"
    assert TikTokManager._decrypt_secret(token) == token
