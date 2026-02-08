"""
Queue manager for URL jobs and mix jobs.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Iterable, List, Sequence
from uuid import uuid4

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from managers.settings_manager import get_settings_manager
from ui.components.custom_dialog import show_info, show_question, show_warning
from utils.logging_config import get_logger

logger = get_logger(__name__)

URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")
MIX_JOB_PREFIX = "mix://job/"


class QueueManager:
    """Manages URL queue and mirrors state to a QTreeWidget."""

    def __init__(self, gui):
        self.gui = gui
        self._ensure_mix_store()

    # ----------------------- mix helpers -----------------------
    def _ensure_mix_store(self) -> Dict[str, List[str]]:
        mix_jobs = getattr(self.gui, "mix_jobs", None)
        if not isinstance(mix_jobs, dict):
            mix_jobs = {}
            self.gui.mix_jobs = mix_jobs
        state = getattr(self.gui, "state", None)
        if state is not None:
            setattr(state, "mix_jobs", mix_jobs)
        return mix_jobs

    def _is_mix_job(self, key: str) -> bool:
        return isinstance(key, str) and key.startswith(MIX_JOB_PREFIX)

    def get_mix_job_urls(self, key: str) -> List[str]:
        if not self._is_mix_job(key):
            return []
        mix_jobs = self._ensure_mix_store()
        urls = mix_jobs.get(key, [])
        return list(urls) if isinstance(urls, list) else []

    def _set_mix_job_urls(self, key: str, urls: Sequence[str]) -> None:
        mix_jobs = self._ensure_mix_store()
        mix_jobs[key] = [u.strip() for u in urls if isinstance(u, str) and u.strip()]

    def _remove_mix_job(self, key: str) -> None:
        mix_jobs = self._ensure_mix_store()
        mix_jobs.pop(key, None)

    def _prune_mix_jobs(self, keep_keys: Iterable[str]) -> None:
        keep = set(keep_keys)
        mix_jobs = self._ensure_mix_store()
        stale = [k for k in mix_jobs.keys() if k not in keep]
        for key in stale:
            mix_jobs.pop(key, None)

    def _to_display_url(self, key: str) -> str:
        if not self._is_mix_job(key):
            return key
        mix_urls = self.get_mix_job_urls(key)
        short_id = key.rsplit("/", 1)[-1][:6]
        if mix_urls:
            return f"[MIX:{short_id}] {len(mix_urls)} clips"
        return f"[MIX:{short_id}]"

    def get_display_url(self, key: str) -> str:
        return self._to_display_url(key)

    def _find_queue_key_by_display(self, display_value: str) -> str:
        if display_value in self.gui.url_queue or display_value in self.gui.url_status:
            return display_value
        for key in self.gui.url_queue:
            if self._to_display_url(key) == display_value:
                return key
        for key in self.gui.url_status.keys():
            if self._to_display_url(key) == display_value:
                return key
        return display_value

    def add_mix_job(self, urls: Sequence[str]) -> str:
        clean_urls = [u.strip() for u in urls if isinstance(u, str) and u.strip()]
        clean_urls = clean_urls[:5]
        if len(clean_urls) < 2:
            raise ValueError("Mix mode requires at least 2 URLs.")

        key = f"{MIX_JOB_PREFIX}{uuid4().hex[:12]}"
        self._set_mix_job_urls(key, clean_urls)
        self.add_url_to_queue(key)
        return key

    # ----------------------- queue operations -----------------------
    def add_url_to_queue(self, url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        key = url.strip()
        if not key:
            return False
        if key in self.gui.url_queue or key in self.gui.url_status:
            return False

        self.gui.url_queue.append(key)
        self.gui.url_status[key] = "waiting"
        if hasattr(self.gui, "url_timestamps"):
            self.gui.url_timestamps[key] = datetime.now()

        self.update_url_listbox()
        self.update_queue_count()
        return True

    def remove_selected_url(self):
        tree: QTreeWidget = getattr(self.gui, "url_listbox", None)
        if tree is None:
            return

        selected = tree.selectedItems()
        if not selected:
            return

        item = selected[0]
        display_value = item.text(1)
        key = self._find_queue_key_by_display(display_value)
        status = self.gui.url_status.get(key)
        if status == "processing":
            show_warning(self.gui, "Warning", "Current job is processing.")
            return

        if key in self.gui.url_queue:
            self.gui.url_queue.remove(key)
        self.gui.url_status.pop(key, None)
        self.gui.url_status_message.pop(key, None)
        self.gui.url_remarks.pop(key, None)
        self._remove_mix_job(key)

        self.update_url_listbox()
        self.update_queue_count()
        self.add_log(f"Removed: {display_value[:80]}")

    def clear_url_queue(self):
        if not self.gui.url_queue and not self.gui.url_status:
            return
        if not show_question(
            self.gui,
            "Confirm",
            "Clear all queued URLs? (completed/failed history will be removed)",
        ):
            return

        processing = [
            url for url, status in self.gui.url_status.items() if status == "processing"
        ]
        self.gui.url_queue[:] = processing
        self.gui.url_status.clear()
        self.gui.url_status.update({url: "processing" for url in processing})
        if hasattr(self.gui, "url_timestamps"):
            kept_timestamps = {
                url: ts for url, ts in self.gui.url_timestamps.items() if url in processing
            }
            self.gui.url_timestamps.clear()
            self.gui.url_timestamps.update(kept_timestamps)
        if hasattr(self.gui, "url_status_message"):
            kept_messages = {
                url: msg
                for url, msg in self.gui.url_status_message.items()
                if url in processing
            }
            self.gui.url_status_message.clear()
            self.gui.url_status_message.update(kept_messages)
        if hasattr(self.gui, "url_remarks"):
            kept_remarks = {
                url: remark
                for url, remark in self.gui.url_remarks.items()
                if url in processing
            }
            self.gui.url_remarks.clear()
            self.gui.url_remarks.update(kept_remarks)
        if hasattr(self.gui, "generated_videos"):
            self.gui.generated_videos = []

        self._prune_mix_jobs(set(processing))
        self.update_url_listbox()
        self.update_queue_count()
        self.add_log("Queue cleared (processing items kept).")

    def clear_waiting_only(self):
        waiting_urls = [
            url for url, status in self.gui.url_status.items() if status == "waiting"
        ]
        if not waiting_urls:
            show_info(self.gui, "Info", "No waiting URLs.")
            return
        if not show_question(self.gui, "Confirm", "Clear waiting URLs only?"):
            return

        for key in waiting_urls:
            if key in self.gui.url_queue:
                self.gui.url_queue.remove(key)
            self.gui.url_status.pop(key, None)
            self.gui.url_status_message.pop(key, None)
            self.gui.url_remarks.pop(key, None)
            self._remove_mix_job(key)

        self.update_url_listbox()
        self.update_queue_count()
        self.add_log("Waiting URLs cleared.")

    # ----------------------- UI sync helpers -----------------------
    def update_url_listbox(self):
        tree: QTreeWidget = getattr(self.gui, "url_listbox", None)
        if tree is None:
            return
        tree.clear()

        status_labels = {
            "waiting": "Waiting",
            "processing": "Processing",
            "completed": "Completed",
            "failed": "Failed",
            "skipped": "Skipped",
        }

        auto_upload_status = getattr(self.gui, "url_auto_upload_status", {})
        if not auto_upload_status and hasattr(self.gui, "state"):
            auto_upload_status = getattr(self.gui.state, "url_auto_upload_status", {})

        for idx, key in enumerate(self.gui.url_queue, 1):
            status = self.gui.url_status.get(key, "waiting")
            display_url = self._to_display_url(key)
            order_label = "Processing" if status == "processing" else "Waiting"
            order_text = f"{order_label} {idx}"

            if status == "processing":
                step_msg = self.gui.url_status_message.get(key, "")
                status_text = step_msg if step_msg else "Processing"
            else:
                status_text = status_labels.get(status, status)

            auto_upload_text = auto_upload_status.get(key, "")
            if not auto_upload_text:
                settings = get_settings_manager()
                if settings.get_youtube_auto_upload() and settings.get_youtube_connected():
                    auto_upload_text = "YouTube"
                else:
                    auto_upload_text = "Disabled"

            remarks_text = ""
            if status == "completed":
                remarks_text = self.gui.url_remarks.get(key, "")
            elif status in ("failed", "skipped"):
                remarks_text = self.gui.url_status_message.get(key, "")

            item = QTreeWidgetItem(
                [order_text, display_url, status_text, auto_upload_text, remarks_text]
            )
            tree.addTopLevelItem(item)

        processed_items = [
            (key, status)
            for key, status in self.gui.url_status.items()
            if key not in self.gui.url_queue and status in ("completed", "failed", "skipped")
        ]
        for key, status in processed_items:
            display_url = self._to_display_url(key)
            order_text = (
                "Completed"
                if status == "completed"
                else "Skipped" if status == "skipped" else "Failed"
            )
            status_text = status_labels.get(status, status)

            auto_upload_text = auto_upload_status.get(key, "")
            if not auto_upload_text and status == "completed":
                settings = get_settings_manager()
                if settings.get_youtube_auto_upload() and settings.get_youtube_connected():
                    auto_upload_text = "YouTube"
                else:
                    auto_upload_text = "Disabled"
            elif not auto_upload_text:
                auto_upload_text = "-"

            remarks_text = (
                self.gui.url_remarks.get(key, "")
                if status == "completed"
                else self.gui.url_status_message.get(key, "")
            )
            item = QTreeWidgetItem(
                [order_text, display_url, status_text, auto_upload_text, remarks_text]
            )
            tree.addTopLevelItem(item)

        keep = set(self.gui.url_queue).union(self.gui.url_status.keys())
        self._prune_mix_jobs(keep)
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

        count_labels = [
            ("count_processing", f"Processing {counts['processing']}"),
            ("count_waiting", f"Waiting {counts['waiting']}"),
            ("count_completed", f"Completed {counts['completed']}"),
            ("count_skipped", f"Skipped {counts['skipped']}"),
            ("count_failed", f"Failed {counts['failed']}"),
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
        urls = URL_PATTERN.findall(text)
        if not urls:
            return 0, 0

        added_count = 0
        duplicate_count = 0

        for raw_url in urls:
            url = raw_url.strip()
            if not url:
                continue
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
            msg = f"{source_label} added {added_count} URL(s)."
            if duplicate_count > 0:
                msg += f"\nSkipped duplicates: {duplicate_count}"
            show_info(self.gui, "Done", msg)
            self.add_log(f"{source_label} added {added_count} URL(s)")
        elif duplicate_count > 0:
            show_warning(self.gui, "Info", f"All URLs were duplicates ({duplicate_count}).")

        return added_count, duplicate_count

    def add_url_from_entry(self):
        url_entry = getattr(self.gui, "url_entry", None)
        if url_entry is None:
            show_warning(self.gui, "Error", "URL input widget not found.")
            return

        text = url_entry.toPlainText().strip()
        if not text:
            show_warning(self.gui, "Info", "Please enter URL(s).")
            return

        urls = URL_PATTERN.findall(text)
        if not urls:
            show_warning(self.gui, "Info", "No valid URL found.")
            return

        self._enqueue_urls(text, "Input")
        url_entry.clear()

    def paste_and_extract(self):
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        text = clipboard.text()

        if not text or not text.strip():
            show_warning(self.gui, "Info", "Clipboard is empty.")
            return

        urls = URL_PATTERN.findall(text)
        if not urls:
            show_warning(self.gui, "Info", "No valid URL found in clipboard.")
            return

        self._enqueue_urls(text, "Clipboard")

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
