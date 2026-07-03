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


def test_summer_run_status_describes_rejected_gemini_keys_without_secret_values():
    handler = BatchHandler(SimpleNamespace())

    title, detail, level = handler._summer_run_result_status(
        {
            "reason": "gemini_api_keys_rejected",
            "blocking_reason": "All configured Gemini API keys were rejected.",
            "invalid_aliases": ["api_1"],
            "missing_aliases": ["api_2", "api_3"],
            "popup_launched": True,
        },
        elapsed_seconds=1.4,
        returncode=1,
    )

    assert title == "Gemini API 키를 사용할 수 없어요"
    assert level == "error"
    assert "새 API 키를 발급해 교체" in detail
    assert "안내 창을 열어 두었어요" in detail
    assert "api_1" not in detail
    assert "api_2" not in detail
    assert "AIza" not in detail


def test_summer_run_status_uses_short_youtube_oauth_message():
    handler = BatchHandler(SimpleNamespace())

    title, detail, level = handler._summer_run_result_status(
        {
            "reason": "youtube_not_connected",
            "pending_count": 59,
            "blocking_reason": (
                "YouTube OAuth token is missing or invalid. Reconnect the YouTube "
                "channel before consuming pending queue items."
            ),
        },
        elapsed_seconds=17,
        returncode=1,
    )

    assert title == "YouTube 업로드 권한 만료"
    assert detail == "설정에서 YouTube를 다시 연결해 주세요. 대기 59건."
    assert level == "error"
    assert "OAuth" not in detail
    assert "pending queue" not in detail
    assert "종료코드" not in detail
    assert "소요" not in detail
