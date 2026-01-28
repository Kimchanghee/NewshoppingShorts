# -*- coding: utf-8 -*-
"""
Application flow controller.
Manages Login -> Loading -> Main App transitions.
"""
from typing import Optional, List, Tuple, Any, Dict

from PyQt5 import QtCore
from PyQt5.QtWidgets import QMessageBox

from utils.logging_config import get_logger
from .initializer import Initializer
from .constants import CHECK_ITEM_IMPACTS

logger = get_logger(__name__)


class AppController:
    """Controls the login -> loading -> main app flow."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.login_data: Optional[Dict[str, Any]] = None
        self.ocr_reader: Optional[object] = None
        self.login_window: Optional[Any] = None
        self.loading_window: Optional[Any] = None
        self.thread: Optional[QtCore.QThread] = None
        self.initializer: Optional[Initializer] = None
        self.init_issues: List[Tuple[str, str, str]] = []

    def start(self) -> None:
        """Show login window (may already be created by ssmaker.py)."""
        if not self.login_window:
            from ui.windows.login_window import Login
            self.login_window = Login()
            self.login_window.controller = self
            self.login_window.show()

    def on_login_success(self, login_data: Dict[str, Any]) -> None:
        """Called when login succeeds."""
        from PyQt5.QtWidgets import QApplication
        from ui.windows.process_window import ProcessWindow

        self.login_data = login_data

        # Pre-create loading window for smooth transition
        self.loading_window = ProcessWindow()
        QApplication.processEvents()

        # Smooth transition: hide login, show loading, then close login
        self.login_window.hide()
        self.loading_window.show()
        QApplication.processEvents()

        self.login_window.closeSocket()
        self.login_window.close()

        # Start initialization
        self.initializer = Initializer()
        self.thread = QtCore.QThread()
        self.initializer.moveToThread(self.thread)

        self.initializer.progressChanged.connect(self._update_progress)
        self.initializer.checkItemChanged.connect(self.loading_window.updateCheckItem)
        self.initializer.statusChanged.connect(self.loading_window.statusLabel.setText)
        self.initializer.ocrReaderReady.connect(self._on_ocr_ready)
        self.initializer.initWarnings.connect(self._on_init_warnings)
        self.initializer.finished.connect(self._on_loading_finished)

        self.thread.started.connect(self.initializer.run)
        self.thread.start()

    def _update_progress(self, value: int) -> None:
        """Update progress bar."""
        self.loading_window.progressBar.setValue(value)
        self.loading_window.percentLabel.setText(f"{value}%")

    def _on_ocr_ready(self, ocr_reader: Optional[object]) -> None:
        """Handle OCR reader ready signal."""
        self.ocr_reader = ocr_reader

    def _on_init_warnings(self, issues: List[Tuple[str, str, str]]) -> None:
        """Handle initialization warnings/errors."""
        self.init_issues = issues

    def _show_init_warnings_popup(self) -> bool:
        """
        Show initialization issues popup.

        Returns:
            True if program should continue, False otherwise
        """
        if not self.init_issues:
            return True

        # Separate errors and warnings
        errors = [
            (item_id, msg)
            for item_id, status, msg in self.init_issues
            if status == "error"
        ]
        warnings = [
            (item_id, msg)
            for item_id, status, msg in self.init_issues
            if status == "warning"
        ]

        # Check for critical errors (Hard Stop)
        has_critical_error = any(
            CHECK_ITEM_IMPACTS.get(item_id, {}).get("critical", False)
            for item_id, _ in errors
        )

        # Build message
        msg_parts: List[str] = []

        if errors:
            msg_parts.append("심각한 문제 (기능 제한):\n")
            for item_id, msg in errors:
                impact_info = CHECK_ITEM_IMPACTS.get(item_id, {})
                name = impact_info.get("name", item_id)
                impact = impact_info.get("impact", "기능에 영향이 있을 수 있습니다.")
                solution = impact_info.get("solution", "")
                msg_parts.append(f"• {name}: {impact}\n")
                if msg:
                    msg_parts.append(f"  상세: {msg}\n")
                if solution:
                    msg_parts.append(f"  -> {solution}\n")
            msg_parts.append("\n")

        if warnings:
            msg_parts.append("경고 (일부 기능 제한):\n")
            for item_id, msg in warnings:
                impact_info = CHECK_ITEM_IMPACTS.get(item_id, {})
                name = impact_info.get("name", item_id)
                impact = impact_info.get("impact", "일부 기능이 제한될 수 있습니다.")
                msg_parts.append(f"• {name}: {impact}\n")
                if msg:
                    msg_parts.append(f"  상세: {msg}\n")

        detail_text = "".join(msg_parts)

        # Critical error - Hard Stop
        if has_critical_error:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("필수 구성요소 누락")
            msg.setText("필수 구성요소가 없어 프로그램을 실행할 수 없습니다.")
            msg.setInformativeText("프로그램을 종료합니다.")
            msg.setDetailedText(detail_text)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            return False

        # Non-critical errors - show warning (can continue)
        if errors:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("초기화 문제 발견")
            msg.setText("일부 필수 구성요소에 문제가 있습니다.\n계속 진행하시겠습니까?")
            msg.setInformativeText("일부 기능이 정상적으로 작동하지 않을 수 있습니다.")
            msg.setDetailedText(detail_text)
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            result = msg.exec_()
            return result == QMessageBox.Yes
        else:
            # Warnings only - show info (continue)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("초기화 알림")
            msg.setText("일부 구성요소에 주의가 필요합니다.")
            msg.setInformativeText("프로그램은 정상적으로 실행됩니다.")
            msg.setDetailedText(detail_text)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            return True

    def _on_loading_finished(self) -> None:
        """Handle loading completion."""
        self.thread.quit()

        # Show warnings popup if any issues
        should_continue = self._show_init_warnings_popup()

        self.loading_window.close()

        if should_continue:
            # Exit Qt and transition to Tkinter
            QtCore.QCoreApplication.quit()
        else:
            # User cancelled - exit program
            self.login_data = None
            QtCore.QCoreApplication.quit()
