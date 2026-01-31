"""
Settings tab placeholder (PyQt6).
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class SettingsTab(QWidget):
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Settings tab (placeholder)", self))
