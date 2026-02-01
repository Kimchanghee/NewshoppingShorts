"""
Settings button for PyQt6
Uses the design system v2 for consistent styling.
"""
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from ui.design_system_v2 import get_design_system, get_color


class SettingsButton(QPushButton):
    def __init__(self, parent=None, on_click=None, theme_manager=None, size=None):
        super().__init__("⚙️", parent)
        self.ds = get_design_system()
        
        # Use design system spacing if size not specified
        if size is None:
            size = self.ds.spacing.space_9  # 36px
        
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Get colors from design system
        text_muted = get_color('text_muted')
        surface_variant = get_color('surface_variant')
        text_primary = get_color('text_primary')
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                font-size: {self.ds.typography.size_lg}px;
                color: {text_muted};
            }}
            QPushButton:hover {{
                background-color: {surface_variant};
                border-radius: {self.ds.border_radius.radius_full}px;
                color: {text_primary};
            }}
        """)
        if on_click:
            self.clicked.connect(on_click)
