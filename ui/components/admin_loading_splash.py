# -*- coding: utf-8 -*-
"""
Admin Loading Splash Screen
A visually striking loading screen for the admin dashboard with dark theme,
animated spinner, and smooth fade transitions.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QProgressBar, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, pyqtProperty
from PyQt6.QtGui import QFont, QPainter, QPen, QColor, QLinearGradient, QPainterPath, QRadialGradient

# Dark color scheme matching admin_dashboard.py
DARK = {
    "bg": "#1a1a2e",
    "card": "#16213e",
    "primary": "#e31639",
    "primary_hover": "#ff1744",
    "text": "#ffffff",
    "text_dim": "#8892b0",
    "border": "#2d3748",
}

FONT_FAMILY = "맑은 고딕"


class SpinningLoader(QWidget):
    """Custom spinning loader with gradient ring"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self._rotation = 0

        # Animation for rotation
        self.rotation_timer = QTimer(self)
        self.rotation_timer.timeout.connect(self._update_rotation)
        self.rotation_timer.start(16)  # ~60fps

    def _update_rotation(self):
        self._rotation = (self._rotation + 4) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Center point
        center = QPoint(40, 40)

        # Save state
        painter.save()
        painter.translate(center)
        painter.rotate(self._rotation)

        # Create gradient for the ring
        gradient = QLinearGradient(-40, -40, 40, 40)
        gradient.setColorAt(0.0, QColor(DARK["primary"]))
        gradient.setColorAt(0.5, QColor(DARK["primary_hover"]))
        gradient.setColorAt(1.0, QColor(DARK["primary"]))

        # Draw spinning arc segments
        pen = QPen(gradient, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # Draw 3 arcs with gaps for spinning effect
        for i in range(3):
            start_angle = i * 120 * 16
            span_angle = 80 * 16
            painter.drawArc(-30, -30, 60, 60, start_angle, span_angle)

        # Restore state
        painter.restore()

        # Draw inner glow circle
        glow_gradient = QRadialGradient(center, 25)
        glow_gradient.setColorAt(0.0, QColor(DARK["primary"] + "40"))
        glow_gradient.setColorAt(0.7, QColor(DARK["primary"] + "20"))
        glow_gradient.setColorAt(1.0, QColor(DARK["primary"] + "00"))

        painter.setBrush(glow_gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 25, 25)


class PulsingDot(QWidget):
    """Pulsing dot indicator"""

    def __init__(self, parent=None, delay=0):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._opacity = 0.3
        self._growing = True

        # Delayed start for staggered effect
        QTimer.singleShot(delay, self._start_animation)

    def _start_animation(self):
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._update_pulse)
        self.pulse_timer.start(30)

    def _update_pulse(self):
        if self._growing:
            self._opacity += 0.02
            if self._opacity >= 1.0:
                self._growing = False
        else:
            self._opacity -= 0.02
            if self._opacity <= 0.3:
                self._growing = True
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(DARK["primary"])
        color.setAlphaF(self._opacity)

        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 12, 12)


class AdminLoadingSplash(QWidget):
    """
    Professional loading splash screen for admin dashboard.
    Features dark theme, animated spinner, and smooth transitions.
    """

    def __init__(self):
        super().__init__()
        self._opacity = 0.0
        self._setup_ui()

    def _setup_ui(self):
        # Frameless window with dark background
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Fixed size
        self.setFixedSize(500, 400)

        # Main container with rounded corners
        self.container = QWidget(self)
        self.container.setGeometry(0, 0, 500, 400)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK["bg"]};
                border: 2px solid {DARK["border"]};
                border-radius: 16px;
            }}
        """)

        # Accent bar at top
        accent_bar = QWidget(self.container)
        accent_bar.setGeometry(0, 0, 500, 6)
        accent_bar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {DARK["primary"]},
                stop:0.5 {DARK["primary_hover"]},
                stop:1 {DARK["primary"]});
            border-top-left-radius: 16px;
            border-top-right-radius: 16px;
        """)

        # Logo/Icon area (geometric design)
        logo_container = QWidget(self.container)
        logo_container.setGeometry(185, 60, 130, 130)
        logo_container.setStyleSheet(f"""
            background-color: {DARK["card"]};
            border: 3px solid {DARK["border"]};
            border-radius: 65px;
        """)

        # Inner logo circle
        inner_logo = QWidget(logo_container)
        inner_logo.setGeometry(25, 25, 80, 80)
        inner_logo.setStyleSheet(f"""
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                fx:0.5, fy:0.5,
                stop:0 {DARK["primary"]},
                stop:0.7 {DARK["primary_hover"]},
                stop:1 {DARK["card"]});
            border-radius: 40px;
        """)

        # Animated spinner
        self.spinner = SpinningLoader(self.container)
        self.spinner.move(210, 210)

        # Title
        title = QLabel("관리자 대시보드", self.container)
        title.setGeometry(0, 310, 500, 35)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont(FONT_FAMILY, 18, QFont.Bold))
        title.setStyleSheet(f"""
            color: {DARK["text"]};
            background: transparent;
            letter-spacing: 2px;
        """)

        # Subtitle
        self.subtitle = QLabel("로딩 중", self.container)
        self.subtitle.setGeometry(0, 350, 500, 25)
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setFont(QFont(FONT_FAMILY, 11))
        self.subtitle.setStyleSheet(f"""
            color: {DARK["text_dim"]};
            background: transparent;
        """)

        # Pulsing dots
        dot_container = QWidget(self.container)
        dot_container.setGeometry(220, 378, 60, 12)

        self.dot1 = PulsingDot(dot_container, delay=0)
        self.dot1.move(0, 0)

        self.dot2 = PulsingDot(dot_container, delay=200)
        self.dot2.move(24, 0)

        self.dot3 = PulsingDot(dot_container, delay=400)
        self.dot3.move(48, 0)

    def _center_on_screen(self):
        """Center the splash screen on the primary screen"""
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )

    def show_splash(self):
        """Show splash with fade-in animation"""
        self._center_on_screen()
        self.show()

        # Fade in animation
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in.start()

    def update_progress(self, value: int, message: str = ""):
        """
        Update loading progress and message.

        Args:
            value: Progress value 0-100 (currently cosmetic)
            message: Status message to display
        """
        if message:
            self.subtitle.setText(message)

    def close_splash(self):
        """Close splash with fade-out animation"""
        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(250)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.InCubic)
        self.fade_out.finished.connect(self.close)
        self.fade_out.start()


# Standalone test
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    splash = AdminLoadingSplash()
    splash.show_splash()

    # Simulate loading progress
    def update_demo():
        import random
        messages = [
            "데이터베이스 연결 중...",
            "사용자 정보 로드 중...",
            "구독 데이터 확인 중...",
            "대시보드 준비 중...",
        ]
        splash.update_progress(random.randint(0, 100), random.choice(messages))

    # Update message every 800ms
    timer = QTimer()
    timer.timeout.connect(update_demo)
    timer.start(800)

    # Auto close after 5 seconds
    QTimer.singleShot(5000, splash.close_splash)

    sys.exit(app.exec())
