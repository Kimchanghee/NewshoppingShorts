"""
Login Watch Handler

This module handles login status monitoring thread logic, extracted from main.py.
"""

import threading
import time
from typing import TYPE_CHECKING

from ui.components.custom_dialog import show_warning, show_error
from caller import rest
from utils.logging_config import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from app.main_app import VideoAnalyzerGUI


class LoginHandler:
    """Handles login watch thread logic"""

    def __init__(self, app: "VideoAnalyzerGUI"):
        self.app = app

    def start_login_watch(self):
        """로그인 상태 감시 시작 및 신규 사용자 자동 체험판 신청"""
        if not self.app.login_data:
            return

        # 신규 사용자 자동 체험판 신청 로직
        # 로그인 직후 work_count가 없거나 -1인 경우 (서버 데이터 기준)
        try:
            user_data = self.app.login_data.get("data", {}).get("data", {})
            user_id = user_data.get("id")
            work_count = user_data.get("work_count", -1)

            # 신규 가입자(또는 work_count가 초기 상태인 사용자)라면 3회 신청
            if user_id and (work_count <= 0 or work_count is None):
                threading.Thread(
                    target=self._auto_request_trial, args=(user_id,), daemon=True
                ).start()
        except Exception as e:
            logger.warning(f"Auto trial request check failed: {e}")

        self.app._login_watch_stop = False
        t = threading.Thread(target=self._login_watch_loop, daemon=True)
        t.start()

    def _auto_request_trial(self, user_id):
        """신규 사용자를 위한 자동 체험판 신청 (3회)"""
        try:
            logger.info(f"Auto-requesting trial for user: {user_id}")
            # 이미 신청 대기 중인지 확인 (SubscriptionWidget 로직 참조)
            status_res = rest.get_subscription_status_with_consistency(user_id)
            if status_res.get("has_pending_request"):
                logger.info("User already has pending request, skipping auto-request")
                return

            # 신청 API 호출
            res = rest.safe_subscription_request(
                user_id, "신규 가입 자동 체험판 신청 (3회)"
            )
            if res.get("success"):
                logger.info(f"Auto-trial request success: {res.get('message')}")
                # UI 업데이트를 위해 메인 스레드에서 새로고침 트리거
                self.app.root.after(2000, self.app._refresh_subscription_status)
            else:
                logger.warning(f"Auto-trial request failed: {res.get('message')}")
        except Exception as e:
            logger.error(f"Error during auto-trial request: {e}")

    def _login_watch_loop(self):
        """5초마다 로그인 상태 확인"""
        try:
            userId = self.app.login_data["data"]["data"]["id"]
            userIp = self.app.login_data["data"]["ip"]
        except Exception as e:
            logger.warning("Failed to extract login data for watch loop: %s", e)
            return

        while not getattr(self.app, "_login_watch_stop", False):
            try:
                data = {"userId": userId, "key": "ssmaker", "ip": userIp}
                res = rest.loginCheck(**data)
                st = res.get("status") if isinstance(res, dict) else None
                if st == "skip":
                    # 검증 실패 - 조용히 재시도
                    time.sleep(5)
                    continue
                if st == "EU003":
                    # Tkinter 스레드 안전 호출
                    self.app.root.after(
                        0, lambda: self.exit_program_other_place("EU003")
                    )
                    break
                elif st == "EU004":
                    self.app.root.after(
                        0, lambda: self.error_program_force_close("EU004")
                    )
                    break
            except Exception as e:
                # 네트워크 오류 등은 무시하고 재시도 (Network errors are ignored and retried)
                logger.debug("Login check failed (will retry): %s", e)
            time.sleep(5)

    def exit_program_other_place(self, status: str):
        """다른 장소에서 로그인(EU003) → 알림 후 종료"""
        if status == "EU003":
            try:
                show_warning(
                    self.app.root,
                    "중복 로그인",
                    "다른 장소에서 로그인되어 프로그램을 종료합니다.",
                )
            except Exception as e:
                logger.warning("Failed to show duplicate login warning: %s", e)
            self.app.processBeforeExitProgram()

    def error_program_force_close(self, status: str):
        """서버에서 강제 종료(EU004) → 알림 후 종료"""
        if status == "EU004":
            try:
                show_error(self.app.root, "오류", "오류로 인해 프로그램을 종료합니다.")
            except Exception as e:
                logger.warning("Failed to show force close error dialog: %s", e)
            self.app.processBeforeExitProgram()
