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
LEGACY_QUEUE_PREFIX_PATTERN = re.compile(
    r"^(?:(?:waiting|processing|completed|failed|skipped|done|error|대기|진행|완료|실패|건너뜀)\s+\d+\s+)",
    re.IGNORECASE,
)


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
            return self._strip_legacy_queue_prefix(key)
        mix_urls = self.get_mix_job_urls(key)
        short_id = key.rsplit("/", 1)[-1][:6]
        if mix_urls:
            return f"[믹스:{short_id}] {len(mix_urls)}개"
        return f"[믹스:{short_id}]"

    def get_display_url(self, key: str) -> str:
        return self._to_display_url(key)

    @staticmethod
    def _normalize_status(status: str) -> str:
        if status is None:
            return "waiting"
        raw = str(status).strip()
        if not raw:
            return "waiting"
        lowered = raw.lower()
        mapping = {
            "waiting": "waiting",
            "wait": "waiting",
            "대기": "waiting",
            "processing": "processing",
            "in progress": "processing",
            "진행": "processing",
            "진행 중": "processing",
            "completed": "completed",
            "complete": "completed",
            "done": "completed",
            "완료": "completed",
            "failed": "failed",
            "error": "failed",
            "실패": "failed",
            "skipped": "skipped",
            "skip": "skipped",
            "건너뜀": "skipped",
            "건너뛰기": "skipped",
        }
        return mapping.get(raw, mapping.get(lowered, lowered))

    @staticmethod
    def _localize_status_text(text: str) -> str:
        if text is None:
            return ""
        message = str(text).strip()
        if not message:
            return ""

        direct_map = {
            "waiting": "대기",
            "wait": "대기",
            "processing": "진행 중",
            "in progress": "진행 중",
            "completed": "완료",
            "complete": "완료",
            "done": "완료",
            "failed": "실패",
            "error": "실패",
            "skipped": "건너뜀",
            "skip": "건너뜀",
            "disabled": "사용 안 함",
            "connected": "연결됨",
            "youtube": "유튜브",
        }
        lowered = message.lower()
        if lowered in direct_map:
            return direct_map[lowered]

        for eng, kor in (
            ("waiting", "대기"),
            ("processing", "진행 중"),
            ("completed", "완료"),
            ("done", "완료"),
            ("failed", "실패"),
            ("error", "실패"),
            ("skipped", "건너뜀"),
            ("disabled", "사용 안 함"),
            ("connected", "연결됨"),
            ("youtube", "유튜브"),
        ):
            message = re.sub(rf"\b{re.escape(eng)}\b", kor, message, flags=re.IGNORECASE)
        return message

    @staticmethod
    def _normalize_source_label(source_label: str) -> str:
        raw = (source_label or "").strip()
        lowered = raw.lower()
        mapping = {
            "input": "입력창",
            "entry": "입력창",
            "clipboard": "클립보드",
        }
        return mapping.get(lowered, raw or "입력")

    @staticmethod
    def _strip_legacy_queue_prefix(text: str) -> str:
        raw = (text or "").strip()
        if not raw:
            return raw
        return LEGACY_QUEUE_PREFIX_PATTERN.sub("", raw)

    @staticmethod
    def _localize_upload_status(text: str) -> str:
        normalized_text = QueueManager._localize_status_text(text)
        mapping = {
            "YouTube": "유튜브",
            "youtube": "유튜브",
            "Disabled": "사용 안 함",
            "disabled": "사용 안 함",
            "Connected": "연결됨",
            "connected": "연결됨",
            "Enabled": "사용",
            "enabled": "사용",
        }
        return mapping.get(normalized_text, normalized_text)

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
            raise ValueError("믹스 모드는 링크가 최소 2개 필요합니다.")

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
        status = self._normalize_status(self.gui.url_status.get(key))
        if status == "processing":
            show_warning(self.gui, "경고", "현재 작업이 진행 중입니다.")
            return

        if key in self.gui.url_queue:
            self.gui.url_queue.remove(key)
        self.gui.url_status.pop(key, None)
        self.gui.url_status_message.pop(key, None)
        self.gui.url_remarks.pop(key, None)
        self._remove_mix_job(key)

        self.update_url_listbox()
        self.update_queue_count()
        self.add_log(f"삭제됨: {display_value[:80]}")

        # Log URL removal
        try:
            from caller.rest import log_user_action
            log_user_action("URL 삭제", f"작업 큐에서 URL 삭제: {display_value[:50]}...")
        except Exception:
            pass

    def clear_url_queue(self):
        if not self.gui.url_queue and not self.gui.url_status:
            return
        if not show_question(
            self.gui,
            "확인",
            "대기열의 모든 링크를 비우시겠습니까? (완료/실패 이력도 삭제됩니다)",
        ):
            return

        processing = [
            url
            for url, status in self.gui.url_status.items()
            if self._normalize_status(status) == "processing"
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
        self.add_log("대기열을 비웠습니다. (진행 중 항목은 유지)")

    def clear_waiting_only(self):
        waiting_urls = [
            url
            for url, status in self.gui.url_status.items()
            if self._normalize_status(status) == "waiting"
        ]
        if not waiting_urls:
            show_info(self.gui, "안내", "대기 중인 링크가 없습니다.")
            return
        if not show_question(self.gui, "확인", "대기 상태 링크만 삭제할까요?"):
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
        self.add_log("대기 중 링크를 삭제했습니다.")

    def clear_completed_only(self):
        """완료된 작업만 삭제"""
        completed_urls = [
            url
            for url, status in self.gui.url_status.items()
            if self._normalize_status(status) == "completed"
        ]
        if not completed_urls:
            show_info(self.gui, "안내", "완료된 작업이 없습니다.")
            return
        if not show_question(self.gui, "확인", f"완료된 작업 {len(completed_urls)}건을 삭제할까요?"):
            return

        for key in completed_urls:
            if key in self.gui.url_queue:
                self.gui.url_queue.remove(key)
            self.gui.url_status.pop(key, None)
            self.gui.url_status_message.pop(key, None)
            self.gui.url_remarks.pop(key, None)
            self._remove_mix_job(key)

        self.update_url_listbox()
        self.update_queue_count()
        self.add_log(f"완료된 작업 {len(completed_urls)}건을 삭제했습니다.")

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

        auto_upload_status = getattr(self.gui, "url_auto_upload_status", {})
        if not auto_upload_status and hasattr(self.gui, "state"):
            auto_upload_status = getattr(self.gui.state, "url_auto_upload_status", {})

        for idx, key in enumerate(self.gui.url_queue, 1):
            status_raw = self.gui.url_status.get(key, "waiting")
            status = self._normalize_status(status_raw)
            if status_raw != status:
                self.gui.url_status[key] = status
            display_url = self._to_display_url(key)
            order_label = "진행" if status == "processing" else "대기"
            order_text = f"{order_label} {idx}"

            if status == "processing":
                step_msg = self.gui.url_status_message.get(key, "")
                status_text = self._localize_status_text(step_msg) if step_msg else "진행 중"
            else:
                status_text = status_labels.get(status, self._localize_status_text(status_raw))

            auto_upload_text = auto_upload_status.get(key, "")
            if not auto_upload_text:
                settings = get_settings_manager()
                if settings.get_youtube_auto_upload() and settings.get_youtube_connected():
                    auto_upload_text = "유튜브"
                else:
                    auto_upload_text = "사용 안 함"
            auto_upload_text = self._localize_upload_status(auto_upload_text)

            remarks_text = ""
            if status == "completed":
                remarks_text = self.gui.url_remarks.get(key, "")
            elif status in ("failed", "skipped"):
                remarks_text = self.gui.url_status_message.get(key, "")

            item = QTreeWidgetItem(
                [order_text, display_url, status_text, auto_upload_text, remarks_text]
            )
            tree.addTopLevelItem(item)

        processed_items = []
        for key, raw_status in self.gui.url_status.items():
            status = self._normalize_status(raw_status)
            if key in self.gui.url_queue or status not in ("completed", "failed", "skipped"):
                continue
            if raw_status != status:
                self.gui.url_status[key] = status
            processed_items.append((key, status))
        for key, status in processed_items:
            display_url = self._to_display_url(key)
            order_text = (
                "완료"
                if status == "completed"
                else "건너뜀" if status == "skipped" else "실패"
            )
            status_text = status_labels.get(status, status)

            auto_upload_text = auto_upload_status.get(key, "")
            if not auto_upload_text and status == "completed":
                settings = get_settings_manager()
                if settings.get_youtube_auto_upload() and settings.get_youtube_connected():
                    auto_upload_text = "유튜브"
                else:
                    auto_upload_text = "사용 안 함"
            elif not auto_upload_text:
                auto_upload_text = "-"
            auto_upload_text = self._localize_upload_status(auto_upload_text)

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
        for raw_status in url_status.values():
            status = self._normalize_status(raw_status)
            if status in counts:
                counts[status] += 1

        count_labels = [
            ("count_processing", f"진행 {counts['processing']}"),
            ("count_waiting", f"대기 {counts['waiting']}"),
            ("count_completed", f"완료 {counts['completed']}"),
            ("count_skipped", f"건너뜀 {counts['skipped']}"),
            ("count_failed", f"실패 {counts['failed']}"),
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
        normalized_status = self._normalize_status(status)
        if url not in self.gui.url_status:
            self.gui.url_status[url] = normalized_status
            self.gui.url_queue.append(url)
        else:
            self.gui.url_status[url] = normalized_status

        if message:
            self.gui.url_status_message[url] = self._localize_status_text(message)
        self.update_url_listbox()

    # ----------------------- URL input helpers -----------------------
    def _enqueue_urls(self, text: str, source_label: str) -> tuple:
        source_label = self._normalize_source_label(source_label)
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
            msg = f"{source_label}에서 링크 {added_count}개를 추가했습니다."
            if duplicate_count > 0:
                msg += f"\n중복 링크 {duplicate_count}개는 제외했습니다."
            show_info(self.gui, "완료", msg)
            self.add_log(f"{source_label}에서 링크 {added_count}개 추가")
            
            # Log URL add
            try:
                from caller.rest import log_user_action
                log_user_action("URL 추가", f"{source_label}에서 {added_count}개의 URL을 추가했습니다.")
            except Exception:
                pass
        elif duplicate_count > 0:
            show_warning(self.gui, "안내", f"입력한 링크가 모두 중복입니다. ({duplicate_count}개)")

        return added_count, duplicate_count

    def add_url_from_entry(self):
        url_entry = getattr(self.gui, "url_entry", None)
        if url_entry is None:
            show_warning(self.gui, "오류", "링크 입력 위젯을 찾을 수 없습니다.")
            return

        text = url_entry.toPlainText().strip()
        if not text:
            show_warning(self.gui, "안내", "링크를 입력해주세요.")
            return

        urls = URL_PATTERN.findall(text)
        if not urls:
            show_warning(self.gui, "안내", "유효한 링크를 찾지 못했습니다.")
            return

        self._enqueue_urls(text, "입력창")
        url_entry.clear()

    def paste_and_extract(self):
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        text = clipboard.text()

        if not text or not text.strip():
            show_warning(self.gui, "안내", "클립보드가 비어 있습니다.")
            return

        urls = URL_PATTERN.findall(text)
        if not urls:
            show_warning(self.gui, "안내", "클립보드에서 유효한 링크를 찾지 못했습니다.")
            return

        self._enqueue_urls(text, "클립보드")

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
