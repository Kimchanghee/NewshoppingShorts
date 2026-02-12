"""
Login Watch Handler

This module handles login status monitoring thread logic, extracted from main.py.
"""

import json
import os
import sys
import threading
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from caller import rest
from ui.components.custom_dialog import show_warning, show_error
from utils.logging_config import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI


class LoginHandler:
    """Handles login watch thread logic"""

    def __init__(self, app: "VideoAnalyzerGUI"):
        self.app = app

    def _extract_login_user_and_token(self) -> tuple[object, str]:
        """Extract user_id and JWT token from login_data safely."""
        login_data = getattr(self.app, "login_data", None)
        if not isinstance(login_data, dict):
            return None, ""

        data_part = login_data.get("data", {})
        inner = data_part.get("data", {}) if isinstance(data_part, dict) else {}
        user_id = inner.get("id") if isinstance(inner, dict) else None
        token = ""
        if isinstance(data_part, dict):
            token = str(data_part.get("token") or "").strip()
        return user_id, token

    def start_login_watch(self):
        """로그인 상태 감시 시작 및 신규 사용자 자동 체험판 신청"""
        if not self.app.login_data:
            logger.warning("[LoginHandler] No login data available, skipping watch start")
            return

        # 신규 사용자 자동 체험판 신청 로직
        # 로그인 직후 work_count가 없거나 0인 경우 (서버 데이터 기준)
        try:
            user_data = self.app.login_data.get("data", {}).get("data", {})
            user_id = user_data.get("id")
            work_count = user_data.get("work_count", -1)
            
            logger.info(f"[LoginHandler] Starting watch for user: {user_id}, initial work_count: {work_count}")

            # 신규 가입자(또는 work_count가 초기 상태인 사용자)라면 자동 체험판 신청
            if user_id and (work_count is None or work_count == 0):
                logger.info(f"[LoginHandler] Triggering auto-trial request for new user: {user_id}")
                threading.Thread(
                    target=self._auto_request_trial, args=(user_id,), daemon=True
                ).start()
            else:
                logger.info("[LoginHandler] User has valid work count, skipping auto-trial request")
        except Exception as e:
            logger.warning(f"[LoginHandler] Auto trial request check failed: {e}")

        self.app._login_watch_stop = False
        t = threading.Thread(target=self._login_watch_loop, daemon=True)
        t.start()

    def _auto_request_trial(self, user_id):
        """신규 사용자를 위한 자동 체험판 신청"""
        try:
            logger.info(f"[AutoTrial] Requesting trial for user: {user_id}")
            # 이미 신청 대기 중인지 확인 (SubscriptionWidget 로직 참조)
            status_res = rest.get_subscription_status_with_consistency(user_id)
            if status_res.get("has_pending_request"):
                logger.info(f"[AutoTrial] User {user_id} already has pending request, skipping")
                return

            # 신청 API 호출
            logger.info(f"[AutoTrial] Sending subscription request API call...")
            res = rest.safe_subscription_request(
                user_id, "신규 가입 자동 체험판 신청"
            )
            
            if res.get("success"):
                logger.info(f"[AutoTrial] Request success: {res.get('message')}")
                # UI 업데이트를 위해 메인 스레드에서 새로고침 트리거
                refresh_fn = getattr(self.app, "_update_subscription_info", None)
                if refresh_fn is not None:
                    QTimer.singleShot(2000, refresh_fn)
            else:
                logger.warning(f"[AutoTrial] Request failed: {res.get('message')}")
        except Exception as e:
            logger.error(f"[AutoTrial] Error during request: {e}", exc_info=True)

    def _login_watch_loop(self):
        """5초마다 로그인 상태 확인"""
        try:
            userId = self.app.login_data["data"]["data"]["id"]
            userIp = self.app.login_data["data"]["ip"]
            logger.info(f"[watch_loop] Loop started for user: {userId} at IP: {userIp}")
        except Exception as e:
            logger.warning("[watch_loop] Failed to extract login data: %s", e)
            return

        loop_count = 0
        last_user_type = self.app.login_data.get("data", {}).get("data", {}).get("user_type")
        while not getattr(self.app, "_login_watch_stop", False):
            loop_count += 1
            try:
                if loop_count % 12 == 0: # 1분마다 로그 남기기 (5초 * 12)
                    logger.debug(f"[watch_loop] Heartbeat check... (seq={loop_count})")

                current_task = getattr(self.app.state, 'current_task_var', None)
                app_version = self._get_app_version()
                data = {"userId": userId, "key": "ssmaker", "ip": userIp, "current_task": current_task, "app_version": app_version}
                res = rest.loginCheck(**data)
                st = res.get("status") if isinstance(res, dict) else None

                if st == "skip":
                    # 검증 실패 - 조용히 재시도
                    if loop_count % 12 == 0:
                        logger.debug("[watch_loop] Check skipped (validation failed)")
                    time.sleep(5)
                    continue

                if st == "AUTH_REQUIRED":
                    logger.warning("[watch_loop] Auth token missing/expired (AUTH_REQUIRED)")
                    cb_signal = getattr(self.app, 'ui_callback_signal', None)
                    if cb_signal is not None:
                        cb_signal.emit(self._on_auth_required)
                    else:
                        QTimer.singleShot(0, self._on_auth_required)
                    break

                if st == "EU003":
                    logger.warning("[watch_loop] Duplicate login detected (EU003)")
                    # 스레드 안전 UI 콜백 (ui_callback_signal 사용)
                    cb_signal = getattr(self.app, 'ui_callback_signal', None)
                    if cb_signal is not None:
                        cb_signal.emit(lambda: self.exit_program_other_place("EU003"))
                    else:
                        QTimer.singleShot(0, lambda: self.exit_program_other_place("EU003"))
                    break
                elif st == "EU004":
                    logger.error("[watch_loop] Force close command received (EU004)")
                    cb_signal = getattr(self.app, 'ui_callback_signal', None)
                    if cb_signal is not None:
                        cb_signal.emit(lambda: self.error_program_force_close("EU004"))
                    else:
                        QTimer.singleShot(0, lambda: self.error_program_force_close("EU004"))
                    break

                # 구독 상태 실시간 감지: heartbeat 응답의 user_type이 변경되면 UI 즉시 갱신
                if st is True and isinstance(res, dict):
                    server_user_type = res.get("user_type")
                    if server_user_type and last_user_type and server_user_type != last_user_type:
                        logger.info(
                            f"[watch_loop] user_type changed: {last_user_type} -> {server_user_type}"
                        )
                        last_user_type = server_user_type
                        cb_signal = getattr(self.app, 'ui_callback_signal', None)
                        refresh_fn = getattr(self.app, 'refresh_user_status', None)
                        if cb_signal is not None and refresh_fn is not None:
                            cb_signal.emit(refresh_fn)
                    elif server_user_type:
                        last_user_type = server_user_type
            except Exception as e:
                # 네트워크 오류 등은 무시하고 재시도 (Network errors are ignored and retried)
                if loop_count % 12 == 0:
                    logger.debug(f"[watch_loop] Check exception: {e}")
            time.sleep(5)

    def _on_auth_required(self):
        """토큰 만료/유실 등으로 세션 확인이 불가능할 때 사용자에게 안내 후 종료."""
        try:
            show_warning(
                self.app,
                "로그인 필요",
                "로그인 세션이 만료되었거나 인증 정보가 없습니다.\n\n"
                "프로그램을 재시작한 뒤 다시 로그인해주세요.",
            )
        except Exception as e:
            logger.warning("Failed to show auth required warning: %s", e)
        self._safe_exit()

    def _safe_exit(self):
        """안전한 앱 종료 - 로그아웃 후 Qt 앱 종료 (메인 스레드에서만 호출)"""
        # 백그라운드 스레드에서 직접 호출된 경우 메인 스레드로 재스케줄
        qt_app = QApplication.instance()
        if qt_app is not None:
            from PyQt6.QtCore import QThread
            if QThread.currentThread() != qt_app.thread():
                logger.warning("[LoginHandler] _safe_exit called from background thread, rescheduling")
                QTimer.singleShot(0, self._safe_exit)
                return
        try:
            # 배치 처리 중이면 스레드 종료 대기
            self.app.batch_processing = False
            self.app.dynamic_processing = False
            batch_thread = getattr(self.app, "batch_thread", None)
            if batch_thread is not None and batch_thread.is_alive():
                logger.info("[LoginHandler] Waiting for batch thread to finish (max 15s)...")
                batch_thread.join(timeout=15)

            # 서버 로그아웃
            if self.app.login_data and isinstance(self.app.login_data, dict):
                user_id, token = self._extract_login_user_and_token()
                if user_id:
                    try:
                        logout_status = rest.logOut(userId=user_id, key=token or "ssmaker")
                        if str(logout_status).lower() == "success":
                            logger.info("[LoginHandler] Logout successful")
                        else:
                            logger.warning(f"[LoginHandler] Logout returned non-success status: {logout_status}")
                    except Exception as logout_err:
                        logger.warning("Logout failed (ignored): %s", logout_err)

            # 구독 매니저 타이머 중지
            sub_mgr = getattr(self.app, "subscription_manager", None)
            if sub_mgr is not None:
                sub_mgr.stop()
        except Exception as e:
            logger.error("Safe exit cleanup failed: %s", e)

        # Qt 앱 종료
        try:
            qt_app = QApplication.instance()
            if qt_app is not None:
                qt_app.quit()
        except Exception:
            pass

    def exit_program_other_place(self, status: str):
        """다른 장소에서 로그인(EU003) → 알림 후 종료"""
        if status == "EU003":
            try:
                show_warning(
                    self.app,
                    "중복 로그인",
                    "다른 장소에서 로그인되어 프로그램을 종료합니다.",
                )
            except Exception as e:
                logger.warning("Failed to show duplicate login warning: %s", e)
            self._safe_exit()

    def error_program_force_close(self, status: str):
        """서버에서 강제 종료(EU004) → 알림 후 종료"""
        if status == "EU004":
            try:
                show_error(self.app, "오류", "오류로 인해 프로그램을 종료합니다.")
            except Exception as e:
                logger.warning("Failed to show force close error dialog: %s", e)
            self._safe_exit()

    def _get_app_version(self) -> str:
        """현재 앱 버전을 version.json에서 읽어 반환"""
        try:
            # PyInstaller 번들 또는 개발 환경에서 경로 결정
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            version_file = os.path.join(base_path, "version.json")
            if os.path.exists(version_file):
                with open(version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("version", "unknown")

            # fallback: config에서 버전 확인
            try:
                from config import APP_VERSION
                return APP_VERSION
            except ImportError:
                pass

            return "unknown"
        except Exception as e:
            logger.warning(f"[LoginHandler] Failed to get app version: {e}")
            return "unknown"

