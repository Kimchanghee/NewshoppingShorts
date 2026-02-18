# -*- coding: utf-8 -*-
"""
Loading/Progress window for application initialization (PyQt6).
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtGui import QIcon

from ui.process_ui_modern import ModernProcessUi

class ProcessWindow(QMainWindow, ModernProcessUi):
    """Loading window that shows initialization progress for PyQt6."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowIcon(QIcon('resource/trayIcon.png'))
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
