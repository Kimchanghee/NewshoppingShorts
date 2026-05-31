from types import SimpleNamespace

import config

from app.api_handler import APIHandler


def _valid_key(char: str) -> str:
    return "AIza" + (char * 35)


class _FakeApiKeyManager:
    MAX_KEYS = 8

    def __init__(self, use_secrets_manager=True):
        self.use_secrets_manager = use_secrets_manager
        self.api_keys = {}


def test_save_api_keys_from_ui_deletes_stale_slots(monkeypatch):
    app = SimpleNamespace(
        api_key_entries=[_valid_key("A"), _valid_key("B")],
        api_key_manager=None,
    )
    handler = APIHandler(app)

    monkeypatch.setattr(config, "GEMINI_API_KEYS", {"api_1": "legacy"}, raising=False)
    monkeypatch.setattr("app.api_handler.ApiKeyManager.APIKeyManager", _FakeApiKeyManager)

    stored = []
    deleted = []

    monkeypatch.setattr(
        "app.api_handler.SecretsManager.store_api_key",
        lambda name, value: stored.append((name, value)) or True,
    )
    monkeypatch.setattr(
        "app.api_handler.SecretsManager.delete_api_key",
        lambda name: deleted.append(name) or True,
    )

    success_calls = []
    monkeypatch.setattr("app.api_handler.show_success", lambda *_args: success_calls.append(True))
    monkeypatch.setattr("app.api_handler.show_warning", lambda *_args: None)
    monkeypatch.setattr("app.api_handler.show_error", lambda *_args: None)

    handler.save_api_keys_from_ui()

    assert [name for name, _ in stored] == ["gemini_api_1", "gemini_api_2"]
    expected_deleted = {f"gemini_api_{idx}" for idx in range(3, _FakeApiKeyManager.MAX_KEYS + 1)}
    expected_deleted.add("gemini")
    assert expected_deleted.issubset(set(deleted))
    assert config.GEMINI_API_KEYS == {
        "api_1": _valid_key("A"),
        "api_2": _valid_key("B"),
    }
    assert isinstance(app.api_key_manager, _FakeApiKeyManager)
    assert success_calls


def test_clear_all_api_keys_deletes_secure_storage_and_resets_state(monkeypatch):
    app = SimpleNamespace(
        api_key_entries=[_valid_key("C")],
        api_key_manager=object(),
    )
    handler = APIHandler(app)

    monkeypatch.setattr(config, "GEMINI_API_KEYS", {"api_1": _valid_key("C")}, raising=False)
    monkeypatch.setattr("app.api_handler.ApiKeyManager.APIKeyManager", _FakeApiKeyManager)
    monkeypatch.setattr("app.api_handler.show_question", lambda *_args: True)

    deleted = []
    monkeypatch.setattr(
        "app.api_handler.SecretsManager.delete_api_key",
        lambda name: deleted.append(name) or True,
    )

    info_calls = []
    monkeypatch.setattr("app.api_handler.show_info", lambda *_args: info_calls.append(True))

    handler.clear_all_api_keys()

    expected_deleted = {f"gemini_api_{idx}" for idx in range(1, _FakeApiKeyManager.MAX_KEYS + 1)}
    expected_deleted.add("gemini")
    assert expected_deleted.issubset(set(deleted))
    assert config.GEMINI_API_KEYS == {}
    assert app.api_key_entries == []
    assert isinstance(app.api_key_manager, _FakeApiKeyManager)
    assert info_calls
