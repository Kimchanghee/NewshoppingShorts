# -*- coding: utf-8 -*-
"""
Instant startup splash screen - shows immediately while app loads.
PyQt5 기반 즉시 표시 스플래시 화면
"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QApplication,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPen, QLinearGradient

from ui.theme_manager import get_theme_manager


class StartupSplash(QWidget):
    """Instant startup splash screen with modern design."""

    loadingComplete = pyqtSignal()

    def __init__(self):
        super().__init__()
        # 테마 매니저에서 색상 가져오기
        self.tm = get_theme_manager()
        self.tm.set_theme("light")  # 스플래시는 화사한 라이트 테마 고정

        self.COLORS = {
            "bg": self.tm.get_color("bg_main"),
            "header_bg": self.tm.get_color("primary_light"),
            "primary": self.tm.get_color("primary"),
            "accent": self.tm.get_color("accent"),
            "text": self.tm.get_color("text_primary"),
            "secondary": self.tm.get_color("text_secondary"),
            "border": self.tm.get_color("border_light"),
            "progress_bg": self.tm.get_color("bg_secondary"),
        }

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(420, 280)

        self._status_text = "초기화 중..."
        self._progress = 0
        self._dot_count = 0

        self._setup_ui()
        self._center_on_screen()
        self._start_animation()

    def _setup_ui(self):
        """Setup the splash screen UI."""
        # Main container with shadow
        self.container = QWidget(self)
        self.container.setGeometry(10, 10, 400, 260)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: {self.COLORS["bg"]};
                border-radius: 16px;
                border: 1px solid {self.COLORS["border"]};
            }}
        """)

        # Drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(0)

        # Logo/Icon area
        icon_label = QLabel("🚀")
        icon_label.setFont(QFont("Segoe UI Emoji", 36))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        layout.addSpacing(10)

        # Title
        title = QLabel("쇼핑 숏폼 메이커")
        title.setFont(QFont("맑은 고딕", 20, QFont.Bold))
        title.setStyleSheet(
            f"color: {self.COLORS['primary']}; background: transparent; border: none;"
        )
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Shopping Shorts Maker")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet(
            f"color: {self.COLORS['secondary']}; background: transparent; border: none;"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(25)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {self.COLORS["progress_bg"]};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {self.COLORS["primary"]};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        layout.addSpacing(15)

        # Status text
        self.status_label = QLabel(self._status_text)
        self.status_label.setFont(QFont("맑은 고딕", 9))
        self.status_label.setStyleSheet(
            f"color: {self.COLORS['secondary']}; background: transparent; border: none;"
        )
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Version
        version = QLabel("v1.0.0")
        version.setFont(QFont("Segoe UI", 8))
        version.setStyleSheet(
            f"color: {self.COLORS['secondary']}; background: transparent; border: none;"
        )
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)

    def _center_on_screen(self):
        """Center the splash on screen."""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _start_animation(self):
        """Start the loading dot animation."""
        self.dot_timer = QTimer(self)
        self.dot_timer.timeout.connect(self._update_dots)
        self.dot_timer.start(400)

    def _update_dots(self):
        """Update the loading dots."""
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        base_text = self._status_text.rstrip(".")
        if base_text.endswith("..."):
            base_text = base_text[:-3]
        self.status_label.setText(f"{base_text}{dots}")

    def set_status(self, text: str):
        """Update status text."""
        self._status_text = text
        self.status_label.setText(text)

    def set_progress(self, value: int):
        """Update progress bar."""
        self._progress = min(100, max(0, value))
        self.progress_bar.setValue(self._progress)

    def finish(self):
        """Complete loading and close."""
        self.dot_timer.stop()
        self.set_progress(100)
        self.set_status("완료!")
        QTimer.singleShot(300, self.close)
        QTimer.singleShot(300, self.loadingComplete.emit)


def show_startup_splash():
    """Show startup splash and return the widget."""
    splash = StartupSplash()
    splash.show()
    QApplication.processEvents()
    return splash
