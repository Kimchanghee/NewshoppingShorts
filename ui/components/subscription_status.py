"""
Subscription status widget for PyQt6
Uses the design system v2 for consistent styling.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve

from ui.design_system_v2 import get_design_system, get_color


class SubscriptionStatusWidget(QWidget):
    requestSubscription = pyqtSignal()

    def __init__(self, parent=None, on_request_subscription=None, theme_manager=None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._on_request_subscription = on_request_subscription
        self._is_trial = True
        self._work_count = 3
        self._work_used = 0
        self._can_work = True
        self._has_pending_request = False
        self._pulse_animation = None
        self._opacity_effect = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self.ds.spacing.space_3,
            self.ds.spacing.space_2,
            self.ds.spacing.space_3,
            self.ds.spacing.space_2
        )
        
        self.type_label = QLabel("체험계정")
        self.type_label.setStyleSheet(f"font-weight: bold; color: {get_color('warning')};")
        layout.addWidget(self.type_label)
        
        self.count_label = QLabel("남은 횟수:")
        self.count_label.setStyleSheet(f"color: {get_color('text_secondary')};")
        layout.addWidget(self.count_label)
        
        self.count_value = QLabel("3/3")
        self.count_value.setStyleSheet(f"font-weight: bold; color: {get_color('primary')};")
        layout.addWidget(self.count_value)
        
        layout.addStretch()
        
        self.request_btn = QPushButton("구독 신청")
        self.request_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('primary')};
                color: {get_color('surface')};
                border-radius: {self.ds.radius.sm}px;
                padding: {self.ds.spacing.space_1}px {self.ds.spacing.space_3}px;
                font-size: {self.ds.typography.size_xs}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {get_color('secondary')};
            }}
        """)
        self.request_btn.clicked.connect(self._on_request_click)
        layout.addWidget(self.request_btn)
        
        self.pending_label = QLabel("신청 대기중")
        self.pending_label.setStyleSheet(f"color: {get_color('info')}; font-size: {self.ds.typography.size_xs}px;")
        self.pending_label.hide()
        layout.addWidget(self.pending_label)

    def _on_request_click(self):
        if self._on_request_subscription:
            self._on_request_subscription()
        self.requestSubscription.emit()

    def update_status(self, is_trial=True, work_count=3, work_used=0, can_work=True, has_pending_request=False):
        self._is_trial = is_trial
        self._work_count = work_count
        self._work_used = work_used
        self._can_work = can_work
        self._has_pending_request = has_pending_request
        self._update_display()

    def _update_display(self):
        is_unlimited = self._work_count == -1

        if is_unlimited:
            self.type_label.setText("구독")
            self.type_label.setStyleSheet(f"font-weight: bold; color: {get_color('success')};")
            self.count_value.setText("무제한")
            self.count_value.setStyleSheet(f"font-weight: bold; color: {get_color('success')};")
            self.request_btn.hide()
            self.pending_label.hide()
            self._stop_pulse_animation()
        else:
            self.type_label.setText("체험계정")
            self.type_label.setStyleSheet(f"font-weight: bold; color: {get_color('warning')};")
            remaining = max(0, self._work_count - self._work_used)
            self.count_value.setText(f"{remaining}/{self._work_count}")

            # Color coding based on remaining count
            color, should_pulse = self._get_urgency_color(remaining)
            self.count_value.setStyleSheet(f"font-weight: bold; color: {color};")

            # Start or stop pulsing animation based on urgency
            if should_pulse:
                self._start_pulse_animation()
            else:
                self._stop_pulse_animation()

            if self._has_pending_request:
                self.request_btn.hide()
                self.pending_label.show()
            else:
                self.request_btn.show()
                self.pending_label.hide()

    def _get_urgency_color(self, remaining: int) -> tuple[str, bool]:
        """
        Get color and pulse flag based on remaining trial count.
        Returns (color_hex, should_pulse)
        """
        if remaining >= 3:
            # Green - healthy status (3-5 uses remaining)
            return get_color('success'), False
        elif remaining >= 1:
            # Yellow/Orange - warning (1-2 uses remaining)
            return get_color('warning'), False
        else:
            # Red - critical (0 uses remaining)
            return get_color('error'), True

    def _start_pulse_animation(self):
        """Start pulsing animation for critical state (0 remaining)"""
        if self._pulse_animation is not None:
            return  # Animation already running

        # Create opacity effect if not exists
        if self._opacity_effect is None:
            self._opacity_effect = QGraphicsOpacityEffect(self.count_value)
            self.count_value.setGraphicsEffect(self._opacity_effect)

        # Create pulsing animation using design system duration
        self._pulse_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._pulse_animation.setDuration(1000)  # 1 second per pulse
        self._pulse_animation.setStartValue(1.0)  # Full opacity
        self._pulse_animation.setEndValue(0.5)    # Half opacity
        self._pulse_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._pulse_animation.setLoopCount(-1)    # Infinite loop

        # Start the animation
        self._pulse_animation.start()

    def _stop_pulse_animation(self):
        """Stop pulsing animation and restore normal opacity"""
        if self._pulse_animation is not None:
            self._pulse_animation.stop()
            self._pulse_animation = None

        # Restore full opacity
        if self._opacity_effect is not None:
            self._opacity_effect.setOpacity(1.0)

    def closeEvent(self, event):
        """Clean up animation when widget is destroyed"""
        self._stop_pulse_animation()
        super().closeEvent(event)
