# -*- coding: utf-8 -*-
"""
Logging Mixin - Provides thread-safe logging methods for GUI.

Extracted from main.py for cleaner separation of logging concerns.
"""
from datetime import datetime

from utils.logging_config import get_logger

logger = get_logger(__name__)


class LoggingMixin:
    """Provides thread-safe logging methods for GUI.

    Requires:
        - self.log_signal: pyqtSignal(str, str) for message and level
        - self.progress_panel: Panel with append_log method (optional)
    """

    def add_log(self, message: str, level: str = "info"):
        """Thread-safe logging - terminal output + UI signal.

        Args:
            message: Log message to display
            level: Log level (info, warning, error, debug)
        """
        log_method = getattr(logger, level, logger.info)
        log_method(message)

        # UI 패널 업데이트용 시그널 (터미널 출력은 위에서 이미 완료)
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            full_msg = f"[{timestamp}] {message}"
            self.log_signal.emit(full_msg, level)
        except RuntimeError:
            pass

    def _on_log_signal(self, message: str, level: str):
        """Main thread handler for UI log panel update.

        Called via log_signal connection. Only updates UI panel,
        does not duplicate terminal output.

        Args:
            message: Formatted log message with timestamp
            level: Log level for styling
        """
        panel = getattr(self, "progress_panel", None)
        if panel is not None and hasattr(panel, "append_log"):
            panel.append_log(message, level)

    def _execute_ui_callback(self, callback):
        """Execute callback in main thread via ui_callback_signal.

        Args:
            callback: Callable to execute in main thread
        """
        try:
            if callable(callback):
                callback()
        except Exception as e:
            logger.debug(f"[UI callback] error: {e}")
