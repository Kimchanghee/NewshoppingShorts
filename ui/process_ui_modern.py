# -*- coding: utf-8 -*-
"""
Modern Startup Check UI for PyQt6
"""
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QFont, QColor

from ui.design_system import get_design_system

class StatusIcon:
    WAITING = "⏳"
    CHECKING = "🔄"
    SUCCESS = "✅"
    WARNING = "⚠️"
    ERROR = "❌"

class ChecklistItem(QFrame):
    def __init__(self, item_id, icon_emoji, title, description, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.icon_emoji = icon_emoji
        self.title_text = title
        self.description_text = description
        self._setup_ui()

    def _setup_ui(self):
        ds = get_design_system()
        c = ds.colors
        self.setFixedHeight(42)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        self.status_icon = QLabel(StatusIcon.WAITING)
        self.status_icon.setFixedWidth(28)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_icon)

        self.title_label = QLabel(f"{self.icon_emoji} {self.title_text}")
        self.title_label.setFixedWidth(180)
        self.title_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {c.text_secondary};")
        layout.addWidget(self.title_label)

        self.desc_label = QLabel(self.description_text)
        self.desc_label.setStyleSheet(f"font-size: 11px; color: {c.text_disabled};")
        layout.addWidget(self.desc_label, 1)

        self.status_text = QLabel("대기")
        self.status_text.setFixedWidth(70)
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.status_text)
        
        self.setStyleSheet(f"background-color: {c.bg_secondary}; border-radius: 8px;")

    def update_status(self, status, message=None):
        ds = get_design_system()
        c = ds.colors
        icon_map = {"checking": StatusIcon.CHECKING, "success": StatusIcon.SUCCESS, "warning": StatusIcon.WARNING, "error": StatusIcon.ERROR}
        self.status_icon.setText(icon_map.get(status, StatusIcon.WAITING))
        self.status_text.setText(message or (status if status != "checking" else "확인 중..."))
        
        # Simple theme update for status
        color = c.primary if status == "checking" else "#16A34A" if status == "success" else "#D97706" if status == "warning" else "#DC2626"
        self.status_text.setStyleSheet(f"color: {color}; font-weight: bold;")

class ModernProcessUi:
    def setupUi(self, window: QMainWindow):
        ds = get_design_system()
        c = ds.colors
        window.resize(620, 560)
        window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.mainwidget = QWidget(window)
        self.frame = QFrame(self.mainwidget)
        self.frame.setGeometry(QtCore.QRect(10, 10, 600, 540))
        self.frame.setStyleSheet(f"background-color: {c.bg_main}; border-radius: 20px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.frame.setGraphicsEffect(shadow)

        self.headerFrame = QFrame(self.frame)
        self.headerFrame.setGeometry(QtCore.QRect(0, 0, 600, 90))
        self.headerFrame.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c.gradient_start}, stop:1 {c.gradient_end}); border-radius: 20px;")

        self.statusLabel = QLabel("시스템 점검 중...", self.headerFrame)
        self.statusLabel.setGeometry(QtCore.QRect(0, 50, 600, 30))
        self.statusLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.statusLabel.setStyleSheet("color: white; font-size: 13px;")

        self.checklistFrame = QFrame(self.frame)
        self.checklistFrame.setGeometry(QtCore.QRect(20, 105, 560, 360))
        layout = QVBoxLayout(self.checklistFrame)
        
        self.checkItems = {}
        items_data = [
            ("system", "💻", "시스템 환경", "컴퓨터 성능 확인"),
            ("fonts", "🔤", "폰트 확인", "자막용 폰트"),
            ("ffmpeg", "🎬", "영상 처리", "영상 변환 엔진"),
            ("internet", "🌐", "인터넷 연결", "서비스 연결용"),
            ("modules", "📦", "핵심 모듈", "확인 중..."),
            ("ocr", "🔍", "자막 인식", "중국어 자막 인식"),
            ("tts_dir", "📁", "음성 폴더", "음성 저장 폴더 준비"),
            ("api", "🔗", "서비스 준비", "서비스 연결"),
        ]
        for item_id, icon, title, desc in items_data:
            item = ChecklistItem(item_id, icon, title, desc)
            self.checkItems[item_id] = item
            layout.addWidget(item)

        self.progressBar = QProgressBar(self.frame)
        self.progressBar.setGeometry(QtCore.QRect(20, 480, 560, 14))
        self.percentLabel = QLabel("0%", self.frame)
        self.percentLabel.setGeometry(QtCore.QRect(530, 500, 50, 20))

        window.setCentralWidget(self.mainwidget)

    def updateCheckItem(self, item_id, status, message=None):
        if item_id in self.checkItems:
            self.checkItems[item_id].update_status(status, message)

    def setProgress(self, value):
        self.progressBar.setValue(value)
        self.percentLabel.setText(f"{value}%")

Process_Ui = ModernProcessUi
