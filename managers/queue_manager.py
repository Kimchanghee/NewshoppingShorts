"""
URL queue manager rewritten for PyQt6 widgets.
"""

import re
from datetime import datetime
from typing import List

from ui.components.custom_dialog import show_info, show_warning, show_error, show_question
from utils.logging_config import get_logger
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from managers.settings_manager import get_settings_manager

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

        # Get auto-upload status dict from state
        auto_upload_status = getattr(self.gui, 'url_auto_upload_status', {})
        if not auto_upload_status and hasattr(self.gui, 'state'):
            auto_upload_status = getattr(self.gui.state, 'url_auto_upload_status', {})

        for idx, url in enumerate(self.gui.url_queue, 1):
            status = self.gui.url_status.get(url, "waiting")
            order_label = "진행" if status == "processing" else "대기"
            order_text = f"{order_label} {idx}"
            if status == "processing":
                step_msg = self.gui.url_status_message.get(url, "")
                status_text = step_msg if step_msg else "진행 중"
            else:
                status_text = status_labels.get(status, status)

            # Auto-upload status column
            auto_upload_text = auto_upload_status.get(url, "")
            if not auto_upload_text:
                # Determine based on settings
                settings = get_settings_manager()
                if settings.get_youtube_auto_upload() and settings.get_youtube_connected():
                    auto_upload_text = "YouTube"
                else:
                    auto_upload_text = "비활성"

            remarks_text = ""
            if status == "completed":
                remarks_text = self.gui.url_remarks.get(url, "")
            elif status in ("failed", "skipped"):
                remarks_text = self.gui.url_status_message.get(url, "")

            item = QTreeWidgetItem([order_text, url, status_text, auto_upload_text, remarks_text])
            tree.addTopLevelItem(item)

        processed_items = [
            (url, status)
            for url, status in self.gui.url_status.items()
            if url not in self.gui.url_queue and status in ("completed", "failed", "skipped")
        ]
        for url, status in processed_items:
            order_text = "완료" if status == "completed" else "건너뜀" if status == "skipped" else "실패"
            status_text = status_labels.get(status, status)

            # Auto-upload status for completed items
            auto_upload_text = auto_upload_status.get(url, "")
            if not auto_upload_text and status == "completed":
                settings = get_settings_manager()
                if settings.get_youtube_auto_upload() and settings.get_youtube_connected():
                    auto_upload_text = "YouTube"
                else:
                    auto_upload_text = "비활성"
            elif not auto_upload_text:
                auto_upload_text = "-"

            remarks_text = self.gui.url_remarks.get(url, "") if status == "completed" else self.gui.url_status_message.get(url, "")
            item = QTreeWidgetItem([order_text, url, status_text, auto_upload_text, remarks_text])
            tree.addTopLevelItem(item)

        self.update_queue_count()

    def update_queue_count(self):
        if not self.gui:
            return

        url_status = getattr(self.gui, "url_status", None)
        if url_status is None:
            return

        counts = {k: 0 for k in ("processing", "waiting", "completed", "skipped", "failed")}
        for status in url_status.values():
            if status in counts:
                counts[status] += 1

        # 안전한 위젯 접근 - 위젯이 None이거나 초기화 전이면 건너뜀
        count_labels = [
            ("count_processing", f"🚥 진행 {counts['processing']}"),
            ("count_waiting", f"⏳ 대기 {counts['waiting']}"),
            ("count_completed", f"✅ 완료 {counts['completed']}"),
            ("count_skipped", f"⏭️ 건너뜀 {counts['skipped']}"),
            ("count_failed", f"⛔ 실패 {counts['failed']}"),
        ]
        for attr, text in count_labels:
            label = getattr(self.gui, attr, None)
            if label is not None:
                label.setText(text)

        total = len(url_status)
        completed = counts["completed"]
        overall_label = getattr(self.gui, "overall_numeric_label", None)
        if overall_label is not None:
            percent = (completed / total * 100) if total else 0
            overall_label.setText(f"{completed}/{total} ({percent:.0f}%)")

    def update_queue_status(self, url: str, status: str, message: str = ""):
        if url not in self.gui.url_status:
            self.gui.url_status[url] = status
            self.gui.url_queue.append(url)
        else:
            self.gui.url_status[url] = status

        if message:
            self.gui.url_status_message[url] = message
        self.update_url_listbox()

    # ----------------------- URL input helpers -----------------------
    def _enqueue_urls(self, text: str, source_label: str) -> tuple:
        """Extract URLs from text and add non-duplicates to the queue.

        Returns (added_count, duplicate_count).
        """
        urls = URL_PATTERN.findall(text)
        if not urls:
            return 0, 0

        added_count = 0
        duplicate_count = 0

        for raw_url in urls:
            url = raw_url.strip()
            if url in self.gui.url_queue or url in self.gui.url_status:
                duplicate_count += 1
                continue
            self.gui.url_queue.append(url)
            self.gui.url_status[url] = "waiting"
            self.gui.url_timestamps[url] = datetime.now()
            added_count += 1

        self.update_url_listbox()
        self.update_queue_count()

        if added_count > 0:
            msg = f"{source_label} {added_count}개 URL이 추가되었습니다."
            if duplicate_count > 0:
                msg += f"\n({duplicate_count}개 중복 URL은 제외)"
            show_info(self.gui, "완료", msg)
            self.add_log(f"{source_label} URL {added_count}개 추가됨")
        elif duplicate_count > 0:
            show_warning(self.gui, "안내", f"모든 URL이 이미 대기열에 있습니다. ({duplicate_count}개)")

        return added_count, duplicate_count

    def add_url_from_entry(self):
        """Extract URLs from the entry widget and add to queue."""
        url_entry = getattr(self.gui, "url_entry", None)
        if url_entry is None:
            show_warning(self.gui, "오류", "URL 입력창을 찾을 수 없습니다.")
            return

        text = url_entry.toPlainText().strip()
        if not text:
            show_warning(self.gui, "안내", "URL을 입력해주세요.")
            return

        urls = URL_PATTERN.findall(text)
        if not urls:
            show_warning(self.gui, "안내", "유효한 URL을 찾을 수 없습니다.")
            return

        self._enqueue_urls(text, "")
        url_entry.clear()

    def paste_and_extract(self):
        """Extract URLs from clipboard and add to queue."""
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        text = clipboard.text()

        if not text or not text.strip():
            show_warning(self.gui, "안내", "클립보드가 비어 있습니다.")
            return

        urls = URL_PATTERN.findall(text)
        if not urls:
            show_warning(self.gui, "안내", "클립보드에서 유효한 URL을 찾을 수 없습니다.")
            return

        self._enqueue_urls(text, "클립보드에서")

    # ----------------------- logging -----------------------
    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        log_signal = getattr(self.gui, "log_signal", None) if self.gui else None
        if log_signal is not None:
            log_signal.emit(full_msg, level)
        else:
            log_method = getattr(logger, level, logger.info)
            log_method(full_msg)
