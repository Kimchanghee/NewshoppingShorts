import json

from managers.settings_manager import SettingsManager


class MemoryCredentialStore:
    def __init__(self, *, reject_writes=False):
        self.values = {}
        self.reject_writes = reject_writes

    def set_credential(self, key, value):
        if self.reject_writes:
            return False
        self.values[key] = value
        return True

    def get_credential(self, key):
        return self.values.get(key)

    def delete_credential(self, key):
        self.values.pop(key, None)
        return True


def _manager(monkeypatch, tmp_path, store, initial=None):
    settings_dir = tmp_path / "settings"
    settings_path = settings_dir / "prefs.json"
    if initial is not None:
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(initial, ensure_ascii=False),
            encoding="utf-8",
        )
    monkeypatch.setattr(
        SettingsManager,
        "_get_settings_dir",
        lambda self: str(settings_dir),
    )
    monkeypatch.setattr(
        SettingsManager,
        "_get_legacy_settings_paths",
        lambda self: [],
    )
    monkeypatch.setattr(
        "managers.settings_manager.get_secrets_manager",
        lambda: store,
    )
    return SettingsManager("prefs.json"), settings_path


def test_sensitive_settings_use_credential_store_and_leave_json_value_free(
    monkeypatch,
    tmp_path,
):
    store = MemoryCredentialStore()
    manager, settings_path = _manager(monkeypatch, tmp_path, store)

    assert manager.set_coupang_keys("access-value", "secret-value") is True
    assert manager.set_linktree_settings(
        "https://example.com/hook",
        "linktree-token",
        profile_url="https://linktr.ee/example",
        auto_publish=True,
    ) is True
    assert manager.set_computer_use_settings(bridge_api_key="bridge-token") is True
    assert manager.set_inpock_cookies({"session": "inpock-cookie"}) is True
    assert manager.set_1688_cookies({"session": "1688-cookie"}) is True

    persisted = json.loads(settings_path.read_text(encoding="utf-8"))
    for key in SettingsManager.SECURE_CREDENTIAL_KEYS:
        assert persisted[key] in ("", {})

    assert manager.get_coupang_keys() == {
        "access_key": "access-value",
        "secret_key": "secret-value",
    }
    assert manager.get_linktree_settings()["api_key"] == "linktree-token"
    assert manager.get_computer_use_settings()["bridge_api_key"] == "bridge-token"
    assert manager.get_inpock_cookies() == {"session": "inpock-cookie"}
    assert manager.get_1688_cookies() == {"session": "1688-cookie"}

    serialized = settings_path.read_text(encoding="utf-8")
    for secret in (
        "access-value",
        "secret-value",
        "linktree-token",
        "bridge-token",
        "inpock-cookie",
        "1688-cookie",
    ):
        assert secret not in serialized


def test_credential_store_failure_is_fail_closed(monkeypatch, tmp_path):
    manager, settings_path = _manager(
        monkeypatch,
        tmp_path,
        MemoryCredentialStore(reject_writes=True),
    )

    assert manager.set_coupang_keys("access-value", "secret-value") is False
    assert manager.get_coupang_keys() == {"access_key": "", "secret_key": ""}
    assert any(
        issue["code"] == "ST-S003"
        and issue["component"] == "settings.secure_storage"
        for issue in manager.get_recovery_issues()
    )
    if settings_path.exists():
        serialized = settings_path.read_text(encoding="utf-8")
        assert "access-value" not in serialized
        assert "secret-value" not in serialized


def test_startup_migrates_plaintext_secrets_then_scrubs_preferences(
    monkeypatch,
    tmp_path,
):
    store = MemoryCredentialStore()
    manager, settings_path = _manager(
        monkeypatch,
        tmp_path,
        store,
        {
            "coupang_access_key": "legacy-access",
            "coupang_secret_key": "legacy-secret",
            "cookies_1688": {"session": "legacy-cookie"},
        },
    )

    assert manager.get_coupang_keys() == {
        "access_key": "legacy-access",
        "secret_key": "legacy-secret",
    }
    assert manager.get_1688_cookies() == {"session": "legacy-cookie"}
    serialized = settings_path.read_text(encoding="utf-8")
    assert "legacy-access" not in serialized
    assert "legacy-secret" not in serialized
    assert "legacy-cookie" not in serialized


def test_bulk_update_cannot_bypass_secure_storage(monkeypatch, tmp_path):
    manager, _ = _manager(monkeypatch, tmp_path, MemoryCredentialStore())

    assert manager.update_settings({"linktree_api_key": "plaintext"}) is False
    assert manager.get_all_settings()["linktree_api_key"] == ""
