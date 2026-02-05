# -*- coding: utf-8 -*-
"""
Enhanced Header Panel - Content Creator's Studio Theme

Features:
- Diagonal gradient accent
- App branding with custom typography
- Theme toggle button
- Settings button
- Professional polish
"""

from typing import Optional

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QFrame, QPushButton, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QFont, QPixmap

from ui.components.base_widget_enhanced import ThemedMixin, create_button


class GradientAccent(QWidget):
    """Diagonal gradient accent strip with pixmap caching"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._cached_pixmap: Optional[QPixmap] = None
        self._cached_width = 0

    def paintEvent(self, event):
        w = self.width()
        if w <= 0:
            return

        # 폭이 변경된 경우에만 pixmap 재생성
        if self._cached_pixmap is None or self._cached_width != w:
            self._cached_width = w
            self._cached_pixmap = QPixmap(w, 4)
            pm_painter = QPainter(self._cached_pixmap)
            gradient = QLinearGradient(0, 0, w, 0)
            gradient.setColorAt(0, QColor("#FF1744"))
            gradient.setColorAt(0.5, QColor("#FF4D6A"))
            gradient.setColorAt(1, QColor("#FF6B9D"))
            pm_painter.fillRect(0, 0, w, 4, gradient)
            pm_painter.end()

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._cached_pixmap)


class EnhancedHeaderPanel(QFrame, ThemedMixin):
    """
    Enhanced header with branding and controls

    Features:
    - Gradient accent strip
    - App title with custom typography
    - Theme toggle
    - Settings button
    """

    theme_toggled = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        # Main vertical layout
        main_layout = QWidget(self)
        v_layout = __import__('PyQt6.QtWidgets', fromlist=['QVBoxLayout']).QVBoxLayout(main_layout)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)

        # Gradient accent strip
        self.accent = GradientAccent(self)
        v_layout.addWidget(self.accent)

        # Header content
        header_content = QFrame(self)
        self.layout = QHBoxLayout(header_content)
        self.layout.setContentsMargins(24, 12, 24, 12)
        self.layout.setSpacing(16)

        # App branding (left)
        branding = self._create_branding()
        self.layout.addWidget(branding)

        self.layout.addStretch()

        # Controls (right)
        controls = self._create_controls()
        self.layout.addWidget(controls)

        v_layout.addWidget(header_content)

        # Set overall layout
        overall = QHBoxLayout(self)
        overall.setContentsMargins(0, 0, 0, 0)
        overall.addWidget(main_layout)

        self.setFixedHeight(68)  # Increased from 40
        self.gui.header_frame = self

    def _create_branding(self) -> QWidget:
        """Create app title/logo area"""
        branding = QWidget()
        layout = QHBoxLayout(branding)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Logo/Icon (could be an actual QPixmap later)
        logo = QLabel("🎬")
        logo.setStyleSheet(f"font-size: {self.typography.font_size_3xl}px;")
        layout.addWidget(logo)

        # Title
        self.title_label = QLabel("쇼핑 쇼츠 메이커")
        layout.addWidget(self.title_label)

        return branding

    def _create_controls(self) -> QWidget:
        """Create header controls (theme toggle, settings)"""
        controls = QWidget()
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Theme toggle button
        self.theme_btn = QPushButton("🌙")
        self.theme_btn.setFixedSize(36, 36)
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setToolTip("다크 모드 전환")
        self.theme_btn.clicked.connect(self._on_theme_toggle)
        layout.addWidget(self.theme_btn)

        # Settings button
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setToolTip("설정")
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

        return controls

    def _on_theme_toggle(self):
        """Toggle theme mode"""
        self.ds.toggle_color_mode()
        self.theme_toggled.emit()
        self.apply_theme()

        # Update icon
        if self.ds.is_dark_mode:
            self.theme_btn.setText("☀️")
            self.theme_btn.setToolTip("라이트 모드 전환")
        else:
            self.theme_btn.setText("🌙")
            self.theme_btn.setToolTip("다크 모드 전환")

    def apply_theme(self):
        """Apply enhanced header styling"""
        c = self.colors
        t = self.typography
        r = self.ds.radius

        # Header background
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_header};
                border: none;
                border-bottom: 1px solid {c.border_light};
            }}
        """)

        # Title with custom font
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {c.text_primary};
                font-family: {t.font_family_heading};
                font-size: {t.font_size_2xl}px;
                font-weight: {t.font_weight_bold};
                letter-spacing: -0.5px;
                background: transparent;
                border: none;
            }}
        """)

        # Control buttons
        button_style = f"""
            QPushButton {{
                background-color: {c.bg_secondary};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: {r.md}px;
                font-size: {t.font_size_lg}px;
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
                border-color: {c.primary};
            }}
            QPushButton:pressed {{
                background-color: {c.bg_selected};
            }}
        """
        self.theme_btn.setStyleSheet(button_style)
        self.settings_btn.setStyleSheet(button_style)
