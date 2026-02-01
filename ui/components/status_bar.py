"""
Status bar component for PyQt6
Uses the design system v2 for consistent styling.
"""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from ui.design_system_v2 import get_design_system, get_color


class StatusBar(QLabel):
    def __init__(self, parent=None, gui=None):
        super().__init__(parent)
        self.ds = get_design_system()
        self.gui = gui
        
        self.setText("준비 완료")
        self.setStyleSheet(f"""
            QLabel {{
                color: {get_color('text_secondary')};
                font-size: {self.ds.typography.size_xs}px;
                padding: {self.ds.spacing.space_1}px {self.ds.spacing.space_3}px;
                background-color: {get_color('surface')};
                border-top: 1px solid {get_color('border_light')};
            }}
        """)
        self.setFixedHeight(self.ds.spacing.space_6)
        
        if gui:
            gui.status_bar = self
            # Initial refresh if method exists
            if hasattr(gui, 'refresh_voice_status_display'):
                gui.refresh_voice_status_display()

    def set_message(self, message: str):
        self.setText(message)
