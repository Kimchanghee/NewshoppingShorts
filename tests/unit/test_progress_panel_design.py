import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from ui.components.subscription_dialog import SubscriptionDialog
from ui.components.trial_limit_dialog import TrialLimitDialog
from ui.panels.progress_panel import ProgressPanel


_APP = QApplication.instance() or QApplication([])


def test_overall_progress_label_keeps_bar_and_badge_in_sync():
    host = QWidget()
    panel = ProgressPanel(host, host)

    host.overall_numeric_label.setText("2/5 (40%)")
    _APP.processEvents()

    assert panel.overall_bar.value() == 40
    assert panel.overall_status_badge.text() == "진행 중"
    panel.close()
    host.close()


def test_current_progress_exposes_pending_active_complete_and_error_states():
    host = QWidget()
    panel = ProgressPanel(host, host)

    panel.update_step_status("download", "completed", 100)
    panel.update_step_status("ocr_analysis", "active", 64)
    panel.update_step_status("translation", "error", 42)
    panel.set_current_task("번역 단계에서 확인이 필요합니다", "error")
    _APP.processEvents()

    assert host.step_indicators["download"]["progress_label"].text() == "100%"
    assert host.step_indicators["ocr_analysis"]["progress_label"].text() == "64%"
    assert host.step_indicators["translation"]["progress_label"].text() == "42%"
    assert panel.status_title.text() == "오류"
    panel.close()
    host.close()


def test_usage_dialogs_share_the_same_secondary_then_primary_action_hierarchy():
    for dialog in (
        TrialLimitDialog(used=5, total=5),
        SubscriptionDialog(user_id="preview", work_used=5, work_count=5),
    ):
        actions = {
            button.text(): button.objectName()
            for button in dialog.findChildren(QPushButton)
            if button.text() in {"닫기", "구독 관리 열기"}
        }
        assert actions == {
            "닫기": "dialogSecondaryButton",
            "구독 관리 열기": "dialogPrimaryButton",
        }
        dialog.close()
