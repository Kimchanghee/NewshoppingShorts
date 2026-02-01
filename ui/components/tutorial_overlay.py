# -*- coding: utf-8 -*-
"""
Tutorial Overlay for PyQt6
Uses the design system v2 for consistent styling.
"""
import sys
from typing import Optional, Callable, List, Dict, Any
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QApplication
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont

from ui.design_system_v2 import get_design_system, get_color


class TutorialOverlay(QWidget):
    STEPS: List[Dict[str, Any]] = [
        {"title": "1. URL 입력", "description": "영상 URL을 붙여넣으세요", "icon": "🔗", "target": "sidebar_menu_1"},
        {"title": "2. 스타일 선택", "description": "음성과 폰트 스타일을 선택하세요", "icon": "🎨", "target": "sidebar_menu_2"},
        {"title": "3. 작업 실행", "description": "작업을 시작하세요", "icon": "🚀", "target": "sidebar_menu_3"},
        {"title": "4. 설정", "description": "환경설정을 변경할 수 있습니다.", "icon": "⚙️", "target": "header_settings_button"},
    ]

    def __init__(self, parent_window, on_complete=None, on_skip=None):
        super().__init__()
        self.ds = get_design_system()
        self.parent_window = parent_window
        self.on_complete = on_complete
        self.on_skip = on_skip
        self.current_step = 0
        
        # Use design system colors
        self.bg_color = QColor(get_color('background'))
        self.bg_color.setAlpha(200)
        self.border_color = QColor(get_color('primary'))
        
        self._setup_window()
        self._sync_position()

    def _setup_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _sync_position(self):
        if self.parent_window:
            self.setGeometry(self.parent_window.geometry())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dim background
        painter.setBrush(QBrush(self.bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())
        
        # Step card dimensions
        card_w, card_h = 300, 200
        card_x = (self.width() - card_w) // 2
        card_y = (self.height() - card_h) // 2
        
        # Draw card with design system colors
        painter.setBrush(QBrush(QColor(get_color('surface'))))
        painter.drawRoundedRect(
            card_x, card_y, card_w, card_h,
            self.ds.radius.md,
            self.ds.radius.md
        )
        
        step = self.STEPS[self.current_step]
        painter.setPen(QPen(QColor(get_color('text_primary'))))
        
        # Title with design system font
        title_font = QFont(self.ds.typography.font_family_primary, self.ds.typography.size_lg, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(
            QRect(card_x, card_y + self.ds.spacing.space_5, card_w, self.ds.spacing.space_7),
            Qt.AlignmentFlag.AlignCenter,
            step["title"]
        )
        
        # Description with design system font
        desc_font = QFont(self.ds.typography.font_family_primary, self.ds.typography.size_sm)
        painter.setFont(desc_font)
        painter.drawText(
            QRect(
                card_x + self.ds.spacing.space_5,
                card_y + self.ds.spacing.space_15,
                card_w - self.ds.spacing.space_10,
                self.ds.spacing.space_20
            ),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            step["description"]
        )
        
        # Placeholder for buttons
        hint_font = QFont(self.ds.typography.font_family_primary, self.ds.typography.size_xs)
        painter.setFont(hint_font)
        painter.setPen(QPen(QColor(get_color('text_secondary'))))
        painter.drawText(
            QRect(card_x, card_y + 160, card_w, self.ds.spacing.space_7),
            Qt.AlignmentFlag.AlignCenter,
            "클릭하여 다음으로"
        )

    def mousePressEvent(self, event):
        if self.current_step < len(self.STEPS) - 1:
            self.current_step += 1
            self.update()
        else:
            self.close()
            if self.on_complete:
                self.on_complete()
