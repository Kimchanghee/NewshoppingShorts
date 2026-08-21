import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit  # noqa: E402

from ui.panels.settings_tab import SettingsTab  # noqa: E402


QT_APP = QApplication.instance() or QApplication([])


class _FakeSettingsTab:
    def __init__(self, key: str):
        self.api_key_inputs = [QLineEdit() for _ in range(8)]
        self.api_key_inputs[0].setText(key)
        self.api_count_label = QLabel()
        self.gui = None
        self.refresh_count = 0

    def _update_key_count(self):
        self.refresh_count += 1

    def _refresh_setup_assistant_status(self):
        pass


def test_save_keeps_working_when_an_empty_slot_credential_read_raises(monkeypatch):
    key = "AQ." + "a" * 40
    panel = _FakeSettingsTab(key)
    stored = {}
    messages = []

    def get_api_key(name):
        if name == "gemini_api_1":
            return stored.get(name)
        raise RuntimeError("credential backend unavailable")

    def store_api_key(name, value):
        stored[name] = value
        return True

    monkeypatch.setattr(
        "ui.panels.settings_tab.SecretsManager.get_api_key",
        get_api_key,
    )
    monkeypatch.setattr(
        "ui.panels.settings_tab.SecretsManager.store_api_key",
        store_api_key,
    )
    monkeypatch.setattr(
        "ui.components.custom_dialog.show_info",
        lambda _parent, title, message: messages.append((title, message)),
    )
    monkeypatch.setattr(
        "ui.components.custom_dialog.show_warning",
        lambda *_args, **_kwargs: raise_unexpected("warning"),
    )
    monkeypatch.setattr(
        "ui.components.custom_dialog.show_error",
        lambda *_args, **_kwargs: raise_unexpected("error"),
    )

    SettingsTab._save_all_api_keys(panel)

    assert stored == {"gemini_api_1": key}
    assert panel.refresh_count == 1
    assert messages and messages[-1][0] == "저장 완료"


def raise_unexpected(kind):
    raise AssertionError(f"unexpected {kind} dialog")
