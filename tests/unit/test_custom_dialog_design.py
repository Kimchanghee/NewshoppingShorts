import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QScrollArea

from ui.components.custom_dialog import CustomDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize("dialog_type", ["info", "warning", "error", "question", "success"])
def test_alert_variants_use_branded_frameless_surface(qapp, dialog_type):
    dialog = CustomDialog(
        None,
        "디자인 확인",
        "메인 화면과 같은 디자인 토큰을 사용하는 알림입니다.",
        dialog_type,
    )
    qapp.processEvents()

    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert dialog.accessibleName() == "디자인 확인"
    assert dialog.findChild(QFrame, "dialogSurface") is not None
    assert dialog.findChild(QFrame, "dialogTitleBar") is not None
    assert dialog.findChild(QFrame, "dialogMessagePanel") is not None
    assert dialog.findChild(QScrollArea, "dialogMessageScroll") is not None
    assert dialog.findChild(QPushButton, "dialogCloseButton").accessibleName() == "알림 닫기"
    assert dialog.findChild(QPushButton, "dialogCloseButton").height() >= 44

    message = dialog.findChild(QLabel, "dialogMessageLabel")
    assert message.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse

    primary = dialog.findChild(QPushButton, "dialogPrimaryButton")
    assert primary.minimumHeight() >= 44
    assert primary.isDefault()
    dialog.close()


def test_alert_width_stays_readable_and_inside_screen(qapp):
    dialog = CustomDialog(
        None,
        "일부 기능 복구 안내",
        "\n\n".join(f"• 연결 기능 {index}\n  다시 설정해 주세요." for index in range(1, 9)),
        "warning",
    )
    qapp.processEvents()

    available_width = (dialog.screen() or qapp.primaryScreen()).availableGeometry().width()
    assert 390 <= dialog.width() <= 520
    assert dialog.width() <= available_width
    dialog.close()


def test_question_buttons_keep_secondary_then_primary_order(qapp):
    results = []
    dialog = None
    dialog = CustomDialog(
        None,
        "계속 진행할까요?",
        "선택한 작업을 실행합니다.",
        "question",
        buttons=[
            ("아니오", lambda: results.append(False)),
            ("예", lambda: results.append(True)),
        ],
    )
    buttons = dialog.findChildren(QPushButton)
    action_buttons = [button for button in buttons if button.text() in {"아니오", "예"}]

    assert [button.text() for button in action_buttons] == ["아니오", "예"]
    assert action_buttons[0].objectName() == "dialogSecondaryButton"
    assert action_buttons[1].objectName() == "dialogPrimaryButton"
    action_buttons[1].click()
    assert results == [True]
    dialog.close()


def test_enter_confirms_and_escape_closes(qapp):
    confirm = CustomDialog(None, "확인", "Enter 키로 확인합니다.", "info")
    confirm.show()
    qapp.processEvents()
    QTest.keyClick(confirm, Qt.Key.Key_Return)
    assert confirm.result_value is True

    cancel = CustomDialog(None, "확인", "Esc 키로 닫습니다.", "question")
    cancel.show()
    qapp.processEvents()
    QTest.keyClick(cancel, Qt.Key.Key_Escape)
    assert not cancel.isVisible()
    assert cancel.result_value is None


def test_remaining_popup_paths_do_not_construct_native_message_boxes():
    root = Path(__file__).resolve().parents[2]
    sourcing = (root / "ui" / "panels" / "sourcing_panel.py").read_text(encoding="utf-8")
    system_check = (root / "startup" / "system_check.py").read_text(encoding="utf-8")

    assert "QMessageBox" not in sourcing
    assert "QMessageBox" not in system_check


def test_alert_hides_internal_codes_and_raw_english_errors(qapp):
    dialog = CustomDialog(
        None,
        "PermissionError: Access denied",
        "[caller.rest/LOGIN_REJECTED]\nInvalid credentials for request_id=abc123",
        "error",
    )
    qapp.processEvents()

    message = dialog.findChild(QLabel, "dialogMessageLabel").text()
    assert dialog.windowTitle() == "오류"
    assert "PermissionError" not in dialog.windowTitle()
    assert "LOGIN_REJECTED" not in message
    assert "request_id" not in message
    assert "Invalid credentials" not in message
    assert any("아이디" in label.text() for label in dialog.findChildren(QLabel))
    dialog.close()


def test_user_message_surfaces_keep_technical_details_out_of_ui_contract():
    root = Path(__file__).resolve().parents[2]
    login_window = (root / "ui" / "windows" / "login_window.py").read_text(encoding="utf-8")
    progress_panel = (root / "ui" / "panels" / "progress_panel.py").read_text(encoding="utf-8")
    multi_account = (root / "ui" / "panels" / "multi_account_panel.py").read_text(encoding="utf-8")
    final_video = (root / "core" / "video" / "CreateFinalVideo.py").read_text(encoding="utf-8")

    assert 'display_msg = f"[{error_module}/{error_code}]' not in login_window
    assert "sanitize_user_message(task_text" in progress_panel
    assert "msg = sanitize_user_message(" in multi_account
    assert 'show_error(app.root, "영상 만들기 실패", error_msg)' in final_video
