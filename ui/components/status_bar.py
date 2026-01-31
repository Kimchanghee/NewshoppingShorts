"""
Status bar component for PyQt6
"""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

class StatusBar(QLabel):
    def __init__(self, parent=None, gui=None):
        super().__init__(parent)
        self.gui = gui
        self.setText("준비 완료")
        self.setStyleSheet("color: #64748b; font-size: 8pt; padding: 2px 10px; background-color: #ffffff; border-top: 1px solid #e2e8f0;")
        self.setFixedHeight(24)
        
        if gui:
            gui.status_bar = self
            # Initial refersh if method exists
            if hasattr(gui, 'refresh_voice_status_display'):
                gui.refresh_voice_status_display()

    def set_message(self, message: str):
        self.setText(message)
