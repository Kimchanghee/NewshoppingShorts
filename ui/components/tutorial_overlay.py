# -*- coding: utf-8 -*-
"""
Tutorial Overlay for PyQt6
"""
import sys
from typing import Optional, Callable, List, Dict, Any
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QApplication
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont

class TutorialOverlay(QWidget):
    STEPS: List[Dict[str, Any]] = [
        {"title": "1. URL 입력", "description": "영상 URL을 붙여넣으세요", "icon": "🔗", "target": "sidebar_menu_1"},
        {"title": "2. 스타일 선택", "description": "음성과 폰트 스타일을 선택하세요", "icon": "🎨", "target": "sidebar_menu_2"},
        {"title": "3. 작업 실행", "description": "작업을 시작하세요", "icon": "🚀", "target": "sidebar_menu_3"},
        {"title": "4. 설정", "description": "환경설정을 변경할 수 있습니다.", "icon": "⚙️", "target": "header_settings_button"},
    ]

    def __init__(self, parent_window, on_complete=None, on_skip=None):
        super().__init__()
        self.parent_window = parent_window
        self.on_complete = on_complete
        self.on_skip = on_skip
        self.current_step = 0
        self.bg_color = QColor(26, 26, 46, 200)
        self.border_color = QColor(227, 22, 57) # primary red
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
        
        # Step card
        card_w, card_h = 300, 200
        card_x = (self.width() - card_w) // 2
        card_y = (self.height() - card_h) // 2
        
        painter.setBrush(QBrush(Qt.GlobalColor.white))
        painter.drawRoundedRect(card_x, card_y, card_w, card_h, 12, 12)
        
        step = self.STEPS[self.current_step]
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.setFont(QFont("Malgun Gothic", 14, QFont.Weight.Bold))
        painter.drawText(QRect(card_x, card_y+20, card_w, 30), Qt.AlignmentFlag.AlignCenter, step["title"])
        
        painter.setFont(QFont("Malgun Gothic", 10))
        painter.drawText(QRect(card_x+20, card_y+60, card_w-40, 80), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, step["description"])
        
        # Placeholder for buttons
        painter.drawText(QRect(card_x, card_y+160, card_w, 30), Qt.AlignmentFlag.AlignCenter, "클릭하여 다음으로")

    def mousePressEvent(self, event):
        if self.current_step < len(self.STEPS) - 1:
            self.current_step += 1
            self.update()
        else:
            self.close()
            if self.on_complete: self.on_complete()
