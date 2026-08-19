"""
Queue manager for URL jobs and mix jobs.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from urllib.parse import urlsplit
from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from managers.settings_manager import get_settings_manager
from managers.summer_coupang_queue_status import (
    build_summer_coupang_queue_snapshot,
    delete_summer_coupang_queue_items,
)
from ui.components.custom_dialog import show_info, show_question, show_warning
from utils.logging_config import get_logger
from utils.secrets_manager import get_secrets_manager

logger = get_logger(__name__)

URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")
MIX_JOB_PREFIX = "mix://job/"
LEGACY_QUEUE_PREFIX_PATTERN = re.compile(
    r"^(?:(?:waiting|processing|completed|failed|skipped|done|error|대기|진행|완료|실패|건너뜀)\s+\d+\s+)",
    re.IGNORECASE,
)
ACTIVE_QUEUE_MESSAGE = (
    "이미 대기 중이거나 진행 중인 영상 작업이 있습니다.\n"
    "현재 작업을 완료하거나 진행 상황 화면에서 삭제한 뒤 다시 담아 주세요."
)


class QueueManager:
    """Manages URL queue and mirrors state to a QTreeWidget."""

    def __init__(self, gui):
        self.gui = gui
        self._last_summer_coupang_snapshot = None
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
        # Handle local file entries
        if key.startswith("local://"):
            return f"[로컬] {os.path.basename(key[8:])}"
        if not self._is_mix_job(key):
            return self._strip_legacy_queue_prefix(key)
        mix_urls = self.get_mix_job_urls(key)
        short_id = key.rsplit("/", 1)[-1][:6]
        if mix_urls:
            local_count = sum(1 for u in mix_urls if u.startswith("local://"))
            if local_count == len(mix_urls):
                return f"[로컬 믹스:{short_id}] {len(mix_urls)}개"
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

    @staticmethod
    def _youtube_upload_token_exists() -> bool:
        try:
            if get_secrets_manager().get_credential("youtube_oauth_token_json_v1"):
                return True
        except Exception:
            pass
        return (Path.home() / ".ssmaker" / "youtube_token.json").exists()

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

    def _get_active_queue_keys(self) -> List[str]:
        """Return keys currently waiting/processing in queue/status."""
        active_keys: List[str] = []
        seen = set()

        for key in self.gui.url_queue:
            status = self._normalize_status(self.gui.url_status.get(key))
            if status in ("waiting", "processing"):
                active_keys.append(key)
                seen.add(key)

        for key, raw_status in self.gui.url_status.items():
            if key in seen:
                continue
            status = self._normalize_status(raw_status)
            if status in ("waiting", "processing"):
                active_keys.append(key)

        return active_keys

    def has_active_queue_item(self) -> bool:
        """Whether there is any waiting/processing queue item."""
        return bool(self._get_active_queue_keys())

    @staticmethod
    def _normalize_mix_sources(urls: Sequence[str]) -> List[str]:
        """Validate and de-duplicate user-provided mix sources."""
        if not isinstance(urls, Sequence) or isinstance(urls, (str, bytes)):
            raise ValueError("믹스 영상 목록 형식이 올바르지 않습니다.")

        normalized: List[str] = []
        seen = set()
        for raw_source in urls:
            if not isinstance(raw_source, str) or not raw_source.strip():
                continue

            source = raw_source.strip()
            if source.startswith("local://"):
                raise ValueError(
                    "내 컴퓨터의 영상 파일은 사용할 수 없습니다. 영상 링크만 입력해 주세요."
                )

            parsed = urlsplit(source)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise ValueError(f"올바른 영상 링크가 아닙니다: {source[:80]}")
            identity = ("url", source)

            if identity in seen:
                continue
            seen.add(identity)
            normalized.append(source)

        if len(normalized) > 5:
            raise ValueError("믹스 모드는 영상을 최대 5개까지 사용할 수 있습니다.")
        if len(normalized) < 2:
            raise ValueError("믹스 모드는 서로 다른 영상이 최소 2개 필요합니다.")
        return normalized

    def add_mix_job(self, urls: Sequence[str]) -> str:
        clean_urls = self._normalize_mix_sources(urls)
        if self.has_active_queue_item():
            raise ValueError(ACTIVE_QUEUE_MESSAGE)

        key = f"{MIX_JOB_PREFIX}{uuid4().hex[:12]}"
        self._set_mix_job_urls(key, clean_urls)
        if not self.add_url_to_queue(key):
            self._remove_mix_job(key)
            raise ValueError("믹스 작업을 목록에 추가하지 못했습니다.")
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
        if self.has_active_queue_item():
            logger.info("[Queue] Reject enqueue while active item exists: %s", key)
            return False

        self.gui.url_queue.append(key)
        self.gui.url_status[key] = "waiting"
        if hasattr(self.gui, "url_timestamps"):
            self.gui.url_timestamps[key] = datetime.now()

        self.update_url_listbox()
        self.update_queue_count()
        return True

    def _delete_local_keys(self, keys: Iterable[str]) -> int:
        deleted = 0
        for key in set(keys):
            existed = key in self.gui.url_queue or key in self.gui.url_status
            while key in self.gui.url_queue:
                self.gui.url_queue.remove(key)
            for attr in (
                "url_status",
                "url_status_message",
                "url_remarks",
                "url_timestamps",
                "url_auto_upload_status",
            ):
                store = getattr(self.gui, attr, None)
                if isinstance(store, dict):
                    store.pop(key, None)
            self._remove_mix_job(key)
            if existed:
                deleted += 1
        return deleted

    def _save_queue_session(self) -> None:
        manager = getattr(self.gui, "session_manager", None)
        save = getattr(manager, "save_session", None)
        if callable(save):
            try:
                save(force=True)
            except Exception as exc:
                logger.warning("[Queue] Failed to persist deletion: %s", exc)

    def _show_delete_feedback(self, message: str) -> None:
        panel = getattr(self.gui, "queue_panel", None)
        show_feedback = getattr(panel, "show_delete_feedback", None)
        if callable(show_feedback):
            show_feedback(message)
        else:
            show_info(self.gui, "삭제 완료", message)

    def _delete_scheduled(self, scope: str, selected_ids=None) -> Dict[str, object]:
        result = delete_summer_coupang_queue_items(
            scope,
            selected_ids=selected_ids,
        )
        if result.get("busy"):
            show_warning(
                self.gui,
                "삭제할 수 없음",
                "풀자동 작업이 실행 중입니다. 작업이 끝난 뒤 다시 삭제해 주세요.",
            )
        return result

    def _finish_delete(self, deleted: int, message: str) -> None:
        self._last_summer_coupang_snapshot = None
        self._save_queue_session()
        self.update_url_listbox()
        self.add_log(message)
        self._show_delete_feedback(message)

    def remove_selected_url(self):
        tree: QTreeWidget = getattr(self.gui, "url_listbox", None)
        if tree is None:
            return

        selected = tree.selectedItems()
        if not selected:
            show_info(self.gui, "선택 필요", "삭제할 항목을 먼저 선택해 주세요.")
            return

        local_keys = []
        scheduled_ids = []
        processing_count = 0
        for item in selected:
            metadata = item.data(0, Qt.ItemDataRole.UserRole)
            metadata = metadata if isinstance(metadata, dict) else {}
            source = metadata.get("source")
            status = self._normalize_status(metadata.get("status"))
            if status == "processing":
                processing_count += 1
                continue
            if source == "scheduled" and metadata.get("id"):
                scheduled_ids.append(str(metadata["id"]))
            elif source == "local" and metadata.get("key"):
                local_keys.append(str(metadata["key"]))
            else:
                display_value = item.text(1)
                key = self._find_queue_key_by_display(display_value)
                if key in self.gui.url_queue or key in self.gui.url_status:
                    local_keys.append(key)

        delete_count = len(set(local_keys)) + len(set(scheduled_ids))
        if not delete_count:
            if processing_count:
                show_warning(self.gui, "삭제할 수 없음", "진행 중인 작업은 삭제할 수 없습니다.")
            else:
                show_info(self.gui, "선택 필요", "삭제 가능한 항목을 선택해 주세요.")
            return
        processing_note = f" 진행 중 {processing_count}건은 유지됩니다." if processing_count else ""
        if not show_question(
            self.gui,
            "선택 항목 삭제",
            f"선택한 항목 {delete_count}건을 삭제할까요?{processing_note}",
        ):
            return

        scheduled_result = (
            self._delete_scheduled("selected", scheduled_ids)
            if scheduled_ids
            else {"deleted": 0, "busy": False}
        )
        if scheduled_result.get("busy"):
            return
        deleted = self._delete_local_keys(local_keys) + int(scheduled_result.get("deleted", 0))
        if not deleted:
            show_info(self.gui, "안내", "선택한 항목은 이미 삭제되었거나 찾을 수 없습니다.")
            self.update_url_listbox()
            return

        message = f"선택한 항목 {deleted}건을 삭제했습니다."
        self._finish_delete(deleted, message)

        try:
            from caller.rest import log_user_action

            log_user_action("URL 삭제", f"작업 큐에서 선택 항목 {deleted}건 삭제")
        except Exception:
            pass

    def clear_url_queue(self):
        snapshot = build_summer_coupang_queue_snapshot()
        local_keys = set(self.gui.url_queue).union(self.gui.url_status.keys())
        local_deletable = [
            key
            for key in local_keys
            if self._normalize_status(self.gui.url_status.get(key)) != "processing"
        ]
        scheduled_counts = snapshot.get("counts", {})
        scheduled_deletable = int(snapshot.get("total", 0)) - int(
            scheduled_counts.get("processing", 0)
        )
        total = len(set(local_deletable)) + max(0, scheduled_deletable)
        if not total:
            show_info(self.gui, "안내", "삭제할 대기열 항목이 없습니다.")
            return

        processing_count = sum(
            1
            for status in self.gui.url_status.values()
            if self._normalize_status(status) == "processing"
        ) + int(scheduled_counts.get("processing", 0))
        processing_note = f" 진행 중 {processing_count}건은 유지됩니다." if processing_count else ""
        if not show_question(
            self.gui,
            "전체 삭제",
            f"삭제 가능한 대기열 {total}건을 모두 삭제할까요?{processing_note}",
        ):
            return

        scheduled_result = (
            self._delete_scheduled("all")
            if scheduled_deletable
            else {"deleted": 0, "busy": False}
        )
        if scheduled_result.get("busy"):
            return
        deleted = self._delete_local_keys(local_deletable) + int(
            scheduled_result.get("deleted", 0)
        )
        if hasattr(self.gui, "generated_videos"):
            self.gui.generated_videos = []
        message = f"대기열 {deleted}건을 삭제했습니다."
        if processing_count:
            message += f" 진행 중 {processing_count}건은 유지했습니다."
        self._finish_delete(deleted, message)

    def clear_waiting_only(self):
        local_keys = set(self.gui.url_queue).union(self.gui.url_status.keys())
        waiting_urls = [
            key
            for key in local_keys
            if self._normalize_status(self.gui.url_status.get(key)) == "waiting"
        ]
        snapshot = build_summer_coupang_queue_snapshot()
        scheduled_count = int(snapshot.get("counts", {}).get("waiting", 0))
        total = len(set(waiting_urls)) + scheduled_count
        if not total:
            show_info(self.gui, "안내", "대기 중인 작업이 없습니다.")
            return
        if not show_question(self.gui, "대기 작업 삭제", f"대기 중인 작업 {total}건을 삭제할까요?"):
            return

        scheduled_result = (
            self._delete_scheduled("waiting")
            if scheduled_count
            else {"deleted": 0, "busy": False}
        )
        if scheduled_result.get("busy"):
            return
        deleted = self._delete_local_keys(waiting_urls) + int(
            scheduled_result.get("deleted", 0)
        )
        self._finish_delete(deleted, f"대기 중인 작업 {deleted}건을 삭제했습니다.")

    def clear_completed_only(self):
        completed_urls = [
            url
            for url, status in self.gui.url_status.items()
            if self._normalize_status(status) == "completed"
        ]
        snapshot = build_summer_coupang_queue_snapshot()
        scheduled_count = int(snapshot.get("counts", {}).get("completed", 0))
        total = len(set(completed_urls)) + scheduled_count
        if not total:
            show_info(self.gui, "안내", "완료된 작업이 없습니다.")
            return
        if not show_question(self.gui, "완료 이력 삭제", f"완료된 작업 {total}건을 삭제할까요?"):
            return

        scheduled_result = (
            self._delete_scheduled("completed")
            if scheduled_count
            else {"deleted": 0, "busy": False}
        )
        if scheduled_result.get("busy"):
            return
        deleted = self._delete_local_keys(completed_urls) + int(
            scheduled_result.get("deleted", 0)
        )
        self._finish_delete(deleted, f"완료된 작업 {deleted}건을 삭제했습니다.")

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
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"source": "local", "key": key, "status": status},
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
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"source": "local", "key": key, "status": status},
            )
            tree.addTopLevelItem(item)

        summer_snapshot = build_summer_coupang_queue_snapshot()
        self._last_summer_coupang_snapshot = summer_snapshot
        for row in summer_snapshot.get("rows", []):
            item = QTreeWidgetItem(
                [
                    str(row.get("order", "")),
                    str(row.get("url", "")),
                    str(row.get("status", "")),
                    str(row.get("upload", "")),
                    str(row.get("remarks", "")),
                ]
            )
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "source": "scheduled",
                    "id": str(row.get("queue_item_id", "")),
                    "status": str(row.get("bucket", "waiting")),
                },
            )
            tree.addTopLevelItem(item)

        keep = set(self.gui.url_queue).union(self.gui.url_status.keys())
        self._prune_mix_jobs(keep)
        self.update_queue_count()
        panel = getattr(self.gui, "queue_panel", None)
        sync_controls = getattr(panel, "sync_delete_controls", None)
        if callable(sync_controls):
            sync_controls(summer_snapshot)

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

        summer_snapshot = getattr(self, "_last_summer_coupang_snapshot", None)
        if summer_snapshot is None:
            summer_snapshot = build_summer_coupang_queue_snapshot()
            self._last_summer_coupang_snapshot = summer_snapshot

        summer_counts = summer_snapshot.get("counts", {}) if isinstance(summer_snapshot, dict) else {}
        counts["processing"] += int(summer_counts.get("processing", 0) or 0)
        counts["waiting"] += int(summer_counts.get("waiting", 0) or 0)
        counts["completed"] += int(summer_counts.get("completed", 0) or 0)
        counts["skipped"] += int(summer_counts.get("skipped", 0) or 0)
        counts["failed"] += int(summer_counts.get("failed", 0) or 0)
        self._update_summer_coupang_status_labels(summer_snapshot)

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

        total = sum(counts.values())
        completed = counts["completed"]
        overall_label = getattr(self.gui, "overall_numeric_label", None)
        if overall_label is not None:
            percent = (completed / total * 100) if total else 0
            overall_label.setText(f"{completed}/{total} ({percent:.0f}%)")

        witty_label = getattr(self.gui, "overall_witty_label", None)
        if witty_label is not None and isinstance(summer_snapshot, dict) and summer_snapshot.get("total"):
            next_time = summer_snapshot.get("next_scheduled_display") or "-"
            interval = int(summer_snapshot.get("interval_minutes") or 0)
            interval_text = f"{interval // 60}시간" if interval and interval % 60 == 0 else f"{interval}분"
            witty_label.setText(f"풀자동화 {completed}/{total} 처리 / {interval_text} 간격 / 다음 {next_time}")

    def _update_summer_coupang_status_labels(self, snapshot):
        if not self.gui or not isinstance(snapshot, dict):
            return

        counts = snapshot.get("counts", {}) if isinstance(snapshot.get("counts"), dict) else {}
        total = int(snapshot.get("total") or 0)
        completed = int(counts.get("completed", 0) or 0)
        waiting = int(counts.get("waiting", 0) or 0)
        next_time = snapshot.get("next_scheduled_display") or "-"
        next_number = snapshot.get("next_planned_number") or ""
        interval = int(snapshot.get("interval_minutes") or 0)
        if interval and interval % 60 == 0:
            interval_text = f"{interval // 60}시간 간격"
        elif interval:
            interval_text = f"{interval}분 간격"
        else:
            interval_text = "확인 중"

        labels = {
            "summer_status_interval": f"자동 업로드\n{interval_text}",
            "summer_status_queue": f"작업 큐\n{completed}/{total} 완료, {waiting} 대기",
            "summer_status_next": f"다음 업로드\n{next_number} {next_time}".strip(),
        }

        try:
            settings = get_settings_manager()
            yt_connected = bool(settings.get_youtube_connected())
            channel = (settings.get_youtube_channel_info() or {}).get("channel_name") or ""
            if yt_connected and self._youtube_upload_token_exists():
                youtube_text = f"YouTube\n연결됨 {channel}".strip()
            else:
                youtube_text = "YouTube\n업로드 권한 만료"
            labels["summer_status_youtube"] = youtube_text
        except Exception:
            labels["summer_status_youtube"] = "YouTube\n확인 실패"

        for attr, text in labels.items():
            label = getattr(self.gui, attr, None)
            if label is not None:
                label.setText(text)

    def update_queue_status(self, url: str, status: str, message: str = ""):
        normalized_status = self._normalize_status(status)
        if url not in self.gui.url_status:
            # 1-link policy: block new entries when an active item exists
            if normalized_status in ("waiting", "processing") and self.has_active_queue_item():
                logger.info("[Queue] update_queue_status: reject new URL while active item exists: %s", url[:80])
                return
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
        if self.has_active_queue_item():
            show_warning(
                self.gui,
                "목록에 담지 못했어요",
                ACTIVE_QUEUE_MESSAGE,
            )
            return 0, 0

        added_count = 0
        duplicate_count = 0
        ignored_count = 0
        first_candidate = None

        for raw_url in urls:
            url = raw_url.strip()
            if not url:
                continue
            if url in self.gui.url_queue or url in self.gui.url_status:
                duplicate_count += 1
                continue
            if first_candidate is None:
                first_candidate = url
            else:
                ignored_count += 1

        if first_candidate and self.add_url_to_queue(first_candidate):
            added_count = 1
        elif first_candidate:
            ignored_count += 1

        if added_count > 0:
            msg = f"{source_label}에서 링크 {added_count}개를 추가했습니다."
            if ignored_count > 0:
                msg += (
                    f"\n단일 영상 모드는 첫 번째 링크만 담습니다. "
                    f"나머지 링크 {ignored_count}개는 제외했습니다."
                )
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
            msg = f"입력한 링크가 모두 중복입니다. ({duplicate_count}개)"
            if ignored_count > 0:
                msg += f"\n함께 입력한 다른 링크 {ignored_count}개는 제외했습니다."
            show_warning(self.gui, "안내", msg)

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
