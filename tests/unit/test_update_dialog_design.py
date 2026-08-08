import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from ui.windows.update_dialog import (
    UpdateCompleteDialog,
    UpdateProgressDialog,
    UpdateReadyDialog,
)


QT_APP = QApplication.instance() or QApplication([])


def _app():
    return QT_APP


def test_progress_dialog_has_readable_landscape_proportions_and_text():
    _app()
    dialog = UpdateProgressDialog(version="1.5.50", release_notes="안정성 개선")

    assert 1.25 <= dialog.width() / dialog.height() <= 1.75
    assert dialog.width() >= 520
    assert dialog.height() <= 420
    assert dialog.progress_bar.height() >= 12
    assert dialog.percent_label.font().pointSize() <= 24
    texts = [label.text() for label in dialog.findChildren(QLabel)]
    assert "업데이트를 준비하고 있어요" in texts
    assert not any("⬇" in text or "✅" in text for text in texts)


def test_complete_dialog_uses_full_width_action_and_gentle_countdown():
    _app()
    dialog = UpdateCompleteDialog(version="1.5.50", release_notes="안정성 개선")

    assert dialog.confirm_btn.height() >= 44
    assert dialog.confirm_btn.width() >= 300
    assert dialog.COUNTDOWN_SECONDS >= 10
    assert dialog.confirm_btn.text() == "SSMaker 시작"


def test_update_action_buttons_have_accessible_names():
    _app()
    dialog = UpdateCompleteDialog(version="1.5.50", release_notes="안정성 개선")
    buttons = dialog.findChildren(QPushButton)

    assert buttons
    assert all(button.accessibleName().strip() for button in buttons)


def test_deferred_update_notice_is_deleted_after_close():
    _app()
    dialog = UpdateReadyDialog(version="1.5.50")

    assert dialog.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
