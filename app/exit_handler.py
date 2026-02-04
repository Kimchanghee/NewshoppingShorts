"""
Exit Handler Module

This module handles application exit, cleanup, and session management.
Extracted from main.py for better code organization.
"""

import threading
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from caller import rest
from ui.components.custom_dialog import show_question, show_error
from utils.logging_config import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI


class ExitHandler:
    """Handles application exit and cleanup"""

    def __init__(self, app: 'VideoAnalyzerGUI'):
        self.app = app

    def process_before_exit_program(self):
        """
        Logout from server before app exit (safe for both Qt/Tk).
        서버 로그아웃 후 앱 종료 (Qt/Tk 모두 안전하게 시도).
        """
        try:
            # Validate login_data structure
            if not self.app.login_data or not isinstance(self.app.login_data, dict):
                logger.info("No login data - skipping logout")
                return

            # Safe nested dictionary access
            user_id = (self.app.login_data.get('data', {})
                                          .get('data', {})
                                          .get('id'))

            if not user_id:
                logger.warning("User ID not found in login data - skipping logout")
                return

            # Attempt logout
            data = {'userId': user_id, "key": "ssmaker"}
            try:
                rest.logOut(**data)
                logger.info("Logout successful")
            except Exception as e:
                logger.warning(f"Logout failed (ignored): {e}")

        except (AttributeError, TypeError, KeyError) as e:
            logger.error(f"Logout data structure error (ignored): {e}")
        except Exception as e:
            logger.exception(f"Unexpected logout error (ignored): {e}")

        # Qt 앱이 살아있다면 먼저 종료 시도
        self._quit_qt_app()

    def _quit_qt_app(self):
        """Qt 앱 종료 시도"""
        try:
            qt_app = QApplication.instance()
            if qt_app is not None:
                qt_app.quit()
                logger.info("[종료] QApplication.quit() 호출")
        except Exception:
            pass

    def safe_exit(self):
        """안전한 종료 처리"""
        try:
            # 배치 처리 중지
            if self.app.batch_processing:
                self.app.batch_processing = False
                self.app.dynamic_processing = False
                logger.info("[종료] 배치 처리 중지")

            # 세션 저장
            if hasattr(self.app, 'session_manager'):
                try:
                    self.app.session_manager.save_session()
                    logger.info("[종료] 세션 저장 완료")
                except Exception as e:
                    logger.error(f"[종료] 세션 저장 실패: {e}")

            # 임시 파일 정리
            self.app.cleanup_temp_files()

            # 로그아웃
            self.process_before_exit_program()

        except Exception as e:
            logger.error(f"[종료] 종료 전 처리 실패: {e}")

    def on_close_request(self):
        """윈도우 닫기 요청 처리"""
        # 배치 처리 중이면 확인
        if self.app.batch_processing:
            try:
                result = show_question(
                    self.app,
                    "종료 확인",
                    "배치 처리가 진행 중입니다.\n\n"
                    "정말 종료하시겠습니까?\n"
                    "(현재 작업은 중단됩니다)"
                )
                if not result:
                    return  # 종료 취소
            except Exception as e:
                logger.error(f"[종료] 확인 다이얼로그 오류: {e}")

        # 안전한 종료 수행
        self.safe_exit()

        # PyQt6 윈도우 종료
        try:
            self.app.close()
        except Exception:
            pass

    def check_and_restore_session(self):
        """세션 복구 확인 및 처리"""
        if not hasattr(self.app, 'session_manager'):
            return

        try:
            session_manager = self.app.session_manager
            if session_manager.has_saved_session():
                session_manager.restore_session()
                logger.info("[세션] 이전 세션 복구 완료")
        except Exception as e:
            logger.error(f"[세션] 복구 실패: {e}")

    def auto_save_session(self):
        """자동 세션 저장 (주기적 호출)"""
        if not hasattr(self.app, 'session_manager'):
            return

        try:
            self.app.session_manager.save_session()
        except Exception as e:
            logger.error(f"[세션] 자동 저장 실패: {e}")

        # 다음 자동 저장 예약 (5분)
        QTimer.singleShot(300000, self.auto_save_session)

    def retry_restore_session(self, max_retries: int = 3):
        """세션 복구 재시도"""
        for attempt in range(max_retries):
            try:
                if hasattr(self.app, 'session_manager'):
                    self.app.session_manager.restore_session()
                    logger.info(f"[세션] 복구 성공 (시도 {attempt + 1})")
                    return True
            except Exception as e:
                logger.warning(f"[세션] 복구 시도 {attempt + 1} 실패: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)

        logger.error(f"[세션] 최대 재시도 횟수 초과")
        return False
