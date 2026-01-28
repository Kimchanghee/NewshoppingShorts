# -*- coding: utf-8 -*-
"""
Loading/Progress window for application initialization.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtGui import QIcon

from ui import process_ui


class ProcessWindow(QMainWindow, process_ui.Process_Ui):
    """Loading window that shows initialization progress."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowIcon(QIcon('resource/icons/trayIcon.png'))
        self.setupUi(self)
        self.setWindowFlags(Qt.FramelessWindowHint)
