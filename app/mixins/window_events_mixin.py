# -*- coding: utf-8 -*-
"""
Window Events Mixin - Window event handlers for VideoAnalyzerGUI.

Extracted from main.py for cleaner separation of event handling.
"""
from PyQt6.QtCore import QTimer

from utils.logging_config import get_logger

logger = get_logger(__name__)


class WindowEventsMixin:
    """Provides window event handlers.

    Requires:
        - self.exit_handler: ExitHandler instance
        - self.batch_processing: bool
        - self.subscription_manager: SubscriptionManager instance
        - self._resize_throttle: QTimer instance
        - self._is_resizing: bool
        - self._tutorial_shown: bool
        - self._should_show_tutorial: bool
    """

    def closeEvent(self, event):
        """Handle safe exit on window close."""
        if getattr(self, "_closing", False):
            event.accept()
            return

        if hasattr(self, "exit_handler"):
            if self.batch_processing:
                from ui.components.custom_dialog import show_question

                try:
                    if not show_question(
                        self,
                        "종료 확인",
                        "배치 처리가 진행 중입니다.\n정말 종료하시겠습니까?",
                    ):
                        event.ignore()
                        return
                except Exception:
                    pass

            self._closing = True
            self.exit_handler.safe_exit()
        event.accept()

    def resizeEvent(self, event):
        """Pause non-essential updates during resize."""
        super().resizeEvent(event)
        if not self._is_resizing:
            self._is_resizing = True
            self.subscription_manager.pause_countdown()
        self._resize_throttle.start()

    def _on_resize_done(self):
        """Resume normal operation after resize."""
        self._is_resizing = False
        self.subscription_manager.resume_countdown()

    def showEvent(self, event):
        """Show tutorial on first launch + check for previous session."""
        super().showEvent(event)
        if not getattr(self, "_show_event_handled", False):
            self._show_event_handled = True
            if (
                hasattr(self, "_should_show_tutorial")
                and self._should_show_tutorial
                and not self._tutorial_shown
            ):
                self._tutorial_shown = True
                QTimer.singleShot(800, self._show_tutorial_then_session)
            else:
                QTimer.singleShot(1500, self._check_previous_session)

    def _check_first_run(self):
        """Check if tutorial should be shown."""
        from ui.components.tutorial_manager import TutorialManager

        self._should_show_tutorial = TutorialManager.should_show_tutorial()

    def _check_previous_session(self):
        """Check for session restore + start auto-save timer."""
        if hasattr(self, "exit_handler"):
            try:
                self.exit_handler.check_and_restore_session()
            except Exception as e:
                logger.warning(f"[세션] 복구 확인 중 오류: {e}")
            self.exit_handler.auto_save_session()

    def _show_tutorial_then_session(self):
        """Show tutorial, then check session on complete/skip."""
        from ui.components.tutorial_manager import show_guided_tutorial

        self._tutorial_manager = show_guided_tutorial(
            self,
            on_complete=lambda: QTimer.singleShot(300, self._check_previous_session),
            on_skip=lambda: QTimer.singleShot(300, self._check_previous_session),
        )

    def show_tutorial_manual(self):
        """Manually show tutorial from settings."""
        from ui.components.tutorial_manager import show_guided_tutorial

        if (
            hasattr(self, "_tutorial_manager")
            and self._tutorial_manager
            and self._tutorial_manager.is_running
        ):
            self._tutorial_manager.stop()
        self._tutorial_manager = show_guided_tutorial(self)
