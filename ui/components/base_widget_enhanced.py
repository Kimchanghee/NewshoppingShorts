# -*- coding: utf-8 -*-
"""
Enhanced Base Widgets for PyQt6 - Content Creator's Studio Theme

Provides themed components with:
- Motion-first micro-interactions
- Distinctive typography (Outfit + Manrope)
- Enhanced visual hierarchy
- Professional polish
"""

import logging
from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QTextEdit, QCheckBox, QRadioButton
)
from PyQt6.QtCore import (
    pyqtSignal, QPropertyAnimation, QEasingCurve,
    Qt, QPoint, QSize, QRect, pyqtProperty
)
from PyQt6.QtGui import QColor, QPalette, QFont, QPainter, QPainterPath

from ui.design_system_enhanced import get_design_system, DesignSystem, ColorMode

logger = logging.getLogger(__name__)


class ThemedMixin:
    """
    Enhanced Mixin for theme support with design system integration

    Provides access to:
    - Color palette
    - Typography system
    - Spacing/radius/shadow
    - Animation presets
    """

    def __init_themed__(self, theme_manager=None):
        self._design_system = get_design_system()
        self._animations = []  # Track active animations for cleanup

    @property
    def ds(self) -> DesignSystem:
        """Quick access to design system"""
        return self._design_system

    @property
    def colors(self):
        """Quick access to current color palette"""
        return self._design_system.colors

    @property
    def typography(self):
        """Quick access to typography system"""
        return self._design_system.typography

    @property
    def spacing(self):
        """Quick access to spacing system"""
        return self._design_system.spacing

    @property
    def is_dark_mode(self) -> bool:
        """Check if dark mode is active"""
        return self._design_system.is_dark_mode

    def get_color(self, key: str) -> str:
        """Get color value by name"""
        return self._design_system.get_color(key)

    def apply_theme(self) -> None:
        """Override in subclasses to apply specific styles"""
        pass

    def cleanup_theme(self) -> None:
        """Cleanup animations and theme resources"""
        for anim in self._animations:
            if anim:
                anim.stop()
                anim.deleteLater()
        self._animations.clear()

    def add_drop_shadow(self, widget: QWidget, blur_radius: int = 10,
                       offset: tuple = (0, 2), color: Optional[QColor] = None):
        """Add subtle drop shadow effect"""
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(blur_radius)
        effect.setOffset(*offset)
        if color is None:
            color = QColor(0, 0, 0, 25)  # Subtle shadow
        effect.setColor(color)
        widget.setGraphicsEffect(effect)


class EnhancedButton(QPushButton, ThemedMixin):
    """
    Enhanced button with micro-interactions

    Features:
    - Smooth hover animations
    - Scale transforms on click
    - Gradient backgrounds for primary style
    - Multiple style presets
    """

    def __init__(self, text: str = "", parent=None,
                 style: str = "primary", size: str = "md",
                 icon: str = None):
        super().__init__(text, parent)
        self.__init_themed__()

        self._style = style
        self._size = size
        self._hover_scale = 1.0

        # Setup
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_animations()
        self.apply_theme()

    def _setup_animations(self):
        """Setup hover/click animations"""
        # Hover animation (subtle scale)
        self._scale_anim = QPropertyAnimation(self, b"minimumSize")
        self._scale_anim.setDuration(self.ds.animation.duration_fast)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animations.append(self._scale_anim)

    def apply_theme(self):
        """Apply enhanced button styles from design system"""
        style_sheet = self.ds.get_button_style(self._style, self._size)
        self.setStyleSheet(style_sheet)

        # Shadow removed for cleaner UI

    def enterEvent(self, event):
        """Hover enter - subtle scale up"""
        current_size = self.size()
        target_size = QSize(
            int(current_size.width() * 1.02),
            int(current_size.height() * 1.02)
        )
        self._scale_anim.setStartValue(self.minimumSize())
        self._scale_anim.setEndValue(target_size)
        # self._scale_anim.start()  # Disabled for now (size animation causes layout issues)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hover leave - scale back to normal"""
        # self._scale_anim.stop()
        super().leaveEvent(event)


