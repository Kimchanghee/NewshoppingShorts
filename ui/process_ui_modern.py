# -*- coding: utf-8 -*-
"""
Modern Startup Check UI for PyQt6
"""
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QGridLayout,
    QLabel, QProgressBar, QScrollArea, QSizePolicy
)
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system, get_color
from ui.responsive import fit_window_to_available
from user_facing_errors import sanitize_user_message


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
        self.setMinimumHeight(52)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QGridLayout(self)
        layout.setContentsMargins(
            ds.spacing.space_3,  # 12px
            ds.spacing.space_1,  # 8px
            ds.spacing.space_3,  # 12px
            ds.spacing.space_1   # 8px
        )

        self.status_icon = QLabel(StatusIcon.WAITING)
        self.status_icon.setFixedWidth(28)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_icon, 0, 0, 2, 1)

        self.title_label = QLabel(f"{self.icon_emoji} {self.title_text}")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            f"font-size: {ds.typography.size_xs}px; "
            f"font-weight: {ds.typography.weight_bold}; "
            f"color: {get_color('text_secondary')};"
        )
        layout.addWidget(self.title_label, 0, 1)

        self.desc_label = QLabel(self.description_text)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(
            f"font-size: {ds.typography.size_2xs}px; "
            f"color: {get_color('text_muted')};"
        )
        layout.addWidget(self.desc_label, 1, 1, 1, 2)

        self.status_text = QLabel("대기")
        self.status_text.setMinimumWidth(64)
        self.status_text.setWordWrap(True)
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_text.setStyleSheet(
            f"font-size: {ds.typography.size_xs}px; "
            f"color: {get_color('text_muted')};"
        )
        layout.addWidget(self.status_text, 0, 2)
        layout.setColumnStretch(1, 1)
        
        self.setStyleSheet(
            f"background-color: {get_color('surface_variant')}; "
            f"border-radius: {ds.radius.base}px;"
        )

    def update_status(self, status, message=None):
        ds = get_design_system()
        icon_map = {
            "checking": StatusIcon.CHECKING,
            "success": StatusIcon.SUCCESS,
            "warning": StatusIcon.WARNING,
            "error": StatusIcon.ERROR
        }
        self.status_icon.setText(icon_map.get(status, StatusIcon.WAITING))
        status_fallback = {
            "checking": "확인 중...",
            "success": "정상",
            "warning": "확인 필요",
            "error": "오류",
        }.get(status, "대기")
        self.status_text.setText(
            sanitize_user_message(message, fallback=status_fallback)
            if message
            else status_fallback
        )
        
        # Use design system colors for status
        if status == "checking":
            color = get_color('primary')
        elif status == "success":
            color = get_color('success')
        elif status == "warning":
            color = get_color('warning')
        elif status == "error":
            color = get_color('error')
        else:
            color = get_color('text_muted')
        
        self.status_text.setStyleSheet(
            f"color: {color}; "
            f"font-size: {ds.typography.size_xs}px; "
            f"font-weight: {ds.typography.weight_bold};"
        )


class ModernProcessUi:
    def setupUi(self, window: QMainWindow):
        ds = get_design_system()
        fit_window_to_available(
            window,
            QtCore.QSize(620, 560),
            QtCore.QSize(360, 340),
        )
        window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.mainwidget = QWidget(window)
        self.frame = QFrame(self.mainwidget)
        self.frame.setStyleSheet(
            f"background-color: {get_color('background')}; "
            f"border-radius: {ds.radius.xl}px;"
        )

        root_layout = QVBoxLayout(self.mainwidget)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.addWidget(self.frame)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(0, 0, 0, 14)
        frame_layout.setSpacing(10)

        # Shadow removed for cleaner UI

        self.headerFrame = QFrame(self.frame)
        self.headerFrame.setMinimumHeight(82)
        self.headerFrame.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {get_color('primary')}, stop:1 {get_color('secondary')}); "
            f"border-radius: {ds.radius.xl}px;"
        )

        header_layout = QVBoxLayout(self.headerFrame)
        header_layout.setContentsMargins(18, 18, 18, 12)
        header_layout.addStretch(1)
        self.statusLabel = QLabel("시스템 점검 중...", self.headerFrame)
        self.statusLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setStyleSheet(
            f"color: white; "
            f"font-size: {ds.typography.size_sm}px;"
        )
        header_layout.addWidget(self.statusLabel)
        frame_layout.addWidget(self.headerFrame)

        checklist_scroll = QScrollArea(self.frame)
        checklist_scroll.setWidgetResizable(True)
        checklist_scroll.setFrameShape(QFrame.Shape.NoFrame)
        checklist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        checklist_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        checklist_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.checklistFrame = QFrame()
        layout = QVBoxLayout(self.checklistFrame)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(ds.spacing.space_2)  # 8px spacing between items
        
        self.checkItems = {}
        items_data = [
            ("system", "💻", "컴퓨터 환경", "사용 가능한 환경인지 확인"),
            ("fonts", "🔤", "자막 폰트", "영상에 사용할 폰트 준비"),
            ("ffmpeg", "🎬", "영상 편집 도구", "영상 변환·편집 기능 확인"),
            ("internet", "🌐", "인터넷 연결", "서비스 접속 상태 확인"),
            ("modules", "📦", "필수 기능", "프로그램 핵심 기능 확인"),
            ("ocr", "🔍", "자막 인식", "영상 속 자막 자동 인식 준비"),
            ("tts_dir", "🔊", "음성 저장소", "AI 음성 파일 저장 폴더 준비"),
            ("api", "🔗", "서버 연결", "서비스 서버 접속 확인"),
            ("update_check", "🔔", "업데이트 확인", "새로운 버전이 있는지 확인"),
        ]
        for item_id, icon, title, desc in items_data:
            item = ChecklistItem(item_id, icon, title, desc)
            self.checkItems[item_id] = item
            layout.addWidget(item)
        layout.addStretch(1)
        checklist_scroll.setWidget(self.checklistFrame)
        frame_layout.addWidget(checklist_scroll, 1)

        progress_row = QGridLayout()
        progress_row.setContentsMargins(20, 0, 20, 0)
        progress_row.setHorizontalSpacing(10)
        self.progressBar = QProgressBar(self.frame)
        self.progressBar.setMinimumHeight(14)
        self.progressBar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {get_color('surface_variant')};
                border-radius: {ds.radius.sm}px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {get_color('primary')};
                border-radius: {ds.radius.sm}px;
            }}
        """)
        progress_row.addWidget(self.progressBar, 0, 0)
        
        self.percentLabel = QLabel("0%", self.frame)
        self.percentLabel.setMinimumWidth(48)
        self.percentLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.percentLabel.setStyleSheet(
            f"font-size: {ds.typography.size_sm}px; "
            f"color: {get_color('text_secondary')};"
        )
        progress_row.addWidget(self.percentLabel, 0, 1)
        progress_row.setColumnStretch(0, 1)
        frame_layout.addLayout(progress_row)

        window.setCentralWidget(self.mainwidget)

    def updateCheckItem(self, item_id, status, message=None):
        if item_id in self.checkItems:
            self.checkItems[item_id].update_status(status, message)

    def setProgress(self, value):
        self.progressBar.setValue(value)
        self.percentLabel.setText(f"{value}%")


Process_Ui = ModernProcessUi
