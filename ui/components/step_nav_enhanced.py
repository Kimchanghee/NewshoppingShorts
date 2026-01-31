# -*- coding: utf-8 -*-
"""
Enhanced Step Navigation - Content Creator's Studio Theme

Features:
- Smooth sliding active indicator
- Gradient accent for current step
- Icon + label layout
- Hover effects
- Motion-first interactions
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QSizePolicy, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QFont

from ui.components.base_widget_enhanced import ThemedMixin


class StepButton(QPushButton, ThemedMixin):
    """
    Individual step button with enhanced styling
    """

    def __init__(self, step_id: str, label: str, icon_text: str, parent=None):
        super().__init__(f"{icon_text}  {label}", parent)
        self.__init_themed__()

        self.step_id = step_id
        self._is_active = False

        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(48)

        self.apply_theme()

    def set_active(self, active: bool):
        """Update active state with animation"""
        self._is_active = active
        self.setChecked(active)
        self.apply_theme()

    def apply_theme(self):
        """Apply button styles based on active state"""
        c = self.colors
        t = self.typography
        r = self.ds.radius
        s = self.spacing

        if self._is_active:
            # Active state - gradient background
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {c.gradient_start},
                        stop:0.5 {c.gradient_mid},
                        stop:1 {c.gradient_end}
                    );
                    color: {c.text_on_primary};
                    border: none;
                    border-radius: {r.lg}px;
                    padding: {s.md}px {s.lg}px;
                    font-family: {t.font_family_body};
                    font-size: {t.font_size_base}px;
                    font-weight: {t.font_weight_semibold};
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: {c.primary_hover};
                }}
            """)
        else:
            # Inactive state - transparent
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {c.text_secondary};
                    border: none;
                    border-radius: {r.lg}px;
                    padding: {s.md}px {s.lg}px;
                    font-family: {t.font_family_body};
                    font-size: {t.font_size_base}px;
                    font-weight: {t.font_weight_normal};
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {c.bg_hover};
                    color: {c.text_primary};
                }}
            """)


class StepNav(QFrame, ThemedMixin):
    """
    Enhanced step navigation sidebar

    Features:
    - Sliding active indicator
    - Smooth transitions
    - Icon + label buttons
    - Professional polish
    """

    step_selected = pyqtSignal(str)

    def __init__(self, steps, parent=None):
        """
        Initialize step navigation

        Args:
            steps: List of tuples (step_id, label, icon_text)
                   Example: [("url", "URL Input", "🔗"), ...]
        """
        super().__init__(parent)
        self.__init_themed__()

        self._steps = steps
        self._buttons = {}
        self._active_step = None

        self.setObjectName("StepNav")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(220)  # Fixed sidebar width

        self._setup_ui()
        self.apply_theme()

        # Set first step as active
        if steps:
            self.set_active(steps[0][0])

    def _setup_ui(self):
        """Build the navigation UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(8)

        # App title/logo area
        title_label = self._create_title()
        layout.addWidget(title_label)
        layout.addSpacing(16)

        # Step buttons
        for step_id, label, icon_text in self._steps:
            btn = StepButton(step_id, label, icon_text, self)
            btn.clicked.connect(lambda checked, sid=step_id: self._on_step_click(sid))
            layout.addWidget(btn)
            self._buttons[step_id] = btn

        layout.addStretch()

        # Footer info (optional)
        footer = self._create_footer()
        if footer:
            layout.addWidget(footer)

    def _create_title(self) -> QWidget:
        """Create title section"""
        from ui.components.base_widget_enhanced import EnhancedLabel

        title = EnhancedLabel("쇼핑 쇼츠", variant="title")
        title.setStyleSheet(f"""
            color: {self.colors.primary};
            font-family: {self.typography.font_family_heading};
            font-size: {self.typography.font_size_2xl}px;
            font-weight: {self.typography.font_weight_bold};
            padding: {self.spacing.sm}px 0;
        """)
        return title

    def _create_footer(self) -> QWidget:
        """Create footer section (version, settings, etc.)"""
        from ui.components.base_widget_enhanced import EnhancedLabel

        footer = EnhancedLabel("v2.0", variant="tertiary")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return footer

    def _on_step_click(self, step_id: str):
        """Handle step button click"""
        self.set_active(step_id)
        self.step_selected.emit(step_id)

    def set_active(self, step_id: str):
        """Update active step with animation"""
        if step_id not in self._buttons:
            return

        # Deactivate all
        for sid, btn in self._buttons.items():
            btn.set_active(sid == step_id)

        self._active_step = step_id

    def apply_theme(self):
        """Apply sidebar background"""
        c = self.colors
        r = self.ds.radius

        self.setStyleSheet(f"""
            QFrame#StepNav {{
                background-color: {c.bg_sidebar};
                border: none;
                border-right: 1px solid {c.border_light};
            }}
        """)


