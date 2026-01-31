"""
Rounded UI widgets for PyQt6 with theme support
"""
import logging
from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QPushButton, QFrame, QLineEdit, QGraphicsDropShadowEffect,
    QHBoxLayout, QVBoxLayout, QLabel, QWidget
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor

from .base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager

logger = logging.getLogger(__name__)

class RoundedButton(QPushButton, ThemedMixin):
    """Rounded button with theme support in PyQt6"""
    
    def __init__(
        self,
        parent=None,
        text="",
        command: Optional[Callable] = None,
        style: str = "primary",  # "primary", "secondary", "outline", "danger", "success"
        theme_manager: Optional[ThemeManager] = None,
        font=None,
        **kwargs
    ):
        super().__init__(text, parent)
        self.command = command
        self._style = style
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
        primary = self.get_color("primary")
        primary_hover = self.get_color("primary_hover")
        primary_text = self.get_color("primary_text")
        bg_secondary = self.get_color("bg_secondary")
        bg_hover = self.get_color("bg_hover")
        text_primary = self.get_color("text_primary")
        error_bg = self.get_color("error_bg")
        error = self.get_color("error")
        success_bg = self.get_color("success_bg")
        success = self.get_color("success")
        
        style_sheet = ""
        if self._style == "primary":
            style_sheet = f"""
                QPushButton {{
                    background-color: {primary};
                    color: {primary_text};
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: bold;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {primary_hover};
                }}
                QPushButton:disabled {{
                    background-color: {self.get_color("text_disabled")};
                }}
            """
        elif self._style == "secondary":
            style_sheet = f"""
                QPushButton {{
                    background-color: {bg_secondary};
                    color: {text_primary};
                    border-radius: 8px;
                    padding: 8px 16px;
                    border: 1px solid {self.get_color("border_light")};
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                }}
            """
        elif self._style == "outline":
            style_sheet = f"""
                QPushButton {{
                    background-color: transparent;
                    color: {primary};
                    border: 1px solid {primary};
                    border-radius: 8px;
                    padding: 8px 16px;
                }}
                QPushButton:hover {{
                    background-color: {self.get_color("primary_light")};
                }}
            """
        elif self._style == "danger":
            style_sheet = f"""
                QPushButton {{
                    background-color: {error_bg};
                    color: {error};
                    border: 1px solid {error};
                    border-radius: 8px;
                    padding: 8px 16px;
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
    
    def __init__(self, parent=None, radius=12, bg_key="bg_card", theme_manager=None, **kwargs):
        super().__init__(parent)
        self.radius = radius
        self._bg_key = bg_key
        self.__init_themed__(theme_manager)
        self.apply_theme()

    def apply_theme(self):
        bg_color = self.get_color(self._bg_key)
        border_color = self.get_color("border_light")
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
        self.__init_themed__(theme_manager)
        self.apply_theme()

    def apply_theme(self):
        bg = self.get_color("bg_input")
        fg = self.get_color("text_primary")
        border = self.get_color("border_light")
        focus = self.get_color("border_focus")
        
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QLineEdit:focus {{
                border: 2px solid {focus};
                background-color: white;
            }}
        """)