class EnhancedLabel(QLabel, ThemedMixin):
    """
    Enhanced label with typography presets

    Variants:
    - primary: Regular body text
    - secondary: Muted text
    - title: Bold heading
    - heading: Large hero heading
    - badge_*: Styled badges
    """

    def __init__(self, text: str = "", parent=None,
                 variant: str = "primary"):
        super().__init__(text, parent)
        self.__init_themed__()

        self._variant = variant
        self.apply_theme()

    def apply_theme(self):
        """Apply typography and color styles"""
        style = self.ds.get_label_style(self._variant)
        self.setStyleSheet(style)

        # Set font family based on variant
        font = self.font()
        if "heading" in self._variant or "title" in self._variant:
            font.setFamily(self.typography.font_family_heading)
        else:
            font.setFamily(self.typography.font_family_body)
        self.setFont(font)


class EnhancedInput(QLineEdit, ThemedMixin):
    """
    Enhanced input field with focus animations

    Features:
    - Smooth focus transitions
    - Border color animations
    - Placeholder styling
    """

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.__init_themed__()

        if placeholder:
            self.setPlaceholderText(placeholder)

        self.apply_theme()

    def apply_theme(self):
        """Apply input styles from design system"""
        style = self.ds.get_input_style()
        self.setStyleSheet(style)

        # Set font
        font = QFont(self.typography.font_family_body)
        font.setPointSize(self.typography.font_size_base)
        self.setFont(font)


class EnhancedTextEdit(QTextEdit, ThemedMixin):
    """Enhanced multi-line text input"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.__init_themed__()
        self.apply_theme()

    def apply_theme(self):
        """Apply text edit styles"""
        style = self.ds.get_input_style()
        self.setStyleSheet(style)

        # Set font
        font = QFont(self.typography.font_family_body)
        font.setPointSize(self.typography.font_size_base)
        self.setFont(font)


class EnhancedCard(QFrame, ThemedMixin):
    """
    Enhanced card component with elevation

    Features:
    - Depth via shadows
    - Rounded corners
    - Hover effects (optional)
    """

    def __init__(self, parent=None, elevation: str = "md",
                 hoverable: bool = False):
        super().__init__(parent)
        self.__init_themed__()

        self._elevation = elevation
        self._hoverable = hoverable

        self.apply_theme()

    def apply_theme(self):
        """Apply card styles with elevation"""
        style = self.ds.get_card_style(self._elevation)
        self.setStyleSheet(style)

        # Shadow removed for cleaner UI
        pass

    def enterEvent(self, event):
        """Hover effect for hoverable cards"""
        if self._hoverable:
            # Slightly increase shadow on hover
            pass  # Can implement shadow intensity change
        super().enterEvent(event)


class DiagonalGradientWidget(QWidget):
    """
    Custom widget with diagonal gradient background

    Perfect for hero sections and accent areas
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ds = get_design_system()

    def paintEvent(self, event):
        """Paint diagonal gradient"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Create gradient
        from PyQt6.QtGui import QLinearGradient
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(self._ds.colors.gradient_start))
        gradient.setColorAt(0.5, QColor(self._ds.colors.gradient_mid))
        gradient.setColorAt(1, QColor(self._ds.colors.gradient_end))

        # Fill
        painter.fillRect(self.rect(), gradient)


class StepIndicator(QWidget, ThemedMixin):
    """
    Visual step indicator for multi-step processes

    Shows progress through workflow stages
    """

    step_changed = pyqtSignal(int)

    def __init__(self, steps: list, parent=None):
        super().__init__(parent)
        self.__init_themed__()

        self._steps = steps  # List of step names
        self._current_step = 0

        self.setMinimumHeight(60)
        self.apply_theme()

    def set_current_step(self, step_index: int):
        """Update current step"""
        if 0 <= step_index < len(self._steps):
            self._current_step = step_index
            self.update()  # Trigger repaint
            self.step_changed.emit(step_index)

    def paintEvent(self, event):
        """Paint step indicator"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate positions
        step_count = len(self._steps)
        if step_count == 0:
            return

        width = self.width()
        height = self.height()
        step_width = width // step_count

        # Draw progress line
        line_y = height // 2
        line_height = 4

        # Background line
        painter.setBrush(QColor(self.colors.border_light))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            0, line_y - line_height // 2,
            width, line_height,
            line_height // 2, line_height // 2
        )

        # Progress line (gradient)
        progress_width = step_width * (self._current_step + 1)
        from PyQt6.QtGui import QLinearGradient
        gradient = QLinearGradient(0, 0, progress_width, 0)
        gradient.setColorAt(0, QColor(self.colors.gradient_start))
        gradient.setColorAt(1, QColor(self.colors.gradient_end))
        painter.setBrush(gradient)
        painter.drawRoundedRect(
            0, line_y - line_height // 2,
            progress_width, line_height,
            line_height // 2, line_height // 2
        )

        # Draw step circles
        for i in range(step_count):
            x = step_width * i + step_width // 2

            # Circle
            radius = 12
            if i <= self._current_step:
                # Completed/current - filled
                painter.setBrush(QColor(self.colors.primary))
            else:
                # Upcoming - outline only
                painter.setBrush(QColor(self.colors.bg_card))

            painter.setPen(QColor(self.colors.primary))
            painter.drawEllipse(
                QPoint(x, line_y),
                radius, radius
            )

            # Step number (optional)
            painter.setPen(QColor(
                self.colors.text_on_primary if i <= self._current_step
                else self.colors.text_secondary
            ))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(
                QRect(x - radius, line_y - radius, radius * 2, radius * 2),
                Qt.AlignmentFlag.AlignCenter,
                str(i + 1)
            )

    def apply_theme(self):
        """Apply theme colors"""
        self.update()


