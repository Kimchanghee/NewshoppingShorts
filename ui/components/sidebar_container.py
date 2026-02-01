"""
Sidebar container module for PyQt6
Uses the design system v2 for consistent styling.
"""
from typing import Dict, Optional, List, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QScrollArea, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ui.design_system_v2 import get_design_system, get_color


class SidebarMenuItem(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, name: str, text: str, step_number: int, icon: str = "", parent=None):
        super().__init__(parent)
        self._name = name
        self._text = text
        self._step_number = step_number
        self._icon = icon
        self._active = False
        self._completed = False
        self.ds = get_design_system()
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(self.ds.spacing.space_14)  # 56px
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self.ds.spacing.space_3,
            0,
            self.ds.spacing.space_3,
            0
        )
        layout.setSpacing(self.ds.spacing.space_3)

        # Step number circle
        self.circle_label = QLabel(str(self._step_number))
        self.circle_label.setFixedSize(28, 28)
        self.circle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.circle_label.setStyleSheet(f"border-radius: 14px; font-weight: bold;")
        layout.addWidget(self.circle_label)

        # Text
        self.title_label = QLabel(self._text)
        self.title_label.setStyleSheet(f"font-size: {self.ds.typography.size_sm}px; font-weight: bold;")
        layout.addWidget(self.title_label)
        layout.addStretch()
        
        self.update_style()

    def update_style(self):
        # Get colors from design system
        primary = get_color('primary')
        text_secondary = get_color('text_secondary')
        border_light = get_color('border_light')
        surface_variant = get_color('surface_variant')
        
        bg = surface_variant if self._active else "transparent"
        text_color = primary if self._active else text_secondary
        circle_bg = primary if self._active or self._completed else border_light
        circle_text = get_color('surface') if self._active or self._completed else text_secondary
        
        self.setStyleSheet(f"background-color: {bg}; border-radius: {self.ds.radius.base}px;")
        self.title_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        self.circle_label.setStyleSheet(f"background-color: {circle_bg}; color: {circle_text}; border-radius: 14px; font-weight: bold;")
        
        if self._completed:
            self.circle_label.setText("✓")
        else:
            self.circle_label.setText(str(self._step_number))

    def set_active(self, active: bool):
        self._active = active
        self.update_style()

    def set_completed(self, completed: bool):
        self._completed = completed
        self.update_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self._name)
        super().mousePressEvent(event)


class SidebarProgressMini(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(120)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.ds.spacing.space_4,
            self.ds.spacing.space_3,
            self.ds.spacing.space_4,
            self.ds.spacing.space_3
        )
        
        title = QLabel("제작 진행")
        title.setStyleSheet(f"font-weight: bold; color: {get_color('text_primary')};")
        layout.addWidget(title)
        
        self.status_label = QLabel("대기 중")
        self.status_label.setStyleSheet(f"color: {get_color('text_secondary')}; font-size: {self.ds.typography.size_xs}px;")
        layout.addWidget(self.status_label)
        
        self.progress_label = QLabel("0%")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet(f"font-size: {self.ds.typography.size_lg}px; font-weight: bold; color: {get_color('primary')};")
        layout.addWidget(self.progress_label)

    def update_status(self, status: str):
        self.status_label.setText(status)

    def update_progress(self, progress: int):
        self.progress_label.setText(f"{progress}%")


class SidebarContainer(QWidget):
    def __init__(self, parent=None, sidebar_width=None, gui=None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._sidebar_width = sidebar_width if sidebar_width is not None else 240
        self._gui = gui
        self._menu_items: Dict[str, SidebarMenuItem] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setFixedWidth(self._sidebar_width)
        self.sidebar_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {get_color('surface')};
                border-right: 1px solid {get_color('border_light')};
            }}
        """)
        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setContentsMargins(
            self.ds.spacing.space_2,
            self.ds.spacing.space_4,
            self.ds.spacing.space_2,
            self.ds.spacing.space_4
        )
        
        self.menu_container = QWidget()
        self.menu_layout = QVBoxLayout(self.menu_container)
        self.menu_layout.setContentsMargins(0, 0, 0, 0)
        self.menu_layout.setSpacing(self.ds.spacing.space_1)
        sidebar_layout.addWidget(self.menu_container)
        
        sidebar_layout.addStretch()
        
        self.progress_mini = SidebarProgressMini()
        sidebar_layout.addWidget(self.progress_mini)
        
        layout.addWidget(self.sidebar_frame)

        # Content
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)
        
        # Accessor for legacy code
        self.content_frame = self.content_stack 

    def add_menu_item(self, name: str, label: str, content_widget: QWidget, step_number: int, icon: str = ""):
        item = SidebarMenuItem(name, label, step_number, icon)
        item.clicked.connect(self.select_menu)
        self.menu_layout.addWidget(item)
        self._menu_items[name] = item
        self.content_stack.addWidget(content_widget)
        
        if len(self._menu_items) == 1:
            self.select_menu(name)

    def select_menu(self, name: str):
        for menu_name, item in self._menu_items.items():
            item.set_active(menu_name == name)
        
        # Assuming widgets are added in the same order as items for simplicity
        idx = list(self._menu_items.keys()).index(name)
        self.content_stack.setCurrentIndex(idx)

    def mark_step_completed(self, name: str, completed: bool = True):
        if name in self._menu_items:
            self._menu_items[name].set_completed(completed)