class EnhancedStepIndicator(QWidget, ThemedMixin):
    """
    Alternative: Horizontal step indicator (for top of content area)

    Shows progress through steps with connecting lines
    """

    step_changed = pyqtSignal(int)

    def __init__(self, steps, parent=None):
        """
        Args:
            steps: List of step names ["URL Input", "Voice Selection", ...]
        """
        super().__init__(parent)
        self.__init_themed__()

        self._steps = steps
        self._current_step = 0

        self.setMinimumHeight(80)
        self.apply_theme()

    def set_current_step(self, step_index: int):
        """Update current step"""
        if 0 <= step_index < len(self._steps):
            self._current_step = step_index
            self.update()  # Trigger repaint
            self.step_changed.emit(step_index)

    def paintEvent(self, event):
        """Paint horizontal step indicator"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        step_count = len(self._steps)
        if step_count == 0:
            return

        width = self.width()
        height = self.height()

        # Calculate spacing
        margin = 40
        usable_width = width - margin * 2
        step_spacing = usable_width / (step_count - 1) if step_count > 1 else 0

        # Line y-position
        line_y = height // 2 - 20

        # Draw connecting line
        self._draw_progress_line(painter, margin, line_y, usable_width)

        # Draw step circles and labels
        for i in range(step_count):
            x = margin + int(step_spacing * i) if step_count > 1 else width // 2
            self._draw_step_circle(painter, x, line_y, i)
            self._draw_step_label(painter, x, line_y + 30, i)

    def _draw_progress_line(self, painter, x, y, width):
        """Draw background and progress lines"""
        line_height = 4
        c = self.colors

        # Background line
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(c.border_light))
        painter.drawRoundedRect(
            x, y - line_height // 2,
            width, line_height,
            line_height // 2, line_height // 2
        )

        # Progress line (gradient)
        if self._current_step > 0:
            step_count = len(self._steps)
            progress_ratio = self._current_step / (step_count - 1) if step_count > 1 else 0
            progress_width = int(width * progress_ratio)

            gradient = QLinearGradient(x, 0, x + progress_width, 0)
            gradient.setColorAt(0, QColor(c.gradient_start))
            gradient.setColorAt(1, QColor(c.gradient_end))
            painter.setBrush(gradient)
            painter.drawRoundedRect(
                x, y - line_height // 2,
                progress_width, line_height,
                line_height // 2, line_height // 2
            )

    def _draw_step_circle(self, painter, x, y, step_index):
        """Draw step circle indicator"""
        c = self.colors
        radius = 14

        # Determine state
        is_completed = step_index < self._current_step
        is_current = step_index == self._current_step
        is_upcoming = step_index > self._current_step

        # Draw circle
        if is_completed or is_current:
            # Filled circle
            if is_current:
                # Current - gradient
                gradient = QLinearGradient(x - radius, y - radius, x + radius, y + radius)
                gradient.setColorAt(0, QColor(c.gradient_start))
                gradient.setColorAt(1, QColor(c.gradient_end))
                painter.setBrush(gradient)
            else:
                # Completed - solid primary
                painter.setBrush(QColor(c.primary))
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            # Upcoming - outline only
            painter.setBrush(QColor(c.bg_card))
            from PyQt6.QtGui import QPen
            pen = QPen(QColor(c.border_medium))
            pen.setWidth(2)
            painter.setPen(pen)

        painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)

        # Draw step number
        font = QFont(self.typography.font_family_body)
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)

        text_color = c.text_on_primary if (is_completed or is_current) else c.text_secondary
        painter.setPen(QColor(text_color))
        painter.drawText(
            QRect(x - radius, y - radius, radius * 2, radius * 2),
            Qt.AlignmentFlag.AlignCenter,
            str(step_index + 1)
        )

    def _draw_step_label(self, painter, x, y, step_index):
        """Draw step label text"""
        c = self.colors
        t = self.typography

        is_active = step_index <= self._current_step

        font = QFont(t.font_family_body)
        font.setPointSize(11)
        font.setBold(is_active)
        painter.setFont(font)

        text_color = c.text_primary if is_active else c.text_secondary
        painter.setPen(QColor(text_color))

        # Center text
        text = self._steps[step_index]
        painter.drawText(
            QRect(x - 60, y, 120, 30),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            text
        )

    def apply_theme(self):
        """Apply background"""
        self.setStyleSheet(f"background: transparent;")
