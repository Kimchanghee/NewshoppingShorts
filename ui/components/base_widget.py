"""
Base widgets for PyQt6 with theme support
Uses the design system v2 for consistent styling.
"""
import logging
from typing import Optional, List, Callable
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QLineEdit, QTextEdit, QCheckBox, QRadioButton
from PyQt6.QtCore import pyqtSignal, QObject, Qt
from PyQt6.QtGui import QColor, QPalette

from ui.design_system_v2 import get_design_system, get_color, set_dark_mode, is_dark_mode

logger = logging.getLogger(__name__)


class ThemedMixin:
    """
    Mixin class for theme support in PyQt6 using Design System V2
    """
    def __init_themed__(self, theme_manager=None):
        """
        Initialize themed mixin.
        Note: theme_manager parameter is kept for backward compatibility but not used.
        """
        self.ds = get_design_system()
        self._themed_children = []

    def get_color(self, key: str) -> str:
        """Get color from design system v2"""
        # Map old theme keys to new design system keys
        key_mapping = {
            'bg_main': 'background',
            'bg_card': 'surface',
            'bg_secondary': 'surface_variant',
            'bg_input': 'surface',
            'bg_hover': 'surface_variant',
            'text_primary': 'text_primary',
            'text_secondary': 'text_secondary',
            'text_muted': 'text_muted',
            'text_disabled': 'text_muted',
            'primary': 'primary',
            'primary_hover': 'secondary',
            'primary_text': 'surface',
            'secondary': 'secondary',
            'border_light': 'border_light',
            'border': 'border',
            'border_focus': 'primary',
            'success': 'success',
            'success_bg': 'surface',
            'error': 'error',
            'error_bg': 'surface_variant',
            'warning': 'warning',
            'info': 'info',
            'btn_secondary': 'surface_variant',
            'btn_secondary_hover': 'surface_variant',
            'btn_secondary_text': 'text_primary',
        }
        mapped_key = key_mapping.get(key, key)
        return get_color(mapped_key)

    @property
    def theme_manager(self):
        """Return self for compatibility"""
        return self

    @property
    def is_dark_mode(self) -> bool:
        return is_dark_mode()

    def set_dark_mode(self, enabled: bool) -> None:
        """Set dark mode"""
        set_dark_mode(enabled)
        self._on_theme_changed("dark" if enabled else "light")

    def _on_theme_changed(self, new_theme: str) -> None:
        self.apply_theme()

    def apply_theme(self) -> None:
        """Override in subclasses to apply specific styles"""
        pass

    def cleanup_theme(self) -> None:
        """Cleanup - no-op for design system v2"""
        pass

    def register_observer(self, callback):
        """No-op for backward compatibility"""
        pass

    def unregister_observer(self, callback):
        """No-op for backward compatibility"""
        pass


class ThemedFrame(QFrame, ThemedMixin):
    def __init__(self, parent=None, theme_manager=None, bg_key="surface", **kwargs):
        super().__init__(parent)
        self.ds = get_design_system()
        self._bg_key = bg_key
        self.__init_themed__(theme_manager)
        self.apply_theme()

    def apply_theme(self):
        bg_color = self.get_color(self._bg_key)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: none;
                border-radius: {self.ds.border_radius.radius_base}px;
            }}
        """)


class ThemedLabel(QLabel, ThemedMixin):
    def __init__(self, parent=None, theme_manager=None, bg_key="transparent", fg_key="text_primary", **kwargs):
        super().__init__(parent)
        self.ds = get_design_system()
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
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: none;
                font-family: {self.ds.typography.font_family_primary};
            }}
        """)


class ThemedButton(QPushButton, ThemedMixin):
    def __init__(self, parent=None, theme_manager=None, style="primary", **kwargs):
        super().__init__(parent)
        self.ds = get_design_system()
        self._style = style
        self.__init_themed__(theme_manager)
        text = kwargs.get('text', '')
        if text:
            self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_theme()

    def apply_theme(self):
        primary = self.get_color("primary")
        primary_hover = self.get_color("secondary")
        primary_text = self.get_color("surface")
        bg_secondary = self.get_color("surface_variant")
        bg_hover = self.get_color("border_light")
        text_primary = self.get_color("text_primary")

        if self._style == "primary":
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {primary};
                    color: {primary_text};
                    border-radius: {self.ds.border_radius.radius_base}px;
                    padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_4}px;
                    font-weight: bold;
                    font-size: {self.ds.typography.size_sm}px;
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
                    border-radius: {self.ds.border_radius.radius_base}px;
                    padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_4}px;
                    font-size: {self.ds.typography.size_sm}px;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                }}
            """)
        else:  # text/ghost
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {primary};
                    border-radius: {self.ds.border_radius.radius_base}px;
                    padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_4}px;
                    font-size: {self.ds.typography.size_sm}px;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                }}
            """)
