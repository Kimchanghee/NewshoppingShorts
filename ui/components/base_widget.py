"""
Base widgets for PyQt6 with theme support
"""
import logging
from typing import Optional, List, Callable
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QLineEdit, QTextEdit, QCheckBox, QRadioButton
from PyQt6.QtCore import pyqtSignal, QObject, Qt
from PyQt6.QtGui import QColor, QPalette

from ..theme_manager import ThemeManager, get_theme_manager

logger = logging.getLogger(__name__)

class ThemedMixin:
    """
    Mixin class for theme support in PyQt6
    """
    def __init_themed__(self, theme_manager: Optional[ThemeManager] = None):
        self._theme_manager = theme_manager or get_theme_manager()
        self._theme_manager.register_observer(self._on_theme_changed)
        self._themed_children = []

    def get_color(self, key: str) -> str:
        return self._theme_manager.get_color(key)

    @property
    def theme_manager(self) -> ThemeManager:
        return self._theme_manager

    @property
    def is_dark_mode(self) -> bool:
        return self._theme_manager.is_dark_mode

    def _on_theme_changed(self, new_theme: str) -> None:
        self.apply_theme()

    def apply_theme(self) -> None:
        """Override in subclasses to apply specific styles"""
        pass

    def cleanup_theme(self) -> None:
        try:
            self._theme_manager.unregister_observer(self._on_theme_changed)
        except Exception:
            pass

class ThemedFrame(QFrame, ThemedMixin):
    def __init__(self, parent=None, theme_manager=None, bg_key="bg_card", **kwargs):
        super().__init__(parent)
        self._bg_key = bg_key
        self.__init_themed__(theme_manager)
        self.apply_theme()

    def apply_theme(self):
        bg_color = self.get_color(self._bg_key)
        self.setStyleSheet(f"background-color: {bg_color}; border: none;")

class ThemedLabel(QLabel, ThemedMixin):
    def __init__(self, parent=None, theme_manager=None, bg_key="transparent", fg_key="text_primary", **kwargs):
        super().__init__(parent)
        self._bg_key = bg_key
        self._fg_key = fg_key
        self.__init_themed__(theme_manager)
        text = kwargs.get('text', '')
        if text:
            self.setText(text)
        self.apply_theme()

    def apply_theme(self):
        bg = self.get_color(self._bg_key) if self._bg_key != "transparent" else "transparent"
        fg = self.get_color(self._fg_key)
        self.setStyleSheet(f"background-color: {bg}; color: {fg}; border: none;")

class ThemedButton(QPushButton, ThemedMixin):
    def __init__(self, parent=None, theme_manager=None, style="primary", **kwargs):
        super().__init__(parent)
        self._style = style
        self.__init_themed__(theme_manager)
        text = kwargs.get('text', '')
        if text:
            self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_theme()

    def apply_theme(self):
        primary = self.get_color("primary")
        primary_hover = self.get_color("primary_hover")
        primary_text = self.get_color("primary_text")
        bg_secondary = self.get_color("bg_secondary")
        bg_hover = self.get_color("bg_hover")
        text_primary = self.get_color("text_primary")

        if self._style == "primary":
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {primary};
                    color: {primary_text};
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {primary_hover};
                }}
            """)
        elif self._style == "secondary":
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_secondary};
                    color: {text_primary};
                    border-radius: 8px;
                    padding: 8px 16px;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                }}
            """)
        else: # text/ghost
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {primary};
                    border-radius: 8px;
                    padding: 8px 16px;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                }}
            """)
