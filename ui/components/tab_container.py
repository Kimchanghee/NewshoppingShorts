"""
Tab container components for PyQt6
"""
from typing import Dict, Optional, List, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QStackedWidget, QFrame, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal
from .base_widget import ThemedMixin

class TabButton(QPushButton, ThemedMixin):
    """Custom tab button for PyQt6"""
    
    def __init__(self, parent, text, icon="", theme_manager=None):
        super().__init__(parent)
        self._text = text
        self._icon = icon
        self._active = False
        self.__init_themed__(theme_manager)
        
        display_text = f"{icon} {text}" if icon else text
        self.setText(display_text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_theme()

    def set_active(self, active: bool):
        self._active = active
        self.apply_theme()

    def apply_theme(self):
        bg = self.get_color("bg_card") if self._active else "transparent"
        fg = self.get_color("tab_active") if self._active else self.get_color("tab_inactive")
        font_weight = "bold" if self._active else "normal"
        border_bottom = f"3px solid {self.get_color('tab_indicator')}" if self._active else "none"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: none;
                border-bottom: {border_bottom};
                padding: 10px 20px;
                font-size: 14px;
                font-weight: {font_weight};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {self.get_color("bg_hover")};
            }}
        """)

class TabContainer(QWidget, ThemedMixin):
    """Themed Tab Container for PyQt6"""
    
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.__init_themed__(theme_manager)
        
        self._tabs: Dict[str, QWidget] = {}
        self._tab_buttons: Dict[str, TabButton] = {}
        self._current_tab_name = None
        
        self.create_layout()
        self.apply_theme()

    def create_layout(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header area
        self.header_frame = QFrame()
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(16, 0, 16, 0)
        self.header_layout.setSpacing(4)
        
        # Tab Buttons Container
        self.button_container = QWidget()
        self.button_layout = QHBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(4)
        self.header_layout.addWidget(self.button_container)
        
        self.header_layout.addStretch()
        
        # Header Right (for extra buttons like theme toggle)
        self.header_right = QWidget()
        self.header_right_layout = QHBoxLayout(self.header_right)
        self.header_right_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.addWidget(self.header_right)
        
        self.main_layout.addWidget(self.header_frame)
        
        # Separator line
        self.separator = QFrame()
        self.separator.setFixedHeight(1)
        self.main_layout.addWidget(self.separator)
        
        # Content Area
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

    def add_tab(self, name, label, content_widget, icon="", select=False):
        self._tabs[name] = content_widget
        self.stack.addWidget(content_widget)
        
        btn = TabButton(self.button_container, label, icon, self.theme_manager)
        btn.clicked.connect(lambda: self.select_tab(name))
        self.button_layout.addWidget(btn)
        self._tab_buttons[name] = btn
        
        if len(self._tabs) == 1 or select:
            self.select_tab(name)

    def select_tab(self, name):
        if name not in self._tabs: return
        
        self._current_tab_name = name
        self.stack.setCurrentWidget(self._tabs[name])
        
        for tab_name, btn in self._tab_buttons.items():
            btn.set_active(tab_name == name)

    def apply_theme(self):
        self.setStyleSheet(f"background-color: {self.get_color('bg_main')};")
        self.header_frame.setStyleSheet(f"background-color: {self.get_color('bg_header')}; border: none;")
        self.separator.setStyleSheet(f"background-color: {self.get_color('border_light')};")
        
        for btn in self._tab_buttons.values():
            btn.apply_theme()

class TabContent(QWidget, ThemedMixin):
    """Themed Tab Content for PyQt6"""
    
    def __init__(self, parent=None, theme_manager=None, padding=(20, 16)):
        super().__init__(parent)
        self._padding = padding
        self.__init_themed__(theme_manager)
        
        # Use a layout for inner container
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(padding[0], padding[1], padding[0], padding[1])
        
        # The 'inner' reference for compatibility
        self.inner = QWidget()
        self.inner_layout = QVBoxLayout(self.inner)
        self.inner_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.inner)
        
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(f"background-color: {self.get_color('bg_main')}; border: none;")
