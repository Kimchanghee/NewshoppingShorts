import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem

from managers.queue_manager import QueueManager
from ui.panels.queue_panel import QueuePanel


QT_APP = QApplication.instance() or QApplication([])


def _noop():
    return None


def test_delete_controls_show_counts_selection_and_result_feedback():
    actions = []
    manager = SimpleNamespace(
        _normalize_status=QueueManager._normalize_status,
        _last_summer_coupang_snapshot=None,
        update_url_listbox=_noop,
    )
    gui = SimpleNamespace(
        queue_manager=manager,
        url_queue=["local-waiting", "local-completed"],
        url_status={
            "local-waiting": "waiting",
            "local-completed": "completed",
        },
        start_batch_processing=_noop,
        stop_batch_processing=_noop,
        clear_waiting_only=lambda: actions.append("waiting"),
        clear_completed_only=lambda: actions.append("completed"),
        remove_selected_url=lambda: actions.append("selected"),
        clear_url_queue=lambda: actions.append("all"),
    )
    panel = QueuePanel(None, gui)
    snapshot = {
        "total": 3,
        "counts": {"waiting": 1, "completed": 1, "processing": 1},
    }

    panel.sync_delete_controls(snapshot)

    assert panel.clear_waiting_btn.text() == "대기 삭제 (2)"
    assert panel.clear_completed_btn.text() == "완료 삭제 (2)"
    assert panel.clear_btn.text() == "전체 삭제 (4)"
    assert panel.remove_btn.isEnabled() is False
    panel.clear_waiting_btn.click()
    panel.clear_completed_btn.click()
    panel.clear_btn.click()

    selected = QTreeWidgetItem(["대기", "https://example.com", "대기", "-", ""])
    selected.setData(
        0,
        Qt.ItemDataRole.UserRole,
        {"source": "scheduled", "id": "scheduled-1", "status": "waiting"},
    )
    gui.url_listbox.addTopLevelItem(selected)
    selected.setSelected(True)
    panel.sync_delete_controls(snapshot)

    assert panel.remove_btn.isEnabled() is True
    assert panel.remove_btn.text() == "선택 삭제 (1)"
    panel.remove_btn.click()
    assert actions == ["waiting", "completed", "all", "selected"]

    panel.show_delete_feedback("대기 중인 작업 2건을 삭제했습니다.")
    assert "2건을 삭제했습니다" in panel.delete_feedback_label.text()
    assert panel.delete_feedback_label.accessibleName() == "대기열 삭제 결과"

    panel.deleteLater()
