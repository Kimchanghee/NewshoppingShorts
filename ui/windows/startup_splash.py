# -*- coding: utf-8 -*-
"""
Startup splash screen for PyQt6 - Enhanced Modern Edition
"""
import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QApplication,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient, QPen, QFontDatabase

from ui.theme_manager import get_theme_manager

class AnimatedLogo(QLabel):
    """Custom animated logo widget with rotation and pulse effects"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rotation_angle = 0
        self.scale_factor = 1.0
        self.pulse_direction = 1

        self.setText("🚀")
        self.setFont(QFont("Segoe UI Emoji", 42))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(80, 80)

        # Rotation animation
        self.rotation_timer = QTimer(self)
        self.rotation_timer.timeout.connect(self._animate_rotation)
        self.rotation_timer.start(30)

        # Pulse animation
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._animate_pulse)
        self.pulse_timer.start(50)

        # Glow effect
        self.glow = QGraphicsDropShadowEffect()
        self.glow.setBlurRadius(25)
        self.glow.setColor(QColor(227, 22, 57, 100))
        self.glow.setOffset(0, 0)
        self.setGraphicsEffect(self.glow)

    def _animate_rotation(self):
        self.rotation_angle = (self.rotation_angle + 1) % 360
        if self.rotation_angle % 120 == 0:
            self.update()

    def _animate_pulse(self):
        self.scale_factor += 0.015 * self.pulse_direction
        if self.scale_factor >= 1.15:
            self.pulse_direction = -1
        elif self.scale_factor <= 0.95:
            self.pulse_direction = 1

        # Update glow intensity
        glow_intensity = int(80 + (self.scale_factor - 1.0) * 200)
        self.glow.setColor(QColor(227, 22, 57, glow_intensity))
        self.update()

class GradientWidget(QWidget):
    """Custom widget with animated gradient background"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gradient_offset = 0.0

        # Shimmer animation
        self.shimmer_timer = QTimer(self)
        self.shimmer_timer.timeout.connect(self._animate_shimmer)
        self.shimmer_timer.start(40)

    def _animate_shimmer(self):
        self.gradient_offset = (self.gradient_offset + 0.005) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Multi-layer gradient background
        rect = self.rect()

        # Base gradient
        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        gradient.setColorAt(0.0, QColor(255, 250, 250))
        gradient.setColorAt(0.5 + self.gradient_offset * 0.3, QColor(252, 245, 246))
        gradient.setColorAt(1.0, QColor(248, 246, 246))

        painter.fillRect(rect, gradient)

        # Shimmer overlay
        shimmer = QLinearGradient(
            int(rect.width() * self.gradient_offset), 0,
            int(rect.width() * (self.gradient_offset + 0.3)), rect.height()
        )
        shimmer.setColorAt(0.0, QColor(255, 255, 255, 0))
        shimmer.setColorAt(0.5, QColor(255, 255, 255, 30))
        shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.fillRect(rect, shimmer)

        # Border with subtle gradient
        painter.setPen(QPen(QColor(226, 232, 240), 1))
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 16, 16)

class StartupSplash(QWidget):
    loadingComplete = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.tm = get_theme_manager()
        self.tm.set_theme("light")

        self.COLORS = {
            "bg": self.tm.get_color("bg_main"),
            "primary": self.tm.get_color("primary"),
            "gradient_start": self.tm.get_color("gradient_start"),
            "gradient_end": self.tm.get_color("gradient_end"),
            "secondary": self.tm.get_color("text_secondary"),
            "border": self.tm.get_color("border_light"),
            "progress_bg": self.tm.get_color("bg_secondary"),
        }

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(450, 320)

        self._status_text = "초기화 중..."
        self._load_fonts()
        self._setup_ui()
        self._center_on_screen()

        # Animated dots for status
        self.dot_timer = QTimer(self)
        self.dot_timer.timeout.connect(self._update_dots)
        self.dot_timer.start(400)
        self._dot_count = 0

    def _load_fonts(self):
        """Load custom fonts"""
        font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fonts", "Pretendard-Bold.ttf")
        if os.path.exists(font_path):
            QFontDatabase.addApplicationFont(font_path)

    def _setup_ui(self):
        # Gradient background container
        self.container = GradientWidget(self)
        self.container.setGeometry(10, 10, 430, 300)

        # Outer shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(40, 35, 40, 35)
        layout.setSpacing(18)

        # Animated logo
        self.logo = AnimatedLogo()
        layout.addWidget(self.logo, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(10)

        # Title with gradient text effect (simulated via shadow)
        title = QLabel("쇼핑 숏폼 메이커")
        title_font = QFont("Pretendard", 24, QFont.Weight.ExtraBold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.5)
        title.setFont(title_font)
        title.setStyleSheet(f"""
            color: {self.COLORS['primary']};
            background: transparent;
            border: none;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title shadow for depth
        title_shadow = QGraphicsDropShadowEffect()
        title_shadow.setBlurRadius(8)
        title_shadow.setColor(QColor(227, 22, 57, 50))
        title_shadow.setOffset(0, 2)
        title.setGraphicsEffect(title_shadow)

        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Shopping Shorts Maker")
        subtitle.setFont(QFont("Pretendard", 10))
        subtitle.setStyleSheet(f"""
            color: {self.COLORS['secondary']};
            background: transparent;
            letter-spacing: 1px;
        """)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # Modern gradient progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {self.COLORS["progress_bg"]};
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.COLORS["gradient_start"]},
                    stop:1 {self.COLORS["gradient_end"]}
                );
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Status text
        self.status_label = QLabel(self._status_text)
        self.status_label.setFont(QFont("Pretendard", 11))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"""
            color: {self.COLORS['secondary']};
            background: transparent;
        """)
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Version number
        version = self._get_version()
        version_label = QLabel(f"v{version}")
        version_label.setFont(QFont("Pretendard", 9))
        version_label.setStyleSheet(f"""
            color: {self.COLORS['border']};
            background: transparent;
        """)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

    def _get_version(self):
        """Load version from version.json"""
        try:
            version_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "version.json")
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("version", "1.0.0")
        except Exception:
            pass
        return "1.0.0"

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _update_dots(self):
        self._dot_count = (self._dot_count + 1) % 4
        self.status_label.setText(self._status_text.rstrip(".") + "." * self._dot_count)

    def set_status(self, text):
        """Update status text (maintains backward compatibility)"""
        self._status_text = text
        self.status_label.setText(text)

    def set_progress(self, value):
        """Update progress bar (maintains backward compatibility)"""
        self.progress_bar.setValue(value)

    def showEvent(self, event):
        """Fade-in animation when splash is shown"""
        super().showEvent(event)
        self.setWindowOpacity(0)

        # Fade in animation
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(400)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_in.start()
