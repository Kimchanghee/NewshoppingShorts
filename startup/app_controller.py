# -*- coding: utf-8 -*-
"""
Application flow controller for PyQt6.
"""
from typing import Optional, List, Tuple, Any, Dict
from PyQt6 import QtCore
from PyQt6.QtWidgets import QMessageBox, QApplication
from utils.logging_config import get_logger
from .initializer import Initializer

logger = get_logger(__name__)

class AppController:
    """Controls the login -> loading -> main app flow in PyQt6."""

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
        from ui.windows.login_window import Login
        self.login_window = Login()
        self.login_window.controller = self
        self.login_window.show()

    def on_login_success(self, login_data: Dict[str, Any]) -> None:
        from ui.windows.process_window import ProcessWindow
        self.login_data = login_data
        self.loading_window = ProcessWindow()
        self.login_window.hide()
        self.loading_window.show()

        self.initializer = Initializer()
        self.thread = QtCore.QThread()
        self.initializer.moveToThread(self.thread)
        self.initializer.progressChanged.connect(self.loading_window.setProgress)
        self.initializer.statusChanged.connect(self.loading_window.statusLabel.setText)
        self.initializer.checkItemChanged.connect(self.loading_window.updateCheckItem)
        self.initializer.ocrReaderReady.connect(self._on_ocr_ready)
        self.initializer.finished.connect(self._on_loading_finished)
        self.thread.started.connect(self.initializer.run)
        self.thread.start()

    def _on_ocr_ready(self, ocr_reader: Optional[object]) -> None:
        self.ocr_reader = ocr_reader

    def _on_loading_finished(self) -> None:
        if self.thread: self.thread.quit()
        if self.loading_window: self.loading_window.close()
        self.launch_main_app()

    def launch_main_app(self):
        """Launch the main PyQt6 application."""
        from main import VideoAnalyzerGUI
        self.main_gui = VideoAnalyzerGUI(login_data=self.login_data, preloaded_ocr=self.ocr_reader)
        self.main_gui.show()
