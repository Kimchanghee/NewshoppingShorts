"""
Theme toggle placeholder (PyQt6).
Uses the design system v2 for consistent styling.
"""
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import pyqtSignal
from ui.design_system_v2 import get_design_system, get_color, set_dark_mode


class ThemeToggle(QPushButton):
    toggled = pyqtSignal(str)
    
    def __init__(self, parent=None, theme_manager=None, on_toggle=None):
        super().__init__("🌓", parent)
        self.ds = get_design_system()
        self._theme = "light"
        
        if on_toggle:
            self.toggled.connect(on_toggle)
        self.clicked.connect(self._handle_click)
        
        # Apply initial styling
        self.apply_theme()

    def _handle_click(self):
        self._theme = "dark" if self._theme == "light" else "light"
        # Update design system dark mode
        set_dark_mode(self._theme == "dark")
        self.toggled.emit(self._theme)
        self.apply_theme()

    def apply_theme(self):
        """Apply design system colors to the toggle button"""
        text_color = get_color('text_primary')
        surface_variant = get_color('surface_variant')
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {surface_variant};
                border: 1px solid {get_color('border_light')};
                border-radius: {self.ds.radius.full}px;
                padding: {self.ds.spacing.space_2}px;
                font-size: {self.ds.typography.size_base}px;
                color: {text_color};
            }}
            QPushButton:hover {{
                background-color: {get_color('border_light')};
            }}
        """)


class ThemeToggleButton(ThemeToggle):
    pass


class ThemeIconButton(ThemeToggle):
    pass