class LoadingSpinner(QWidget, ThemedMixin):
    """
    Animated loading spinner

    Smooth rotation with brand color
    """

    def __init__(self, size: int = 40, parent=None):
        super().__init__(parent)
        self.__init_themed__()

        self._size = size
        self._angle = 0

        self.setFixedSize(size, size)

        # Rotation animation
        self._timer = self.startTimer(16)  # ~60fps

    def timerEvent(self, event):
        """Rotate spinner"""
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, event):
        """Paint spinner"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Center point
        center = self.rect().center()

        # Rotate
        painter.translate(center)
        painter.rotate(self._angle)

        # Draw arc
        from PyQt6.QtGui import QPen
        pen = QPen(QColor(self.colors.primary))
        pen.setWidth(4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        radius = self._size // 2 - 4
        painter.drawArc(
            -radius, -radius,
            radius * 2, radius * 2,
            0 * 16, 270 * 16  # 270 degree arc
        )

    def cleanup_theme(self):
        """Stop animation"""
        if self._timer:
            self.killTimer(self._timer)
        super().cleanup_theme()


# ==================== CONVENIENCE FUNCTIONS ====================

def create_button(text: str, style: str = "primary", size: str = "md",
                 parent=None, on_click: Optional[Callable] = None) -> EnhancedButton:
    """Quick button creation helper"""
    btn = EnhancedButton(text, parent, style=style, size=size)
    if on_click:
        btn.clicked.connect(on_click)
    return btn


def create_label(text: str, variant: str = "primary", parent=None) -> EnhancedLabel:
    """Quick label creation helper"""
    return EnhancedLabel(text, parent, variant=variant)


def create_input(placeholder: str = "", parent=None) -> EnhancedInput:
    """Quick input creation helper"""
    return EnhancedInput(placeholder, parent)


def create_card(parent=None, elevation: str = "md", hoverable: bool = False) -> EnhancedCard:
    """Quick card creation helper"""
    return EnhancedCard(parent, elevation=elevation, hoverable=hoverable)
