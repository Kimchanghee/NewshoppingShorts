"""
Login Watch Handler

This module handles login status monitoring thread logic, extracted from main.py.
"""

import threading
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from ui.components.custom_dialog import show_warning, show_error
from caller import rest
from utils.logging_config import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI


class LoginHandler:
    """Handles login watch thread logic"""

    def __init__(self, app: "VideoAnalyzerGUI"):
        self.app = app

    def start_login_watch(self):
        """로그인 상태 감시 시작 및 신규 사용자 자동 체험판 신청"""
        if not self.app.login_data:
            logger.warning("[LoginHandler] No login data available, skipping watch start")
            return

        # 신규 사용자 자동 체험판 신청 로직
        # 로그인 직후 work_count가 없거나 -1인 경우 (서버 데이터 기준)
        try:
            user_data = self.app.login_data.get("data", {}).get("data", {})
            user_id = user_data.get("id")
            work_count = user_data.get("work_count", -1)
            
            logger.info(f"[LoginHandler] Starting watch for user: {user_id}, initial work_count: {work_count}")

            # 신규 가입자(또는 work_count가 초기 상태인 사용자)라면 3회 신청
            if user_id and (work_count <= 0 or work_count is None):
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
        """신규 사용자를 위한 자동 체험판 신청 (5회)"""
        try:
            logger.info(f"[AutoTrial] Requesting trial for user: {user_id}")
            # 이미 신청 대기 중인지 확인 (SubscriptionWidget 로직 참조)
            status_res = rest.get_subscription_status_with_consistency(user_id)
            if status_res.get("has_pending_request"):
                logger.info(f"[AutoTrial] User {user_id} already has pending request, skipping")
                return

            # 신청 API 호출 (5회로 변경)
            logger.info(f"[AutoTrial] Sending subscription request API call...")
            res = rest.safe_subscription_request(
                user_id, "신규 가입 자동 체험판 신청 (5회)"
            )
            
            if res.get("success"):
                logger.info(f"[AutoTrial] Request success: {res.get('message')}")
                # UI 업데이트를 위해 메인 스레드에서 새로고침 트리거
                refresh_fn = getattr(self.app, "_refresh_subscription_status", None)
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
        while not getattr(self.app, "_login_watch_stop", False):
            loop_count += 1
            try:
                if loop_count % 12 == 0: # 1분마다 로그 남기기 (5초 * 12)
                    logger.debug(f"[watch_loop] Heartbeat check... (seq={loop_count})")
                    
                current_task = getattr(self.app.state, 'current_task_var', None)
                data = {"userId": userId, "key": "ssmaker", "ip": userIp, "current_task": current_task}
                res = rest.loginCheck(**data)
                st = res.get("status") if isinstance(res, dict) else None
                
                if st == "skip":
                    # 검증 실패 - 조용히 재시도
                    if loop_count % 12 == 0:
                        logger.debug("[watch_loop] Check skipped (validation failed)")
                    time.sleep(5)
                    continue
                    
                if st == "EU003":
                    logger.warning("[watch_loop] Duplicate login detected (EU003)")
                    # PyQt6 스레드 안전 호출
                    QTimer.singleShot(
                        0, lambda: self.exit_program_other_place("EU003")
                    )
                    break
                elif st == "EU004":
                    logger.error("[watch_loop] Force close command received (EU004)")
                    QTimer.singleShot(
                        0, lambda: self.error_program_force_close("EU004")
                    )
                    break
            except Exception as e:
                # 네트워크 오류 등은 무시하고 재시도 (Network errors are ignored and retried)
                if loop_count % 12 == 0:
                    logger.debug(f"[watch_loop] Check exception: {e}")
            time.sleep(5)

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
            # 배치 처리 중지
            self.app.batch_processing = False
            self.app.dynamic_processing = False

            # 서버 로그아웃
            if self.app.login_data and isinstance(self.app.login_data, dict):
                user_id = (
                    self.app.login_data.get("data", {})
                    .get("data", {})
                    .get("id")
                )
                if user_id:
                    try:
                        rest.logOut(userId=user_id, key="ssmaker")
                        logger.info("[LoginHandler] Logout successful")
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
