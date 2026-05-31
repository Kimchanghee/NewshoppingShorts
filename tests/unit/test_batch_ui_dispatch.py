from types import SimpleNamespace

from core.video.batch.processor import _dispatch_ui_callback


class DummySignal:
    def __init__(self):
        self.emitted = []

    def emit(self, callback):
        self.emitted.append(callback)


def test_dispatch_ui_callback_prefers_ui_signal():
    signal = DummySignal()
    app = SimpleNamespace(ui_callback_signal=signal)
    called = []

    def callback():
        called.append("ran")

    _dispatch_ui_callback(app, callback)

    assert signal.emitted == [callback]
    assert called == []


def test_dispatch_ui_callback_falls_back_to_qtimer(monkeypatch):
    app = SimpleNamespace()
    called = []

    monkeypatch.setattr(
        "core.video.batch.processor.QTimer.singleShot",
        lambda _ms, cb: cb(),
    )

    _dispatch_ui_callback(app, lambda: called.append("ran"))

    assert called == ["ran"]
