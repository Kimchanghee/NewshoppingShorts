"""
URL queue manager rewritten for PyQt6 widgets.
"""

import re
from datetime import datetime
from typing import List

from ui.components.custom_dialog import show_info, show_warning, show_error, show_question
from utils.logging_config import get_logger
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

logger = get_logger(__name__)

URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")


class QueueManager:
    """Manages URL queue and mirrors state to a QTreeWidget."""

    def __init__(self, gui):
        self.gui = gui

    # ----------------------- queue operations -----------------------
    def remove_selected_url(self):
        tree: QTreeWidget = getattr(self.gui, "url_listbox", None)
        if tree is None:
            return
        selected = tree.selectedItems()
        if not selected:
            return
        item = selected[0]
        url_value = item.text(1)
        status = self.gui.url_status.get(url_value)
        if status == "processing":
            show_warning(self.gui, "경고", "현재 처리 중입니다.")
            return
        if url_value in self.gui.url_queue:
            self.gui.url_queue.remove(url_value)
        self.gui.url_status.pop(url_value, None)
        self.update_url_listbox()
        self.update_queue_count()
        self.add_log(f"URL 삭제: {url_value[:60]}...")

    def clear_url_queue(self):
        if not self.gui.url_queue and not self.gui.url_status:
            return
        if not show_question(self.gui, "확인", "대기 중인 모든 URL을 삭제하시겠습니까?\n(완료/실패 기록도 모두 삭제됩니다)"):
            return

        processing = [url for url, status in self.gui.url_status.items() if status == "processing"]
        self.gui.url_queue = processing
        self.gui.url_status = {url: "processing" for url in processing}
        if hasattr(self.gui, "url_timestamps"):
            self.gui.url_timestamps = {url: ts for url, ts in self.gui.url_timestamps.items() if url in processing}
        if hasattr(self.gui, "url_status_message"):
            self.gui.url_status_message = {url: msg for url, msg in self.gui.url_status_message.items() if url in processing}
        if hasattr(self.gui, "generated_videos"):
            self.gui.generated_videos = []

        self.update_url_listbox()
        self.update_queue_count()
        self.add_log("URL 대기열 전체 초기화(완료/실패 기록 포함)")

    def clear_waiting_only(self):
        waiting_urls = [url for url, status in self.gui.url_status.items() if status == "waiting"]
        if not waiting_urls:
            show_info(self.gui, "안내", "대기 중인 URL이 없습니다.")
            return
        if not show_question(self.gui, "확인", "대기 상태 URL만 삭제할까요?"):
            return
        for url in waiting_urls:
            if url in self.gui.url_queue:
                self.gui.url_queue.remove(url)
            self.gui.url_status.pop(url, None)
        self.update_url_listbox()
        self.update_queue_count()
        self.add_log("대기 URL 삭제 완료")

    # ----------------------- UI sync helpers -----------------------
    def update_url_listbox(self):
        tree: QTreeWidget = getattr(self.gui, "url_listbox", None)
        if tree is None:
            return
        tree.clear()

        status_labels = {
            "waiting": "대기",
            "processing": "진행 중",
            "completed": "완료",
            "failed": "실패",
            "skipped": "건너뜀",
        }

        for idx, url in enumerate(self.gui.url_queue, 1):
            status = self.gui.url_status.get(url, "waiting")
            order_label = "진행" if status == "processing" else "대기"
            order_text = f"{order_label} {idx}"
            if status == "processing":
                step_msg = self.gui.url_status_message.get(url, "")
                status_text = step_msg if step_msg else "진행 중"
            else:
                status_text = status_labels.get(status, status)
            remarks_text = ""
            if status == "completed":
                remarks_text = self.gui.url_remarks.get(url, "")
            elif status in ("failed", "skipped"):
                remarks_text = self.gui.url_status_message.get(url, "")

            item = QTreeWidgetItem([order_text, url, status_text, remarks_text])
            tree.addTopLevelItem(item)

        processed_items = [
            (url, status)
            for url, status in self.gui.url_status.items()
            if url not in self.gui.url_queue and status in ("completed", "failed", "skipped")
        ]
        for url, status in processed_items:
            order_text = "완료" if status == "completed" else "건너뜀" if status == "skipped" else "실패"
            status_text = status_labels.get(status, status)
            remarks_text = self.gui.url_remarks.get(url, "") if status == "completed" else self.gui.url_status_message.get(url, "")
            item = QTreeWidgetItem([order_text, url, status_text, remarks_text])
            tree.addTopLevelItem(item)

        self.update_queue_count()

    def update_queue_count(self):
        counts = {k: 0 for k in ("processing", "waiting", "completed", "skipped", "failed")}
        for status in self.gui.url_status.values():
            if status in counts:
                counts[status] += 1

        self.gui.count_processing.setText(f"🚥 진행 {counts['processing']}")
        self.gui.count_waiting.setText(f"⏳ 대기 {counts['waiting']}")
        self.gui.count_completed.setText(f"✅ 완료 {counts['completed']}")
        self.gui.count_skipped.setText(f"⏭️ 건너뜀 {counts['skipped']}")
        self.gui.count_failed.setText(f"⛔ 실패 {counts['failed']}")

        total = len(self.gui.url_status)
        completed = counts["completed"]
        if hasattr(self.gui, "overall_numeric_label"):
            percent = (completed / total * 100) if total else 0
            self.gui.overall_numeric_label.setText(f"{completed}/{total} ({percent:.0f}%)")

    def update_queue_status(self, url: str, status: str, message: str = ""):
        if url not in self.gui.url_status:
            self.gui.url_status[url] = status
            self.gui.url_queue.append(url)
        else:
            self.gui.url_status[url] = status

        if message:
            self.gui.url_status_message[url] = message
        self.update_url_listbox()

    # ----------------------- logging -----------------------
    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        if hasattr(self.gui, "log_signal"):
            self.gui.log_signal.emit(full_msg, level)
        else:
            logger.log(getattr(logger, level, logger.info), full_msg)
