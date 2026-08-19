import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QScrollArea, QWidget

from ui.windows.api_key_error_dialog import ApiKeyErrorDialog


QT_APP = QApplication.instance() or QApplication([])


def test_api_key_recovery_uses_the_branded_alert_surface():
    dialog = ApiKeyErrorDialog(
        step_name="대본 생성",
        key_name="Gemini 2",
        error_msg="quota exceeded",
    )
    QT_APP.processEvents()

    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    assert dialog.accessibleName() == "API 키 복구"
    assert dialog.findChild(QFrame, "dialogSurface") is not None
    assert dialog.findChild(QFrame, "dialogTitleBar") is not None
    assert dialog.findChild(QFrame, "dialogMessagePanel") is not None
    assert dialog.findChild(QScrollArea, "dialogMessageScroll") is not None

    close = dialog.findChild(QPushButton, "dialogCloseButton")
    assert close.accessibleName() == "API 키 복구 창 닫기"
    assert close.width() >= 44 and close.height() >= 44

    actions = [dialog.retry_btn, dialog.settings_btn, dialog.stop_btn]
    assert all(button.minimumHeight() >= 44 for button in actions)
    assert all(button.accessibleName().strip() for button in actions)
    assert dialog.retry_btn.isDefault()
    assert not any("⚠" in label.text() for label in dialog.findChildren(QLabel))
    dialog.close()


def test_api_key_dialog_enter_retries_and_escape_stops():
    retry = ApiKeyErrorDialog(error_msg="quota exceeded")
    retry.show()
    QT_APP.processEvents()
    QTest.keyClick(retry, Qt.Key.Key_Return)
    assert retry.result_action == "retry"

    stop = ApiKeyErrorDialog(error_msg="quota exceeded")
    stop.show()
    QT_APP.processEvents()
    QTest.keyClick(stop, Qt.Key.Key_Escape)
    assert stop.result_action == "stop"
    assert not stop.isVisible()


def test_settings_action_keeps_recovery_dialog_open():
    class Parent(QWidget):
        def __init__(self):
            super().__init__()
            self.steps = []

        def _on_step_selected(self, step):
            self.steps.append(step)

    parent = Parent()
    dialog = ApiKeyErrorDialog(parent=parent, error_msg="quota exceeded")
    dialog.show()
    QT_APP.processEvents()
    QTest.mouseClick(dialog.settings_btn, Qt.MouseButton.LeftButton)

    assert parent.steps == ["settings"]
    assert dialog.isVisible()
    assert dialog.result_action == "stop"
    dialog.close()


def test_api_key_dialog_has_no_legacy_light_palette_literals():
    source = (
        Path(__file__).resolve().parents[2]
        / "ui"
        / "windows"
        / "api_key_error_dialog.py"
    ).read_text(encoding="utf-8")

    for legacy_color in ("#EFF6FF", "#2563EB", "#FEF2F2", "#F3F4F6"):
        assert legacy_color not in source


def test_drive_permission_guidance_is_not_misreported_as_an_api_key_failure():
    dialog = ApiKeyErrorDialog(
        error_type="permission",
        error_msg="Google Drive: You do not have permission to access the file",
    )
    guidance = dialog.findChild(QLabel, "apiKeyGuidanceText")

    assert "API 키가 아니라 Google Drive 공유 권한 문제" in guidance.text()
    dialog.close()
