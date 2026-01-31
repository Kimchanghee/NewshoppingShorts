# -*- coding: utf-8 -*-
"""
Loading/Progress window for application initialization (PyQt6).
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtGui import QIcon

from ui import process_ui

class ProcessWindow(QMainWindow, process_ui.Process_Ui):
    """Loading window that shows initialization progress for PyQt6."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowIcon(QIcon('resource/trayIcon.png'))
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
