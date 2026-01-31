"""
Theme toggle placeholder (PyQt6).
"""
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import pyqtSignal

class ThemeToggle(QPushButton):
    toggled = pyqtSignal(str)
    def __init__(self, parent=None, theme_manager=None, on_toggle=None):
        super().__init__("🌓", parent)
        self._theme = "light"
        if on_toggle:
            self.toggled.connect(on_toggle)
        self.clicked.connect(self._handle_click)

    def _handle_click(self):
        self._theme = "dark" if self._theme == "light" else "light"
        self.toggled.emit(self._theme)

    def apply_theme(self):
        pass

class ThemeToggleButton(ThemeToggle):
    pass

class ThemeIconButton(ThemeToggle):
    pass
