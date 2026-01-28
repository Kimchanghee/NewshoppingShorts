# -*- coding: utf-8 -*-
"""
Modern Startup Check UI for Shopping Shorts Maker
쇼핑 숏폼 메이커 모던 시작 점검 UI

STITCH MCP 디자인 기반 리팩토링
기존 기능 100% 보존 + 모던 UI/UX 적용
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QGraphicsDropShadowEffect
)
from PyQt5.QtGui import QFont, QColor, QPainter, QLinearGradient

from ui.design_system import get_design_system, get_color


class StatusIcon:
    """상태별 아이콘 정의"""
    WAITING = "⏳"
    CHECKING = "🔄"
    SUCCESS = "✅"
    WARNING = "⚠️"
    ERROR = "❌"


class ChecklistItem(QFrame):
    """
    점검 항목 위젯
    Checklist item widget with animated status updates
    """

    def __init__(
        self,
        item_id: str,
        icon_emoji: str,
        title: str,
        description: str,
        parent=None
    ):
        super().__init__(parent)
        self.item_id = item_id
        self.icon_emoji = icon_emoji
        self.title_text = title
        self.description_text = description
        self._status = "waiting"

        self._setup_ui()
        self._apply_waiting_style()

    def _setup_ui(self):
        ds = get_design_system()
        c = ds.colors

        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # 상태 아이콘
        self.status_icon = QLabel(StatusIcon.WAITING)
        self.status_icon.setFixedWidth(28)
        self.status_icon.setAlignment(Qt.AlignCenter)
        self.status_icon.setStyleSheet("font-size: 14px; background: transparent;")
        layout.addWidget(self.status_icon)

        # 타이틀 (이모지 + 텍스트)
        self.title_label = QLabel(f"{self.icon_emoji} {self.title_text}")
        self.title_label.setFixedWidth(180)
        self.title_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {c.text_secondary};
            background: transparent;
        """)
        layout.addWidget(self.title_label)

        # 설명
        self.desc_label = QLabel(self.description_text)
        self.desc_label.setStyleSheet(f"""
            font-size: 11px;
            color: {c.text_disabled};
            background: transparent;
        """)
        layout.addWidget(self.desc_label, 1)

        # 상태 텍스트
        self.status_text = QLabel("대기")
        self.status_text.setFixedWidth(70)
        self.status_text.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_text.setStyleSheet(f"""
            font-size: 11px;
            color: {c.text_disabled};
            background: transparent;
        """)
        layout.addWidget(self.status_text)

    def _apply_waiting_style(self):
        ds = get_design_system()
        c = ds.colors
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_secondary};
                border-radius: 8px;
                border: none;
            }}
        """)

    def update_status(self, status: str, message: str = None):
        """
        상태 업데이트
        status: 'waiting', 'checking', 'success', 'warning', 'error'
        """
        self._status = status
        ds = get_design_system()
        c = ds.colors

        if status == "checking":
            self.status_icon.setText(StatusIcon.CHECKING)
            self.status_text.setText("확인 중...")
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c.primary_light};
                    border-radius: 8px;
                    border: 1px solid {c.secondary_light};
                }}
            """)
            self.title_label.setStyleSheet(f"""
                font-size: 12px;
                font-weight: bold;
                color: {c.primary};
                background: transparent;
            """)
            self.desc_label.setStyleSheet(f"""
                font-size: 11px;
                color: {c.secondary};
                background: transparent;
            """)
            self.status_text.setStyleSheet(f"""
                font-size: 11px;
                font-weight: bold;
                color: {c.primary};
                background: transparent;
            """)

        elif status == "success":
            self.status_icon.setText(StatusIcon.SUCCESS)
            self.status_text.setText(message or "완료")
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c.success_light};
                    border-radius: 8px;
                    border: 1px solid {c.success_border};
                }}
            """)
            self.title_label.setStyleSheet(f"""
                font-size: 12px;
                font-weight: bold;
                color: #166534;
                background: transparent;
            """)
            self.desc_label.setStyleSheet(f"""
                font-size: 11px;
                color: {c.success};
                background: transparent;
            """)
            self.status_text.setStyleSheet(f"""
                font-size: 11px;
                font-weight: bold;
                color: #16A34A;
                background: transparent;
            """)

        elif status == "warning":
            self.status_icon.setText(StatusIcon.WARNING)
            self.status_text.setText(message or "경고")
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c.warning_light};
                    border-radius: 8px;
                    border: 1px solid {c.warning_border};
                }}
            """)
            self.title_label.setStyleSheet(f"""
                font-size: 12px;
                font-weight: bold;
                color: #92400E;
                background: transparent;
            """)
            self.desc_label.setStyleSheet(f"""
                font-size: 11px;
                color: {c.warning};
                background: transparent;
            """)
            self.status_text.setStyleSheet(f"""
                font-size: 11px;
                font-weight: bold;
                color: #D97706;
                background: transparent;
            """)

        elif status == "error":
            self.status_icon.setText(StatusIcon.ERROR)
            self.status_text.setText(message or "실패")
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c.error_light};
                    border-radius: 8px;
                    border: 1px solid {c.error_border};
                }}
            """)
            self.title_label.setStyleSheet(f"""
                font-size: 12px;
                font-weight: bold;
                color: #991B1B;
                background: transparent;
            """)
            self.desc_label.setStyleSheet(f"""
                font-size: 11px;
                color: {c.error};
                background: transparent;
            """)
            self.status_text.setStyleSheet(f"""
                font-size: 11px;
                font-weight: bold;
                color: #DC2626;
                background: transparent;
            """)


class ModernProgressBar(QProgressBar):
    """
    모던 스타일 프로그레스 바
    Modern styled progress bar with gradient
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apply_style()
        self.setTextVisible(False)
        self.setValue(0)

    def _apply_style(self):
        ds = get_design_system()
        c = ds.colors

        self.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 7px;
                background-color: {c.primary_light};
                height: 14px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c.gradient_start},
                    stop:1 {c.gradient_end}
                );
                border-radius: 7px;
            }}
        """)


class ModernProcessUi:
    """
    모던 시작 점검 UI 클래스
    Modern Startup Check UI class

    기존 Process_Ui의 모든 기능을 보존하면서 모던 UI/UX 적용
    """

    def setupUi(self, window: QMainWindow):
        """UI 설정 / Setup UI"""

        ds = get_design_system()
        c = ds.colors

        # 윈도우 기본 설정
        window.setObjectName("ProcessWindow")
        window.resize(620, 560)
        window.setMinimumSize(QtCore.QSize(620, 560))
        window.setMaximumSize(QtCore.QSize(620, 560))
        window.setWindowFlags(Qt.FramelessWindowHint)
        window.setAttribute(Qt.WA_TranslucentBackground)

        # 중앙 위젯
        self.mainwidget = QWidget(window)
        self.mainwidget.setObjectName("centralwidget")

        # 메인 프레임 (그림자 효과)
        self.frame = QFrame(self.mainwidget)
        self.frame.setGeometry(QtCore.QRect(10, 10, 600, 540))
        self.frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_main};
                border-radius: 20px;
            }}
        """)

        # 그림자 효과
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.frame.setGraphicsEffect(shadow)

        # ═══════════════════════════════════════════════════════════════
        # 헤더 영역 - 보라색 그라데이션
        # ═══════════════════════════════════════════════════════════════
        self.headerFrame = QFrame(self.frame)
        self.headerFrame.setGeometry(QtCore.QRect(0, 0, 600, 90))
        self.headerFrame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c.gradient_start},
                    stop:1 {c.gradient_end}
                );
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom-left-radius: 24px;
                border-bottom-right-radius: 24px;
            }}
        """)

        # 헤더 레이아웃
        headerLayout = QVBoxLayout(self.headerFrame)
        headerLayout.setContentsMargins(20, 15, 20, 15)
        headerLayout.setSpacing(4)

        # 앱 타이틀
        self.title = QLabel("🚀 쇼핑 숏폼 메이커")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("""
            color: #FFFFFF;
            font-size: 20px;
            font-weight: bold;
            background: transparent;
        """)
        headerLayout.addWidget(self.title)

        # 상태 메시지
        self.statusLabel = QLabel("시스템을 점검하고 있습니다...")
        self.statusLabel.setAlignment(Qt.AlignCenter)
        self.statusLabel.setStyleSheet("""
            color: rgba(255, 255, 255, 0.9);
            font-size: 13px;
            background: transparent;
        """)
        headerLayout.addWidget(self.statusLabel)

        # ═══════════════════════════════════════════════════════════════
        # 체크리스트 카드
        # ═══════════════════════════════════════════════════════════════
        self.checklistFrame = QFrame(self.frame)
        self.checklistFrame.setGeometry(QtCore.QRect(20, 105, 560, 360))
        self.checklistFrame.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_card};
                border-radius: 16px;
                border: 1px solid {c.border_card};
            }}
        """)

        checklistLayout = QVBoxLayout(self.checklistFrame)
        checklistLayout.setContentsMargins(16, 12, 16, 16)
        checklistLayout.setSpacing(8)

        # 체크리스트 타이틀
        self.checklistTitle = QLabel("📋 시작 전 점검 항목")
        self.checklistTitle.setStyleSheet(f"""
            color: {c.text_primary};
            font-size: 14px;
            font-weight: bold;
            background: transparent;
            padding-bottom: 8px;
        """)
        checklistLayout.addWidget(self.checklistTitle)

        # 점검 항목들
        self.checkItems = {}

        items_data = [
            ("system", "💻", "시스템 환경", "컴퓨터 성능 확인"),
            ("fonts", "🔤", "폰트 확인", "자막용 폰트"),
            ("ffmpeg", "🎬", "영상 처리", "영상 변환 엔진"),
            ("internet", "🌐", "인터넷 연결", "서비스 연결용"),
            ("modules", "📦", "핵심 모듈", "확인 중..."),
            ("ocr", "🔍", "자막 인식", "중국어 자막 인식 (첫 실행 1-2분)"),
            ("tts_dir", "📁", "음성 폴더", "음성 저장 폴더 준비"),
            ("api", "🔗", "서비스 준비", "서비스 연결"),
        ]

        for item_id, icon, title, desc in items_data:
            item_widget = ChecklistItem(item_id, icon, title, desc)
            self.checkItems[item_id] = item_widget
            checklistLayout.addWidget(item_widget)

        checklistLayout.addStretch()

        # ═══════════════════════════════════════════════════════════════
        # 프로그레스 영역
        # ═══════════════════════════════════════════════════════════════
        self.progressFrame = QFrame(self.frame)
        self.progressFrame.setGeometry(QtCore.QRect(20, 478, 560, 50))
        self.progressFrame.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_card};
                border-radius: 12px;
                border: 1px solid {c.border_card};
            }}
        """)

        progressLayout = QHBoxLayout(self.progressFrame)
        progressLayout.setContentsMargins(16, 10, 16, 10)
        progressLayout.setSpacing(12)

        # 진행률 라벨
        self.progressLabel = QLabel("진행률")
        self.progressLabel.setStyleSheet(f"""
            color: {c.text_primary};
            font-size: 12px;
            font-weight: bold;
            background: transparent;
        """)
        progressLayout.addWidget(self.progressLabel)

        # 프로그레스 바
        self.progressBar = ModernProgressBar()
        self.progressBar.setFixedHeight(14)
        self.progressBar.setObjectName("progressBar")
        progressLayout.addWidget(self.progressBar, 1)

        # 퍼센트 표시
        self.percentLabel = QLabel("0%")
        self.percentLabel.setFixedWidth(50)
        self.percentLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.percentLabel.setStyleSheet(f"""
            color: {c.primary};
            font-size: 13px;
            font-weight: bold;
            background: transparent;
        """)
        progressLayout.addWidget(self.percentLabel)

        # 중앙 위젯 설정
        window.setCentralWidget(self.mainwidget)
        QtCore.QMetaObject.connectSlotsByName(window)

    def updateCheckItem(self, item_id: str, status: str, message: str = None):
        """
        체크리스트 항목 상태 업데이트 (기존 API 호환)

        Args:
            item_id: 항목 ID (system, fonts, ffmpeg, internet, modules, ocr, tts_dir, api)
            status: 상태 (checking, success, warning, error)
            message: 상태 메시지 (선택사항)
        """
        if item_id in self.checkItems:
            self.checkItems[item_id].update_status(status, message)

    def setProgress(self, value: int):
        """
        프로그레스 바 업데이트

        Args:
            value: 0-100 사이의 진행률
        """
        self.progressBar.setValue(value)
        self.percentLabel.setText(f"{value}%")

    def setStatusMessage(self, message: str):
        """
        상태 메시지 업데이트

        Args:
            message: 표시할 상태 메시지
        """
        self.statusLabel.setText(message)


# 기존 Process_Ui와의 호환성을 위한 별칭
Process_Ui = ModernProcessUi
