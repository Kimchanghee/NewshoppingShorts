"""
Batch Processing Handler

This module handles batch processing control logic, extracted from main.py.
"""

import threading
import time
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer
from ui.components.custom_dialog import (
    show_warning,
    show_info,
    show_error,
    show_question,
)
import core.video.DynamicBatch as DynamicBatch
from utils.logging_config import get_logger
from user_facing_errors import (
    friendly_error_message,
    friendly_error_title,
    looks_developer_facing,
    sanitize_user_message,
)
from caller import rest
from ui.design_system_v2 import get_design_system, get_color
import config
from utils.secrets_manager import SecretsManager
from managers.summer_coupang_queue_status import build_summer_coupang_queue_snapshot

logger = get_logger(__name__)

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI


class BatchHandler:
    """Handles batch processing start/stop logic"""

    def __init__(self, app: "VideoAnalyzerGUI"):
        self.app = app

    @staticmethod
    def _key_exists(value: str) -> bool:
        return bool(isinstance(value, str) and value.strip())

    def _has_valid_api_key(self) -> bool:
        """Return True when at least one usable Gemini API key exists."""
        try:
            # 1) In-memory config keys
            cfg = getattr(config, "GEMINI_API_KEYS", {}) or {}
            if isinstance(cfg, dict) and any(self._key_exists(v) for v in cfg.values()):
                return True

            # 2) API key manager snapshot
            mgr = getattr(self.app, "api_key_manager", None)
            mgr_keys = getattr(mgr, "api_keys", None) if mgr else None
            if isinstance(mgr_keys, dict) and any(self._key_exists(v) for v in mgr_keys.values()):
                return True

            # 3) Secure storage fallback
            for i in range(1, 9):
                key = SecretsManager.get_api_key(f"gemini_api_{i}")
                if self._key_exists(key):
                    return True
            if self._key_exists(SecretsManager.get_api_key("gemini")):
                return True
        except Exception as e:
            logger.debug("[BatchHandler] API 키 확인 중 예외: %s", e)
        return False

    @staticmethod
    def _short_detail(text: str, limit: int = 260) -> str:
        detail = " ".join(str(text or "").split())
        if len(detail) <= limit:
            return detail
        return detail[: limit - 1].rstrip() + "…"

    @staticmethod
    def _progress_status_for_level(level: str) -> str:
        return {
            "active": "active",
            "success": "completed",
            "warning": "error",
            "error": "error",
            "idle": "idle",
        }.get(level, "active")

    def _set_run_status(self, title: str, detail: str = "", level: str = "info") -> None:
        """Keep the queue/progress UI explicit about what Start actually did."""
        safe_title = (
            friendly_error_title(title)
            if looks_developer_facing(title)
            else str(title or "상태 확인 중").strip()
        )
        safe_detail = self._short_detail(
            sanitize_user_message(detail, fallback="잠시 문제가 생겼어요. 다시 시도해 주세요.")
        )

        def apply_status():
            try:
                color_key_by_level = {
                    "active": "warning",
                    "success": "success",
                    "warning": "warning",
                    "error": "error",
                    "idle": "text_muted",
                    "info": "primary",
                }
                accent = get_color(color_key_by_level.get(level, "primary"))
            except Exception:
                accent = "#E31639"

            status_label = getattr(self.app, "start_run_status_label", None)
            if status_label is not None:
                status_label.setText(safe_title)
                status_label.setStyleSheet(
                    f"color: {accent};"
                    "border: none;"
                    "font-size: 13px;"
                    "font-weight: 700;"
                    "padding: 2px 0 0 0;"
                )

            detail_label = getattr(self.app, "start_run_detail_label", None)
            if detail_label is not None:
                try:
                    detail_color = get_color("text_secondary")
                except Exception:
                    detail_color = "#B8B8B8"
                detail_label.setText(safe_detail or "상세 상태를 확인하는 중입니다.")
                detail_label.setStyleSheet(
                    f"color: {detail_color};"
                    "border: none;"
                    "font-size: 12px;"
                    "padding: 0 0 6px 0;"
                )

            task_label = getattr(self.app, "current_task_label", None)
            progress_panel = getattr(self.app, "progress_panel", None)
            if progress_panel is not None and hasattr(progress_panel, "set_current_task"):
                progress_panel.set_current_task(
                    self._short_detail(safe_title, limit=80),
                    status=self._progress_status_for_level(level),
                )
            elif task_label is not None:
                task_label.setText(self._short_detail(safe_title, limit=80))

            witty_label = getattr(self.app, "overall_witty_label", None)
            if witty_label is not None and safe_detail:
                witty_label.setText(safe_detail)

        self._dispatch_ui_callback(apply_status)

    @staticmethod
    def _format_alias_list(values) -> str:
        if not values:
            return ""
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        return ", ".join(str(v) for v in values if str(v).strip())

    @staticmethod
    def _set_button_text(button, text: str) -> None:
        if button is None or not hasattr(button, "setText"):
            return
        try:
            button.setText(text)
        except Exception:
            return

    def _summer_run_result_status(self, summary: dict, elapsed_seconds: float, returncode: int):
        reason = str(summary.get("reason") or "").strip()
        status = str(summary.get("status") or "").strip()
        blocking = str(summary.get("blocking_reason") or summary.get("error") or "").strip()
        planned = (
            summary.get("planned_number")
            or summary.get("next_planned_number")
            or "-"
        )
        elapsed = f"{elapsed_seconds:.0f}초"
        code_suffix = f" 종료코드 {returncode}." if returncode else ""

        if status == "completed":
            youtube_url = str(summary.get("youtube_url") or "").strip()
            linktree_ok = bool(summary.get("linktree_ok"))
            detail = f"{planned}번 처리 완료. YouTube 업로드 완료"
            detail += ", Linktree 등록 완료." if linktree_ok else "."
            if youtube_url:
                detail += f" YouTube: {youtube_url}"
            detail += f" 소요 {elapsed}."
            return "작업 완료", detail, "success"

        if reason in {"gemini_api_keys_missing", "gemini_api_keys_rejected"}:
            parts = []
            if summary.get("popup_launched"):
                parts.append("안내 창을 열어 두었어요.")
            elif summary.get("popup_throttled"):
                parts.append("중복 안내 창은 생략했어요.")
            detail = friendly_error_message(summary)
            if parts:
                detail += "\n" + " ".join(parts)
            detail += f"\n확인 시간: {elapsed}."
            return friendly_error_title(summary), f"{detail}{code_suffix}", "error"

        reason_titles = {
            "youtube_not_connected": "YouTube 업로드 권한 만료",
            "youtube_account_verification_failed": "YouTube 계정 확인 실패",
            "linktree_not_connected": "Linktree 연결 필요",
            "linktree_preflight_error": "Linktree 확인 실패",
            "affiliate_link_missing": "제휴 링크 필요",
            "no_due_items": "예약 시간 전",
            "no_pending_items": "대기 항목 없음",
            "another_run_in_progress": "이미 실행 중",
            "all_pending_items_skipped_low_similarity": "처리 가능한 항목 없음",
            "all_candidate_items_skipped": "후보 항목 건너뜀",
        }
        title = reason_titles.get(reason) or reason_titles.get(str(summary.get("blocking_type") or ""))
        if title:
            detail_source = summary if reason == "youtube_not_connected" else (blocking or reason)
            detail = sanitize_user_message(
                detail_source,
                fallback="현재 상태를 확인해 주세요.",
            )
            pending = summary.get("pending_count")
            next_at = summary.get("next_scheduled_at") or summary.get("scheduler_next_run")
            if pending is not None:
                detail = f"{detail} 대기 {pending}건."
            if next_at:
                detail = f"{detail} 다음 예약 {next_at}."
            level = (
                "warning"
                if reason in {"no_due_items", "no_pending_items", "another_run_in_progress"}
                else "error"
            )
            if reason == "youtube_not_connected":
                return title, detail, level
            return title, f"{detail}{code_suffix} 소요 {elapsed}.", level

        if status:
            level = "success" if returncode == 0 else "warning"
            detail = sanitize_user_message(
                blocking or reason or f"{planned}번 작업 상태: {status}",
                fallback="실행 결과를 확인해 주세요.",
            )
            return "실행 결과 확인", f"{detail}{code_suffix} 소요 {elapsed}.", level

        detail = sanitize_user_message(
            blocking or reason or "실행 결과가 돌아왔지만 처리 상태를 분류하지 못했어요.",
            fallback="실행 결과를 확인해 주세요.",
        )
        level = "success" if returncode == 0 else "error"
        return "실행 결과 확인", f"{detail}{code_suffix} 소요 {elapsed}.", level

    def _start_summer_coupang_queue_now(self) -> bool:
        """Run the visible Summer Coupang queue when the normal URL queue is empty."""
        try:
            snapshot = build_summer_coupang_queue_snapshot()
            counts = snapshot.get("counts", {}) if isinstance(snapshot, dict) else {}
            waiting_count = int(counts.get("waiting", 0) or 0)
        except Exception as exc:
            logger.warning("[BatchHandler] Summer Coupang queue check failed: %s", exc)
            self._set_run_status(
                "큐 확인 실패",
                f"Summer Coupang 큐 파일을 읽지 못했습니다: {exc}",
                "error",
            )
            return False

        if waiting_count <= 0:
            self._set_run_status(
                "실행할 항목 없음",
                "일반 URL 큐와 Summer Coupang 대기 항목이 모두 비어 있습니다.",
                "warning",
            )
            return False

        existing_thread = getattr(self.app, "batch_thread", None)
        if existing_thread and existing_thread.is_alive():
            self._set_run_status(
                "이미 실행 중",
                "이전 작업 스레드가 아직 살아 있습니다. 완료되거나 중지된 뒤 다시 시작할 수 있습니다.",
                "warning",
            )
            show_warning(self.app, "경고", "이미 작업이 진행 중입니다.")
            return True

        self.app.batch_processing = True
        self.app.dynamic_processing = False
        next_number = snapshot.get("next_planned_number") or "-"
        next_time = snapshot.get("next_scheduled_display") or "즉시"
        self._set_run_status(
            "실행 요청됨",
            f"Summer Coupang {next_number}번 상품을 즉시 실행합니다. 대기 {waiting_count}건, 기준 예약 {next_time}.",
            "active",
        )
        self.app.add_log(
            f"[Summer Coupang] 예약 큐 {waiting_count}건 감지 - 첫 대기 상품을 즉시 실행합니다."
        )

        start_btn = getattr(self.app, "start_batch_button", None)
        stop_btn = getattr(self.app, "stop_batch_button", None)
        if start_btn is not None:
            self._reset_start_button_style(start_btn)
            self._set_button_text(start_btn, "실행 중...")
            start_btn.setEnabled(False)
        if stop_btn is not None:
            stop_btn.setEnabled(False)

        thread = threading.Thread(
            target=self._summer_coupang_queue_now_wrapper,
            daemon=True,
        )
        self.app.batch_thread = thread
        thread.start()
        return True

    def _summer_coupang_queue_now_wrapper(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_summer_coupang_queue_once.py"
        command = [sys.executable, str(script), "--run-now"]
        env = os.environ.copy()
        env["SSMAKER_LINKTREE_BROWSER_PUBLISH"] = "1"
        env["SSMAKER_LINKTREE_CLOSE_TAB_AFTER_VERIFY"] = "1"
        started_at = time.monotonic()
        self._set_run_status(
            "실행 중",
            "Summer Coupang 백그라운드 러너가 실제로 시작됐습니다. run_summer_coupang_queue_once.py --run-now 실행 중.",
            "active",
        )
        try:
            completed = subprocess.run(
                command,
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=60 * 60,
            )
            output = (completed.stdout or "").strip()
            summary = self._extract_json_summary(output)
            elapsed = time.monotonic() - started_at
            if summary:
                planned = summary.get("planned_number") or "-"
                status = summary.get("status") or summary.get("reason") or "-"
                youtube_url = summary.get("youtube_url") or ""
                self.app.add_log(f"[Summer Coupang] 즉시 실행 완료: {planned} / {status}")
                if youtube_url:
                    self.app.add_log(f"[Summer Coupang] YouTube: {youtube_url}")
                title, detail, level = self._summer_run_result_status(
                    summary,
                    elapsed,
                    completed.returncode,
                )
                self._set_run_status(title, detail, level)
            else:
                tail = output[-800:] if output else (completed.stderr or "")[-800:]
                self.app.add_log(f"[Summer Coupang] 즉시 실행 결과: {tail}")
                self._set_run_status(
                    "실행 결과 확인 필요",
                    f"러너 요약 JSON을 찾지 못했습니다. {tail}",
                    "warning" if completed.returncode == 0 else "error",
                )

            if completed.returncode != 0:
                self.app.add_log(
                    f"[Summer Coupang] 즉시 실행 종료 코드 {completed.returncode}: "
                    f"{(completed.stderr or '').strip()[-800:]}"
                )
        except subprocess.TimeoutExpired:
            self.app.add_log("[Summer Coupang] 즉시 실행이 60분을 초과해 중단되었습니다.")
            self._set_run_status(
                "실행 시간 초과",
                "Summer Coupang 러너가 60분 안에 끝나지 않아 중단되었습니다.",
                "error",
            )
            logger.warning("[BatchHandler] Summer Coupang run-now timed out")
        except Exception as exc:
            self.app.add_log(f"[Summer Coupang] 즉시 실행 실패: {exc}")
            self._set_run_status(
                "실행 실패",
                f"Summer Coupang 러너를 시작하거나 완료 처리하는 중 오류가 났습니다: {exc}",
                "error",
            )
            logger.error("[BatchHandler] Summer Coupang run-now failed: %s", exc, exc_info=True)
        finally:
            self._dispatch_ui_callback(self._reset_summer_coupang_manual_ui)

    def _dispatch_ui_callback(self, callback) -> None:
        signal = getattr(self.app, "ui_callback_signal", None)
        if signal is not None:
            try:
                signal.emit(callback)
                return
            except Exception as exc:
                logger.debug("[BatchHandler] ui_callback_signal dispatch failed: %s", exc)
        QTimer.singleShot(0, callback)

    @staticmethod
    def _extract_json_summary(output: str):
        text = (output or "").strip()
        if not text:
            return {}
        start = text.rfind("\n{")
        if start >= 0:
            text = text[start + 1 :]
        else:
            start = text.find("{")
            if start > 0:
                text = text[start:]
        try:
            return json.loads(text)
        except Exception:
            return {}

    def _reset_summer_coupang_manual_ui(self) -> None:
        self.app.batch_processing = False
        self.app.dynamic_processing = False
        start_btn = getattr(self.app, "start_batch_button", None)
        if start_btn is not None:
            start_btn.setEnabled(True)
            self._set_button_text(start_btn, "▶ 작업 시작")
            self._reset_start_button_style(start_btn)
        try:
            if hasattr(self.app, "update_url_listbox"):
                self.app.update_url_listbox()
            elif getattr(self.app, "queue_manager", None) is not None:
                self.app.queue_manager.update_url_listbox()
        except Exception as exc:
            logger.warning("[BatchHandler] Summer Coupang UI refresh failed: %s", exc)

    def start_batch_processing(self):
        """배치 처리 시작 - 동적 URL 처리 지원 (중복 실행 방지)"""
        # 이미 실행 중인 스레드가 있는지 확인
        if self.app.batch_thread and self.app.batch_thread.is_alive():
            self.app.add_log("이미 작업이 진행 중입니다. 기다려주세요.")
            self._set_run_status(
                "이미 실행 중",
                "이전 작업 스레드가 아직 끝나지 않았습니다. 완료 또는 중지 처리 후 다시 시작할 수 있습니다.",
                "warning",
            )
            show_warning(self.app, "경고", "이미 작업이 진행 중입니다.")
            return

        if not self.app.url_queue:
            if self._start_summer_coupang_queue_now():
                return
            self._set_run_status(
                "실행할 항목 없음",
                "일반 URL 큐와 Summer Coupang 대기 항목이 모두 비어 있습니다.",
                "warning",
            )
            show_warning(self.app, "경고", "처리할 URL이 없습니다.")
            return

        # 대기 중인 URL만 처리 (thread-safe access)
        with self.app.url_status_lock:
            waiting_urls = [
                url
                for url in self.app.url_queue
                if self.app.url_status.get(url) == "waiting"
            ]

        if not waiting_urls:
            self._set_run_status(
                "대기 URL 없음",
                "URL 목록은 있지만 처리 상태가 '대기'인 항목이 없습니다.",
                "warning",
            )
            show_info(self.app, "알림", "처리할 대기 중인 URL이 없습니다.")
            return

        # TTS 음성 선택 검증 - 실제 선택된 음성 체크
        selected_voices = [
            vid for vid, selected in self.app.voice_vars.items() if selected
        ]
        if not selected_voices or len(selected_voices) == 0:
            self._set_run_status(
                "TTS 음성 필요",
                "작업을 시작하려면 TTS 음성을 최소 1개 이상 선택해야 합니다.",
                "warning",
            )
            show_warning(
                self.app, "경고", "TTS 음성을 최소 1개 이상 선택해주세요."
            )
            return

        # 선택된 음성 확인 로그 (명확한 표시)
        voice_manager = getattr(self.app, "voice_manager", None)
        voice_labels = []
        for vid in selected_voices:
            if voice_manager:
                profile = voice_manager.get_voice_profile(vid)
                if profile:
                    gender = "👩" if profile.get("gender") == "female" else "👨"
                    voice_labels.append(f"{gender}{profile.get('label', vid)}")
                    continue
            voice_labels.append(vid)

        self.app.add_log(
            f"[음성 확인] 선택된 음성 {len(selected_voices)}개: {', '.join(voice_labels)}"
        )
        self.app.add_log(
            f"[음성 확인] 각 URL당 {len(selected_voices)}개의 영상이 생성됩니다."
        )

        # API 키 검증 - 먼저 체크 (빈 dict, None, 또는 모든 값이 빈 문자열인 경우 체크)
        if not self._has_valid_api_key():
            self.app.add_log("[API] API 키가 설정되지 않았습니다.")
            self._set_run_status(
                "API 키 필요",
                "저장된 Gemini API 키가 없습니다. 설정 > API 키에서 최소 1개를 저장해야 작업을 시작할 수 있습니다.",
                "error",
            )
            show_warning(
                self.app,
                "API KEY 필요",
                "API KEY를 먼저 저장해주세요.\n\n"
                "작업을 시작하려면 최소 1개 이상의 API 키가 필요합니다.\n"
                "확인을 누르면 설정 > API 키 화면으로 이동합니다.",
            )
            if hasattr(self.app, "open_api_key_settings"):
                self.app.open_api_key_settings()
            elif hasattr(self.app, "_on_step_selected"):
                self.app._on_step_selected("settings")
            return

        # 작업 횟수 확인 (Work count check)
        try:
            login_data = self.app.login_data
            if not login_data or not isinstance(login_data, dict):
                logger.warning("[BatchHandler] No login_data, skipping work count check")
                user_id = ""
            else:
                user_id = login_data.get("data", {}).get("data", {}).get("id", "")
            if user_id:
                work_check = rest.checkWorkAvailable(user_id)
                if not work_check.get("success") and work_check.get("message") == "No auth token":
                    self.app.add_log("[로그인] 인증 토큰이 없습니다. 다시 로그인해주세요.")
                    show_warning(
                        self.app,
                        "로그인 필요",
                        "인증 토큰이 없거나 만료되었습니다.\n\n"
                        "프로그램을 재시작한 뒤 다시 로그인해주세요.",
                    )
                    return
                if work_check.get("success"):
                    work_count = work_check.get("work_count", -1)
                    work_used = work_check.get("work_used", 0)
                    remaining = work_check.get("remaining", -1)

                    # 체험판 사용자 확인 (user_type == "trial")
                    is_trial_user = (
                        self.app.login_data.get("data", {})
                        .get("data", {})
                        .get("user_type", "")
                        == "trial"
                    )
                    effective_is_trial_user = is_trial_user

                    if remaining != -1 and remaining <= 0:
                        # Double-check via subscription status API (handles auto-heal on server)
                        try:
                            sub_status = rest.getSubscriptionStatus(str(user_id))
                            if sub_status.get("success"):
                                effective_is_trial_user = bool(
                                    sub_status.get("is_trial", is_trial_user)
                                )
                                # If subscription status says can_work, trust it (server may have auto-healed)
                                if sub_status.get("can_work"):
                                    self.app.add_log("[구독] 구독 활성 상태 확인됨. 작업을 계속합니다.")
                                    remaining = -1  # treat as unlimited so we don't block below
                                elif sub_status.get("has_pending_request"):
                                    self.app.add_log("[구독] 구독 신청이 이미 접수되어 승인 대기 중입니다.")
                                    show_warning(
                                        self.app,
                                        "구독 승인 대기",
                                        "구독 신청이 이미 접수되어 승인 대기 중입니다.\n\n"
                                        "관리자 승인 후 자동으로 사용 가능해집니다.\n"
                                        "잠시 후 다시 시도하거나 앱을 재시작해 주세요.",
                                    )
                                    return
                        except Exception:
                            pass

                    if remaining != -1 and remaining <= 0:

                        if effective_is_trial_user:
                            # 체험판 사용자: 구독 신청 다이얼로그 표시
                            self.app.add_log("[작업] 체험판 사용량 소진. 구독 신청 안내.")

                            # Run dialog in main thread
                            def show_sub_dialog():
                                try:
                                    from ui.components.subscription_dialog import SubscriptionDialog
                                    dialog = SubscriptionDialog(self.app, user_id, work_used, work_count)
                                    dialog.exec()
                                except Exception as e:
                                    logger.error(f"Failed to show subscription dialog: {e}")
                                    show_warning(self.app, "오류", f"구독 신청 창을 열 수 없습니다: {e}")

                            QTimer.singleShot(0, show_sub_dialog)
                        else:
                            # 유료 사용자(또는 관리자 계정 등): 일반 초과 알림
                            self.app.add_log("[작업] 잔여 작업 횟수가 없습니다.")
                            show_warning(
                                self.app,
                                "작업 횟수 초과",
                                "잔여 작업 횟수가 없습니다.\n\n"
                                "구독이 활성화되어 있다면 구독 상태를 새로고침하거나 앱을 재시작해 주세요.\n"
                                "문제가 지속되면 관리자에게 문의해 주세요.",
                            )
                        return
                    if remaining != -1:
                        self.app.add_log(f"[작업] 잔여 무료 횟수: {remaining}회")
                    else:
                        self.app.add_log("[작업] 무료 횟수: 무제한")
        except Exception as e:
            logger.warning(f"Work count check failed (continuing): {e}")
            # 체크 실패 시 계속 진행 (네트워크 오류 등)

        # Gemini 클라이언트 초기화
        if not getattr(self.app, "genai_client", None):
            self.app.add_log("[API] Gemini 클라이언트를 초기화합니다.")
            if not self.app.init_client():
                self.app.add_log("API 연결 실패로 작업을 중단합니다.")
                self._set_run_status(
                    "API 초기화 실패",
                    "Gemini 클라이언트 초기화에 실패했습니다. 저장된 키가 실제로 유효한지 확인해야 합니다.",
                    "error",
                )
                show_error(
                    self.app,
                    "❌ API 초기화 실패",
                    "Gemini API 클라이언트 초기화에 실패했습니다.\n\n"
                    "가능한 원인:\n"
                    "• API 키가 유효하지 않음\n"
                    "• 네트워크 연결 문제\n"
                    "• Gemini SDK 설치 오류\n\n"
                    "API 키 설정을 확인해주세요.",
                )
                return

        self.app.add_log(f"영상 만들기 시작 - {len(waiting_urls)}개 URL")

        # Detailed logging for usage tracking
        try:
            from ui.panels.cta_panel import get_selected_cta_lines

            selected_font = getattr(self.app, 'selected_font_id', 'unknown')
            selected_cta = getattr(self.app, 'selected_cta_id', 'unknown')
            cta_lines = get_selected_cta_lines(self.app)
            
            rest.log_user_action(
                "영상 생성 시작", 
                f"작업 URL: {len(waiting_urls)}개\n"
                f"선택 음성: {', '.join(voice_labels)}\n"
                f"폰트: {selected_font}\n"
                f"CTA: {selected_cta} ({' '.join(cta_lines)})"
            )
        except Exception as e:
            logger.warning(f"Failed to log start action: {e}")

        # 동적 처리 플래그 설정
        self.app.dynamic_processing = True
        self.app.batch_processing = True
        self._set_run_status(
            "실행 중",
            f"일반 URL {len(waiting_urls)}개 처리를 시작했습니다. 백그라운드 스레드가 생성됩니다.",
            "active",
        )
        start_btn = getattr(self.app, "start_batch_button", None)
        stop_btn = getattr(self.app, "stop_batch_button", None)
        if start_btn is not None:
            self._reset_start_button_style(start_btn)
            self._set_button_text(start_btn, "실행 중...")
            start_btn.setEnabled(False)
        if stop_btn is not None:
            stop_btn.setEnabled(True)
        self.app.reset_progress_states()

        # 동적 처리 스레드 시작 (순차 실행 보장)
        thread = threading.Thread(target=self._batch_processing_wrapper, daemon=True)
        self.app.batch_thread = thread
        thread.start()

    def _batch_processing_wrapper(self):
        """배치 처리 래퍼 - Lock으로 순차 실행 보장

        Uses timeout-based lock acquisition to prevent deadlock if previous thread crashes.
        타임아웃 기반 락 획득으로 이전 스레드 크래시 시 데드락 방지.
        """
        LOCK_TIMEOUT_SECONDS = 300  # 5분 타임아웃
        MAX_RETRIES = 3

        acquired = self.app.batch_processing_lock.acquire(blocking=False)
        if not acquired:
            self.app.add_log("다른 작업이 진행 중이어서 대기합니다...")
            self._set_run_status(
                "실행 대기 중",
                "다른 배치 작업 락이 사용 중입니다. 잠시 대기한 뒤 다시 실행합니다.",
                "warning",
            )
            # Timeout-based acquisition to prevent deadlock
            for retry in range(MAX_RETRIES):
                acquired = self.app.batch_processing_lock.acquire(
                    timeout=LOCK_TIMEOUT_SECONDS
                )
                if acquired:
                    break
                self.app.add_log(
                    f"[배치] Lock 획득 재시도 ({retry + 1}/{MAX_RETRIES})..."
                )

            if not acquired:
                self.app.add_log(
                    "다른 작업이 진행 중입니다. 잠시 후 다시 시도해주세요."
                )
                self._set_run_status(
                    "실행 차단",
                    "배치 작업 락을 확보하지 못했습니다. 이전 작업이 비정상 종료됐는지 확인이 필요합니다.",
                    "error",
                )
                self.app.batch_processing = False
                self.app.dynamic_processing = False
                QTimer.singleShot(0, self._reset_batch_ui_on_complete)
                return

        try:
            self.app.add_log("영상 만들기 시작!")
            DynamicBatch.dynamic_batch_processing_thread(self.app)
        except Exception as e:
            logger.error("[배치] 처리 중 오류 발생: %s", e, exc_info=True)
            self.app.add_log(f"오류 발생: {e}")
            self._set_run_status(
                "작업 오류",
                f"배치 처리 중 오류가 발생했습니다: {e}",
                "error",
            )
        except BaseException as e:
            # MemoryError, SystemExit 등 심각한 오류도 잡아서 로깅
            logger.critical("[배치] 심각한 오류로 처리 중단: %s", e, exc_info=True)
            self.app.add_log(f"심각한 오류: {type(e).__name__}")
            self._set_run_status(
                "작업 중단",
                f"심각한 오류로 배치 처리가 중단됐습니다: {type(e).__name__}",
                "error",
            )
        finally:
            self.app.batch_processing_lock.release()
            self.app.add_log("영상 만들기 완료!")
            # 스레드 종료 시 UI 상태 복구
            QTimer.singleShot(0, self._reset_batch_ui_on_complete)

    def _reset_batch_ui_on_complete(self):
        """배치 처리 완료 시 UI 상태 복구"""
        try:
            self.app.batch_processing = False
            self.app.dynamic_processing = False
            start_btn = getattr(self.app, "start_batch_button", None)
            stop_btn = getattr(self.app, "stop_batch_button", None)
            if start_btn is not None:
                start_btn.setEnabled(True)
                self._set_button_text(start_btn, "▶ 작업 시작")
            if stop_btn is not None:
                stop_btn.setEnabled(False)

            # Check if there were skipped/stopped items → red button
            has_interrupted = False
            has_failed = False
            url_status = getattr(self.app, "url_status", {})
            for status in url_status.values():
                normalized = status.strip().lower() if isinstance(status, str) else ""
                if normalized in ("skipped", "건너뜀", "waiting", "대기"):
                    has_interrupted = True
                if normalized in ("failed", "error", "실패", "오류"):
                    has_failed = True

            if has_interrupted and start_btn is not None:
                self._set_start_button_red(start_btn)
            elif start_btn is not None:
                self._reset_start_button_style(start_btn)

            if has_failed:
                self._set_run_status(
                    "작업 완료 - 확인 필요",
                    "처리 중 실패 항목이 있습니다. 대기열의 상태/비고와 진행 로그를 확인하세요.",
                    "error",
                )
            elif has_interrupted:
                self._set_run_status(
                    "작업 중지/대기",
                    "완료되지 않은 항목이 남아 있습니다. 작업 시작을 다시 누르면 이어서 처리합니다.",
                    "warning",
                )
            else:
                self._set_run_status(
                    "작업 완료",
                    "현재 대기열 처리가 끝났습니다.",
                    "success",
                )

            self._play_completion_alarm()
        except Exception as e:
            logger.error(f"Failed to reset batch UI state: {e}")

    def _play_completion_alarm(self):
        try:
            import winsound

            for i in range(3):
                winsound.Beep(1000 + (i * 200), 300)
                if i < 2:
                    time.sleep(0.1)
            logger.info("[알람] 배치 처리 완료 알람 재생")
        except ImportError:
            logger.warning("[알람] winsound 모듈이 없어 알람을 재생할 수 없습니다.")
        except Exception as e:
            logger.error(f"[알람] 알람 재생 실패: {e}")

    def _set_start_button_red(self, btn):
        """작업 중지/건너뜀 시 시작 버튼을 빨간색으로 표시"""
        try:
            _ds = get_design_system()
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('error')};
                    color: white;
                    border-radius: {_ds.radius.base}px;
                    padding: {_ds.spacing.space_2}px {_ds.spacing.space_4}px;
                    font-weight: bold;
                    border: none;
                    font-size: {_ds.typography.size_sm}px;
                }}
                QPushButton:hover {{
                    background-color: #FF6B6B;
                }}
                QPushButton:disabled {{
                    background-color: {get_color('text_muted')};
                }}
            """)
        except Exception as e:
            logger.warning(f"Failed to set red button style: {e}")

    def _reset_start_button_style(self, btn):
        """시작 버튼 스타일을 기본(primary)으로 복구"""
        try:
            if hasattr(btn, "apply_theme"):
                btn.apply_theme()
            else:
                _ds = get_design_system()
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('primary')};
                        color: white;
                        border-radius: {_ds.radius.base}px;
                        padding: {_ds.spacing.space_2}px {_ds.spacing.space_4}px;
                        font-weight: bold;
                        border: none;
                        font-size: {_ds.typography.size_sm}px;
                    }}
                    QPushButton:hover {{
                        background-color: {get_color('secondary')};
                    }}
                    QPushButton:disabled {{
                        background-color: {get_color('text_muted')};
                    }}
                """)
        except Exception as e:
            logger.warning(f"Failed to reset button style: {e}")

    def stop_batch_processing(self):
        """배치 처리 중지 (현재 URL 완료 후 중지)"""
        if not self.app.batch_processing:
            self._set_run_status(
                "이미 중지됨",
                "현재 실행 중인 작업이 없습니다.",
                "idle",
            )
            self.app.add_log("이미 중지된 상태입니다.")
            return

        self.app.batch_processing = False
        self._set_run_status(
            "중지 요청됨",
            "현재 처리 중인 항목을 정리한 뒤 작업을 멈춥니다.",
            "warning",
        )
        self.app.dynamic_processing = False  # 동적 처리도 중지
        self.app.add_log("중지 요청됨 - 현재 영상 완료 후 중지됩니다.")

        # UI 즉시 업데이트 (실제 스레드는 백그라운드에서 정리됨)
        stop_btn = getattr(self.app, "stop_batch_button", None)
        if stop_btn is not None:
            stop_btn.setEnabled(False)

        # 백그라운드에서 스레드 종료 대기
        def wait_for_thread_finish():
            if self.app.batch_thread and self.app.batch_thread.is_alive():
                self.app.batch_thread.join(timeout=30)  # 최대 30초 대기
                self.app.add_log("이전 작업 종료 완료")

            # 세션 저장 (중지된 상태 기록)
            try:
                if hasattr(self.app, "session_manager"):
                    self.app.session_manager.save_session()
                    self.app.add_log("[세션] 중지 시점 세션 저장 완료")
            except Exception as e:
                self.app.add_log(f"[세션] 저장 실패: {e}")

            # UI 상태 복구 - 빨간색으로 표시 (중지됨)
            def enable_start_btn():
                start_btn = getattr(self.app, "start_batch_button", None)
                if start_btn is not None:
                    start_btn.setEnabled(True)
                    self._set_button_text(start_btn, "▶ 작업 시작")
                    self._set_start_button_red(start_btn)
            QTimer.singleShot(0, enable_start_btn)

        threading.Thread(target=wait_for_thread_finish, daemon=True).start()
