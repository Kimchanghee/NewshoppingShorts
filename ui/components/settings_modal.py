"""
Settings modal placeholder (PyQt6)
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

class SettingsModal(QDialog):
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Settings modal (PyQt6 placeholder)", self))
        self.setModal(True)
