from types import SimpleNamespace

import config
from app.batch_handler import BatchHandler


class DummyButton:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)


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


def test_start_batch_processing_runs_summer_coupang_queue_when_url_queue_empty(monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def is_alive(self):
            return False

        def start(self):
            started.append(self.target)

    logs = []
    app = SimpleNamespace(
        url_queue=[],
        batch_thread=None,
        batch_processing=False,
        dynamic_processing=False,
        start_batch_button=DummyButton(),
        stop_batch_button=DummyButton(),
        add_log=logs.append,
    )
    handler = BatchHandler(app)

    monkeypatch.setattr(
        "app.batch_handler.build_summer_coupang_queue_snapshot",
        lambda: {"counts": {"waiting": 3}},
    )
    monkeypatch.setattr("app.batch_handler.threading.Thread", FakeThread)
    monkeypatch.setattr(handler, "_reset_start_button_style", lambda _btn: None)

    handler.start_batch_processing()

    assert started == [handler._summer_coupang_queue_now_wrapper]
    assert app.batch_thread is not None
    assert app.batch_processing is True
    assert app.start_batch_button.enabled is False
    assert any("예약 큐 3건" in line for line in logs)


def test_summer_coupang_manual_reset_prefers_ui_callback_signal(monkeypatch):
    emitted = []
    called = []

    class DummySignal:
        def emit(self, callback):
            emitted.append(callback)

    app = SimpleNamespace(ui_callback_signal=DummySignal())
    handler = BatchHandler(app)
    monkeypatch.setattr(
        "app.batch_handler.QTimer.singleShot",
        lambda _ms, _cb: called.append("qtimer"),
    )

    callback = object()
    handler._dispatch_ui_callback(callback)

    assert emitted == [callback]
    assert called == []
