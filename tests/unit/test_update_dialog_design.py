import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit

from ui.windows.update_dialog import (
    UpdateCompleteDialog,
    UpdateNotesDialog,
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


def test_update_surface_uses_shared_dark_design_tokens_and_large_close_target():
    _app()
    from ui.design_system_v2 import get_color
    from ui.windows.update_dialog import _colors

    colors = _colors()
    dialog = UpdateNotesDialog(version="1.5.69", release_notes="업데이트 디자인을 통일했습니다.")

    assert colors["card"] == get_color("surface")
    assert colors["outer"] == get_color("background")
    assert colors["primary"] == get_color("primary")
    assert dialog.close_x_btn.width() >= 44
    assert dialog.close_x_btn.height() >= 44


def test_update_notes_hide_internal_english_release_metadata():
    _app()
    dialog = UpdateNotesDialog(
        version="1.5.64",
        release_notes="SSMaker v1.5.64: return to login after logout",
    )
    notes = dialog.findChild(QTextEdit, "releaseNotes")

    assert notes.toPlainText() == "안정성과 사용성을 개선했습니다."
    assert "return to login" not in notes.toPlainText()
    assert dialog.close_btn.text() == "닫기"
    assert dialog.close_x_btn.accessibleName() == "업데이트 안내 닫기"


def test_update_notes_keep_customer_facing_korean_copy():
    _app()
    dialog = UpdateNotesDialog(
        version="1.5.65",
        release_notes="SSMaker v1.5.65: 로그인 화면 이동을 개선했습니다.",
    )
    notes = dialog.findChild(QTextEdit, "releaseNotes")

    assert notes.toPlainText() == "로그인 화면 이동을 개선했습니다."


def test_update_notes_close_button_hides_window_and_emits_once():
    app = _app()
    dialog = UpdateNotesDialog(version="1.5.65", release_notes="사용성을 개선했습니다.")
    closed = []
    dialog.closed.connect(lambda: closed.append(True))
    dialog.show()
    app.processEvents()

    QTest.mouseClick(dialog.close_btn, Qt.MouseButton.LeftButton)

    assert not dialog.isVisible()
    assert closed == [True]


def test_update_notes_escape_uses_the_same_close_path():
    app = _app()
    dialog = UpdateNotesDialog(version="1.5.65", release_notes="사용성을 개선했습니다.")
    closed = []
    dialog.closed.connect(lambda: closed.append(True))
    dialog.show()
    app.processEvents()

    QTest.keyClick(dialog, Qt.Key.Key_Escape)

    assert not dialog.isVisible()
    assert closed == [True]


def test_update_notes_titlebar_close_uses_the_same_close_path():
    app = _app()
    dialog = UpdateNotesDialog(version="1.5.65", release_notes="사용성을 개선했습니다.")
    closed = []
    dialog.closed.connect(lambda: closed.append(True))
    dialog.show()
    app.processEvents()

    QTest.mouseClick(dialog.close_x_btn, Qt.MouseButton.LeftButton)

    assert not dialog.isVisible()
    assert closed == [True]


def test_deferred_update_notice_is_deleted_after_close():
    _app()
    dialog = UpdateReadyDialog(version="1.5.50")

    assert dialog.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
