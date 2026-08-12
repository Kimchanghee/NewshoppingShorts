from types import SimpleNamespace

from app.batch_handler import BatchHandler
from ui.panels.sourcing_panel import SourcingPanel


class _Label:
    def __init__(self):
        self.text = ""
        self.style = ""

    def setText(self, value):
        self.text = value

    def setStyleSheet(self, value):
        self.style = value


def test_legacy_sourcing_path_stops_before_network_in_offline_mode():
    panel = SimpleNamespace(
        gui=SimpleNamespace(offline_mode=True),
        results_label=_Label(),
    )
    panel._current_sourcing_method = lambda: (_ for _ in ()).throw(
        AssertionError("sourcing path must not continue")
    )

    SourcingPanel._on_start_clicked(panel)

    assert "오프라인 설정 모드" in panel.results_label.text


def test_batch_path_stops_before_queue_or_auth_checks_in_offline_mode(monkeypatch):
    shown = []
    app = SimpleNamespace(offline_mode=True)
    handler = BatchHandler(app)
    monkeypatch.setattr(
        "app.batch_handler.show_warning",
        lambda _parent, title, message: shown.append((title, message)),
    )

    handler.start_batch_processing()

    assert shown
    assert "오프라인 설정 모드" in shown[0][0]
