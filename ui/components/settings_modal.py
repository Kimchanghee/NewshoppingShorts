"""
Settings modal placeholder (PyQt6)
Uses the design system v2 for consistent styling.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from ui.design_system_v2 import get_design_system, get_color


class SettingsModal(QDialog):
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.ds = get_design_system()
        
        self.setWindowTitle("설정")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6
        )
        layout.setSpacing(self.ds.spacing.space_4)
        
        label = QLabel("Settings modal (PyQt6 placeholder)", self)
        label.setStyleSheet(f"""
            QLabel {{
                color: {get_color('text_primary')};
                font-size: {self.ds.typography.size_base}px;
                font-family: {self.ds.typography.font_family_primary};
            }}
        """)
        layout.addWidget(label)
