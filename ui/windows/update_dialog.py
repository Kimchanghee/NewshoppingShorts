# -*- coding: utf-8 -*-
"""
Modern Update Dialog for PyQt6
업데이트 확인 및 다운로드 진행 UI
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

from ui.theme_manager import get_theme_manager


class UpdateConfirmDialog(QWidget):
    """업데이트 확인 다이얼로그"""

    update_accepted = pyqtSignal()
    update_declined = pyqtSignal()

    def __init__(self, version: str, release_notes: str = "", is_mandatory: bool = False):
        super().__init__()
        self.tm = get_theme_manager()
        self.version = version
        self.release_notes = release_notes
        self.is_mandatory = is_mandatory

        self._setup_colors()
        self._setup_window()
        self._setup_ui()
        self._center_on_screen()

    def _setup_colors(self):
        self.COLORS = {
            "bg": "#FFFFFF",
            "primary": self.tm.get_color("primary"),
            "gradient_start": self.tm.get_color("gradient_start"),
            "gradient_end": self.tm.get_color("gradient_end"),
            "text_primary": "#111827",
            "text_secondary": "#6B7280",
            "border": "#E5E7EB",
            "surface": "#F9FAFB",
        }

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 320)

    def _setup_ui(self):
        # Main container with shadow
        self.container = QWidget(self)
        self.container.setGeometry(10, 10, 400, 300)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: {self.COLORS['bg']};
                border-radius: 16px;
                border: 1px solid {self.COLORS['border']};
            }}
        """)

        # Shadow removed for cleaner UI

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        # Icon
        icon_label = QLabel("🔄")
        icon_label.setFont(QFont("Segoe UI Emoji", 36))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_label)

        # Title
        title = QLabel("새로운 업데이트")
        title.setFont(QFont("Pretendard", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            color: {self.COLORS['text_primary']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(title)

        # Version info
        version_text = f"버전 {self.version}이(가) 준비되었습니다"
        version_label = QLabel(version_text)
        version_label.setFont(QFont("Pretendard", 12))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(f"""
            color: {self.COLORS['text_secondary']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(version_label)

        # Release notes (if available)
        if self.release_notes:
            notes_label = QLabel(self.release_notes[:100] + ("..." if len(self.release_notes) > 100 else ""))
            notes_label.setFont(QFont("Pretendard", 11))
            notes_label.setWordWrap(True)
            notes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            notes_label.setStyleSheet(f"""
                color: {self.COLORS['text_secondary']};
                background-color: {self.COLORS['surface']};
                padding: 12px;
                border-radius: 8px;
                border: none;
            """)
            layout.addWidget(notes_label)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        if not self.is_mandatory:
            self.later_btn = QPushButton("나중에")
            self.later_btn.setFixedSize(120, 44)
            self.later_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.later_btn.setFont(QFont("Pretendard", 12, QFont.Weight.Medium))
            self.later_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.COLORS['surface']};
                    color: {self.COLORS['text_secondary']};
                    border: 1px solid {self.COLORS['border']};
                    border-radius: 8px;
                }}
                QPushButton:hover {{
                    background-color: #F3F4F6;
                }}
            """)
            self.later_btn.clicked.connect(self._on_decline)
            btn_layout.addWidget(self.later_btn)

        self.update_btn = QPushButton("지금 업데이트")
        self.update_btn.setFixedSize(160 if not self.is_mandatory else 200, 44)
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setFont(QFont("Pretendard", 12, QFont.Weight.Bold))
        self.update_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.COLORS['gradient_start']},
                    stop:1 {self.COLORS['gradient_end']}
                );
                color: white;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.COLORS['primary']},
                    stop:1 {self.COLORS['gradient_start']}
                );
            }}
        """)
        self.update_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(self.update_btn)

        layout.addLayout(btn_layout)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def _on_accept(self):
        self.update_accepted.emit()
        self.close()

    def _on_decline(self):
        self.update_declined.emit()
        self.close()

    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowOpacity(0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_in.start()


class UpdateProgressDialog(QWidget):
    """업데이트 다운로드 진행 다이얼로그"""

    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.tm = get_theme_manager()
        self._progress = 0
        self._status_text = "다운로드 준비 중..."

        self._setup_colors()
        self._setup_window()
        self._setup_ui()
        self._center_on_screen()

        # Animated dots
        self.dot_timer = QTimer(self)
        self.dot_timer.timeout.connect(self._update_dots)
        self.dot_timer.start(400)
        self._dot_count = 0

    def _setup_colors(self):
        self.COLORS = {
            "bg": "#FFFFFF",
            "primary": self.tm.get_color("primary"),
            "gradient_start": self.tm.get_color("gradient_start"),
            "gradient_end": self.tm.get_color("gradient_end"),
            "text_primary": "#111827",
            "text_secondary": "#6B7280",
            "border": "#E5E7EB",
            "progress_bg": "#F3F4F6",
        }

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 280)

    def _setup_ui(self):
        # Main container
        self.container = QWidget(self)
        self.container.setGeometry(10, 10, 400, 260)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: {self.COLORS['bg']};
                border-radius: 16px;
                border: 1px solid {self.COLORS['border']};
            }}
        """)

        # Shadow removed for cleaner UI

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        # Icon
        icon_label = QLabel("⬇️")
        icon_label.setFont(QFont("Segoe UI Emoji", 32))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_label)

        # Title
        title = QLabel("업데이트 다운로드 중")
        title.setFont(QFont("Pretendard", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            color: {self.COLORS['text_primary']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(title)

        layout.addSpacing(8)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {self.COLORS['progress_bg']};
                border-radius: 5px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.COLORS['gradient_start']},
                    stop:1 {self.COLORS['gradient_end']}
                );
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Progress percentage
        self.percent_label = QLabel("0%")
        self.percent_label.setFont(QFont("Pretendard", 24, QFont.Weight.Bold))
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.percent_label.setStyleSheet(f"""
            color: {self.COLORS['primary']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.percent_label)

        # Status text
        self.status_label = QLabel(self._status_text)
        self.status_label.setFont(QFont("Pretendard", 11))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"""
            color: {self.COLORS['text_secondary']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def _update_dots(self):
        self._dot_count = (self._dot_count + 1) % 4
        base_text = self._status_text.rstrip(".")
        self.status_label.setText(base_text + "." * self._dot_count)

    def set_progress(self, value: int):
        """Update progress (0-100)"""
        self._progress = value
        self.progress_bar.setValue(value)
        self.percent_label.setText(f"{value}%")

        # Update status text based on progress
        if value < 30:
            self._status_text = "다운로드 중..."
        elif value < 70:
            self._status_text = "파일 전송 중..."
        elif value < 100:
            self._status_text = "거의 완료..."
        else:
            self._status_text = "설치 준비 중..."
            self.dot_timer.stop()
            self.status_label.setText(self._status_text)

    def set_status(self, text: str):
        """Update status text"""
        self._status_text = text
        self.status_label.setText(text)

    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowOpacity(0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_in.start()

    def closeEvent(self, event):
        self.dot_timer.stop()
        super().closeEvent(event)
