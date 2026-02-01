"""
Rounded UI widgets for PyQt6 with theme support
Uses the design system v2 for consistent styling.
"""
import logging
from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QPushButton, QFrame, QLineEdit, QGraphicsDropShadowEffect,
    QHBoxLayout, QVBoxLayout, QLabel, QWidget
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor

from ui.design_system_v2 import get_design_system, get_color
from .base_widget import ThemedMixin

logger = logging.getLogger(__name__)


class RoundedButton(QPushButton, ThemedMixin):
    """Rounded button with theme support in PyQt6"""
    
    def __init__(
        self,
        parent=None,
        text="",
        command: Optional[Callable] = None,
        style: str = "primary",  # "primary", "secondary", "outline", "danger", "success"
        theme_manager=None,
        font=None,
        **kwargs
    ):
        super().__init__(text, parent)
        self.command = command
        self._style = style
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        
        if font:
            # Convert Tkinter font tuple to QFont if necessary
            if isinstance(font, tuple):
                qfont = QFont(font[0], font[1])
                if "bold" in font:
                    qfont.setBold(True)
                self.setFont(qfont)
            else:
                self.setFont(font)
        
        if command:
            self.clicked.connect(command)
            
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_theme()

    def apply_theme(self):
        primary = get_color('primary')
        secondary = get_color('secondary')
        text_primary = get_color('text_primary')
        error = get_color('error')
        success = get_color('success')
        surface_variant = get_color('surface_variant')
        border_light = get_color('border_light')
        
        # Get button size from design system
        btn_size = self.ds.get_button_size('md')
        
        style_sheet = ""
        if self._style == "primary":
            style_sheet = f"""
                QPushButton {{
                    background-color: {primary};
                    color: white;
                    border-radius: {self.ds.radius.base}px;
                    padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_4}px;
                    font-weight: bold;
                    border: none;
                    font-size: {self.ds.typography.size_sm}px;
                }}
                QPushButton:hover {{
                    background-color: {secondary};
                }}
                QPushButton:disabled {{
                    background-color: {get_color('text_muted')};
                }}
            """
        elif self._style == "secondary":
            style_sheet = f"""
                QPushButton {{
                    background-color: {surface_variant};
                    color: {text_primary};
                    border-radius: {self.ds.radius.base}px;
                    padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_4}px;
                    border: 1px solid {border_light};
                    font-size: {self.ds.typography.size_sm}px;
                }}
                QPushButton:hover {{
                    background-color: {border_light};
                }}
            """
        elif self._style == "outline":
            style_sheet = f"""
                QPushButton {{
                    background-color: transparent;
                    color: {primary};
                    border: 1px solid {primary};
                    border-radius: {self.ds.radius.base}px;
                    padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_4}px;
                    font-size: {self.ds.typography.size_sm}px;
                }}
                QPushButton:hover {{
                    background-color: {surface_variant};
                }}
            """
        elif self._style == "danger":
            style_sheet = f"""
                QPushButton {{
                    background-color: {get_color('background')};
                    color: {error};
                    border: 1px solid {error};
                    border-radius: {self.ds.radius.base}px;
                    padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_4}px;
                    font-size: {self.ds.typography.size_sm}px;
                }}
                QPushButton:hover {{
                    background-color: {error};
                    color: white;
                }}
            """
        
        self.setStyleSheet(style_sheet)


def create_rounded_button(parent, text, command, style="primary", gui=None, **kwargs):
    """Helper to create RoundedButton with compatible signature"""
    return RoundedButton(parent, text=text, command=command, style=style, **kwargs)


class RoundedFrame(QFrame, ThemedMixin):
    """Rounded frame with theme support in PyQt6"""
    
    def __init__(self, parent=None, radius=None, bg_key="surface", theme_manager=None, **kwargs):
        super().__init__(parent)
        self.ds = get_design_system()
        # Use design system radius if not specified
        self.radius = radius if radius is not None else self.ds.radius.lg
        self._bg_key = bg_key
        self.__init_themed__(theme_manager)
        self.apply_theme()

    def apply_theme(self):
        bg_color = get_color(self._bg_key)
        border_color = get_color('border_light')
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {self.radius}px;
            }}
        """)


class RoundedEntry(QLineEdit, ThemedMixin):
    """Rounded entry field with theme support in PyQt6"""
    
    def __init__(self, parent=None, theme_manager=None, **kwargs):
        super().__init__(parent)
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self.apply_theme()

    def apply_theme(self):
        bg = get_color('surface')
        fg = get_color('text_primary')
        border = get_color('border_light')
        focus = get_color('primary')
        
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {self.ds.radius.base}px;
                padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_3}px;
                font-size: {self.ds.typography.size_sm}px;
            }}
            QLineEdit:focus {{
                border: 2px solid {focus};
                background-color: {get_color('surface_variant')};
            }}
        """)
