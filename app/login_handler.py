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

    def __init__(self, app: 'VideoAnalyzerGUI'):
        self.app = app

    def start_login_watch(self):
        """로그인 상태 감시 시작 (threading.Thread 사용)"""
        if not self.app.login_data:
            return
        self.app._login_watch_stop = False
        t = threading.Thread(target=self._login_watch_loop, daemon=True)
        t.start()

    def _login_watch_loop(self):
        """5초마다 로그인 상태 확인"""
        try:
            userId = self.app.login_data['data']['data']['id']
            userIp = self.app.login_data['data']['ip']
        except Exception as e:
            logger.warning("Failed to extract login data for watch loop: %s", e)
            return

        while not getattr(self.app, "_login_watch_stop", False):
            try:
                data = {'userId': userId, "key": "ssmaker", "ip": userIp}
                res = rest.loginCheck(**data)
                st = res.get('status') if isinstance(res, dict) else None
                if st == "EU003":
                    # Tkinter 스레드 안전 호출
                    self.app.root.after(0, lambda: self.exit_program_other_place("EU003"))
                    break
                elif st == "EU004":
                    self.app.root.after(0, lambda: self.error_program_force_close("EU004"))
                    break
            except Exception as e:
                # 네트워크 오류 등은 무시하고 재시도 (Network errors are ignored and retried)
                logger.debug("Login check failed (will retry): %s", e)
            time.sleep(5)

    def exit_program_other_place(self, status: str):
        """다른 장소에서 로그인(EU003) → 알림 후 종료"""
        if status == "EU003":
            try:
                show_warning(self.app.root, "중복 로그인", "다른 장소에서 로그인되어 프로그램을 종료합니다.")
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
