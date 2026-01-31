"""
Settings button for PyQt6
"""
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

class SettingsButton(QPushButton):
    def __init__(self, parent=None, on_click=None, theme_manager=None, size=36):
        super().__init__("⚙️", parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 16pt;
                color: #64748b;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                border-radius: 18px;
                color: #1b0e10;
            }
        """)
        if on_click:
            self.clicked.connect(on_click)
