from types import SimpleNamespace

import config
from app.batch_handler import BatchHandler


def test_has_valid_api_key_returns_true_when_secrets_manager_has_key(monkeypatch):
    app = SimpleNamespace(api_key_manager=SimpleNamespace(api_keys={}))
    handler = BatchHandler(app)

    monkeypatch.setattr(config, "GEMINI_API_KEYS", {})

    def _fake_get_api_key(name: str):
        if name == "gemini_api_3":
            return "AIzaFakeKeyFromSecretsManager1234567890123456789012"
        return ""

    monkeypatch.setattr("app.batch_handler.SecretsManager.get_api_key", _fake_get_api_key)

    assert handler._has_valid_api_key() is True


def test_has_valid_api_key_returns_false_when_all_sources_empty(monkeypatch):
    app = SimpleNamespace(api_key_manager=SimpleNamespace(api_keys={}))
    handler = BatchHandler(app)

    monkeypatch.setattr(config, "GEMINI_API_KEYS", {})
    monkeypatch.setattr("app.batch_handler.SecretsManager.get_api_key", lambda _name: "")

    assert handler._has_valid_api_key() is False
