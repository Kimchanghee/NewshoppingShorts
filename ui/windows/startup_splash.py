# -*- coding: utf-8 -*-
"""
Startup splash screen for PyQt6.
"""

import json
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget

from ui.theme_manager import get_theme_manager


class AnimatedLogo(QLabel):
    """Minimal brand badge with subtle pulse animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pulse = 0.0
        self.pulse_direction = 1

        self.setText("SS")
        self.setFont(QFont("Pretendard", 24, QFont.Weight.Bold))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(72, 72)
        self.setStyleSheet(
            "background-color: #E31639; color: white; border: 1px solid #F1A5B5; border-radius: 36px;"
        )

        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._animate_pulse)
        self.pulse_timer.start(60)

    def _animate_pulse(self):
        self._pulse += 0.06 * self.pulse_direction
        if self._pulse >= 1.0:
            self.pulse_direction = -1
        elif self._pulse <= 0.0:
            self.pulse_direction = 1

        fill_alpha = int(220 + (self._pulse * 25))
        border_alpha = int(30 + (self._pulse * 40))
        self.setStyleSheet(
            f"background-color: rgba(227, 22, 57, {fill_alpha}); "
            f"color: white; border: 1px solid rgba(241, 165, 181, {border_alpha}); border-radius: 36px;"
        )


class GradientWidget(QWidget):
    """Custom widget with animated gradient background."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gradient_offset = 0.0

        self.shimmer_timer = QTimer(self)
        self.shimmer_timer.timeout.connect(self._animate_shimmer)
        self.shimmer_timer.start(40)

    def _animate_shimmer(self):
        self.gradient_offset = (self.gradient_offset + 0.005) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        gradient.setColorAt(0.0, QColor(255, 250, 250))
        gradient.setColorAt(0.5 + self.gradient_offset * 0.3, QColor(252, 245, 246))
        gradient.setColorAt(1.0, QColor(248, 246, 246))
        painter.fillRect(rect, gradient)

        shimmer = QLinearGradient(
            int(rect.width() * self.gradient_offset),
            0,
            int(rect.width() * (self.gradient_offset + 0.3)),
            rect.height(),
        )
        shimmer.setColorAt(0.0, QColor(255, 255, 255, 0))
        shimmer.setColorAt(0.5, QColor(255, 255, 255, 30))
        shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(rect, shimmer)

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
        # Keep splash compact, but large enough so text/controls never overlap.
        self.setFixedSize(460, 360)

        self._status_text = "프로그램을 준비하고 있습니다"
        self._load_fonts()
        self._setup_ui()
        self._center_on_screen()

        self.dot_timer = QTimer(self)
        self.dot_timer.timeout.connect(self._update_dots)
        self.dot_timer.start(400)
        self._dot_count = 0

    def _load_fonts(self):
        """Load bundled fonts if available."""
        project_root = Path(__file__).resolve().parents[2]
        for font_name in ("Pretendard-Bold.ttf", "Pretendard-Regular.ttf"):
            font_path = project_root / "fonts" / font_name
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))

    def _setup_ui(self):
        self.container = GradientWidget(self)
        self.container.setGeometry(10, 10, 440, 340)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(8)

        self.logo = AnimatedLogo()
        layout.addWidget(self.logo, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(10)

        self.title_label = QLabel("쇼핑 쇼츠 메이커")
        self.title_label.setFont(QFont("Pretendard", 22, QFont.Weight.ExtraBold))
        self.title_label.setMinimumHeight(34)
        self.title_label.setMaximumHeight(46)
        self.title_label.setWordWrap(True)
        self.title_label.setContentsMargins(0, 0, 0, 0)
        self.title_label.setStyleSheet(
            f"color: {self.COLORS['primary']}; background: transparent; border: none;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("쇼핑 숏폼 메이커")
        self.subtitle_label.setFont(QFont("Pretendard", 10))
        self.subtitle_label.setStyleSheet(
            f"color: {self.COLORS['secondary']}; background: transparent; letter-spacing: 1px;"
        )
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_label)

        layout.addSpacing(12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"""
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
            """
        )
        layout.addWidget(self.progress_bar)

        self.percent_label = QLabel("0%")
        self.percent_label.setFont(QFont("Pretendard", 10, QFont.Weight.Bold))
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.percent_label.setStyleSheet(f"color: {self.COLORS['primary']}; background: transparent;")
        layout.addWidget(self.percent_label)

        self.status_label = QLabel(self._status_text)
        self.status_label.setFont(QFont("Pretendard", 11))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"color: {self.COLORS['secondary']}; background: transparent;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        version_label = QLabel(f"v{self._get_version()}")
        version_label.setFont(QFont("Pretendard", 9))
        version_label.setStyleSheet(f"color: {self.COLORS['border']}; background: transparent;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        # Keep references for test/debug introspection.
        self.version_label = version_label
        self._ensure_layout_capacity(layout)

    def _ensure_layout_capacity(self, layout: QVBoxLayout) -> None:
        """
        Expand splash/container height when required so widgets never overlap.
        Handles font fallback and high-DPI environments safely.
        """
        layout.activate()
        required_h = layout.sizeHint().height()
        current_container_h = self.container.height()
        if required_h <= current_container_h:
            return

        container_w = self.container.width()
        target_container_h = required_h + 4
        target_window_h = target_container_h + 20  # container y-offset top/bottom

        self.setFixedSize(self.width(), target_window_h)
        self.container.setGeometry(10, 10, container_w, target_container_h)

    def _get_version(self) -> str:
        """Load version from version.json with frozen/non-frozen fallback paths."""
        candidates = []
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(Path(meipass) / "version.json")
            candidates.append(Path(sys.executable).resolve().parent / "version.json")
        else:
            candidates.append(Path(__file__).resolve().parents[2] / "version.json")
        candidates.append(Path.cwd() / "version.json")

        for version_file in candidates:
            try:
                if version_file.exists():
                    with open(version_file, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                    version = str(data.get("version", "")).strip()
                    if version:
                        return version
            except Exception:
                continue

        return "1.0.0"

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _update_dots(self):
        self._dot_count = (self._dot_count + 1) % 4
        self.status_label.setText(self._status_text.rstrip(".") + "." * self._dot_count)

    def set_status(self, text):
        """Update status text (maintains backward compatibility)."""
        self._status_text = text
        self.status_label.setText(text)

    def set_progress(self, value):
        """Update progress bar (maintains backward compatibility)."""
        self.progress_bar.setValue(value)
        if hasattr(self, "percent_label"):
            self.percent_label.setText(f"{value}%")

    def showEvent(self, event):
        """Fade-in animation when splash is shown."""
        super().showEvent(event)
        self.setWindowOpacity(0)

        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(400)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_in.start()
