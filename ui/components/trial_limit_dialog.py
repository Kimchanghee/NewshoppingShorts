# -*- coding: utf-8 -*-
"""
Trial Limit Dialog Component for PyQt6
Modern dialog shown when user exceeds trial usage limit
"""
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ..theme_manager import ThemeManager, get_theme_manager


class TrialLimitDialog(QDialog):
    """
    Dialog shown when user exceeds trial limit

    Displays usage information and prompts user to subscribe
    for unlimited access.

    Signals:
        subscription_requested: Emitted when user clicks subscribe button
    """

    subscription_requested = pyqtSignal()

    def __init__(
        self,
        parent=None,
        used: int = 5,
        total: int = 5,
        theme_manager: Optional[ThemeManager] = None
    ):
        """
        Initialize trial limit dialog

        Args:
            parent: Parent widget
            used: Number of trials used
            total: Total number of trials allowed
            theme_manager: Optional theme manager instance
        """
        super().__init__(parent)
        self.used = used
        self.total = total
        self._theme_manager = theme_manager or get_theme_manager()
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        # Dialog configuration
        self.setWindowTitle("체험판 한도 초과")
        self.setModal(True)
        self.setMinimumWidth(450)

        # Get theme colors
        bg_main = self._theme_manager.get_color("bg_main")
        bg_card = self._theme_manager.get_color("bg_card")
        text_primary = self._theme_manager.get_color("text_primary")
        text_secondary = self._theme_manager.get_color("text_secondary")
        primary = self._theme_manager.get_color("primary")
        error = self._theme_manager.get_color("error")
        error_light = self._theme_manager.get_color("error_bg")
        border_light = self._theme_manager.get_color("border_light")

        # Main layout with no margins (frame will have margins)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Set dialog background
        self.setStyleSheet(f"QDialog {{ background-color: {bg_main}; border: none; }}")

        # Container frame for rounded corners and shadow effect
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_card};
                border: 1px solid {border_light};
                border-radius: 12px;
                margin: 2px;
            }}
        """)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 24, 24, 24)
        container_layout.setSpacing(20)

        # Header with icon and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Warning icon
        icon_label = QLabel("!")
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {error};
                color: white;
                border-radius: 16px;
                font-weight: bold;
                font-size: 18px;
                font-family: Inter, Pretendard, sans-serif;
            }}
        """)
        header_layout.addWidget(icon_label)

        # Title
        title_label = QLabel("체험판 한도 초과")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {text_primary};
                font-size: 18px;
                font-weight: bold;
                background: transparent;
                font-family: Inter, Pretendard, sans-serif;
            }}
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        container_layout.addLayout(header_layout)

        # Usage information box
        usage_box = QFrame()
        usage_box.setStyleSheet(f"""
            QFrame {{
                background-color: {error_light};
                border: 1px solid {error};
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        usage_layout = QVBoxLayout(usage_box)
        usage_layout.setContentsMargins(16, 16, 16, 16)
        usage_layout.setSpacing(8)

        # Usage message
        usage_label = QLabel(f"체험판 사용 횟수를 모두 소진했습니다 ({self.used}/{self.total})")
        usage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        usage_label.setStyleSheet(f"""
            QLabel {{
                color: {error};
                font-size: 14px;
                font-weight: bold;
                background: transparent;
                font-family: Inter, Pretendard, sans-serif;
            }}
        """)
        usage_layout.addWidget(usage_label)

        container_layout.addWidget(usage_box)

        # Explanation message
        explanation_label = QLabel(
            "추가 동영상 제작을 원하시면 구독이 필요합니다.\n"
            "구독 시 무제한으로 사용할 수 있습니다."
        )
        explanation_label.setWordWrap(True)
        explanation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        explanation_label.setStyleSheet(f"""
            QLabel {{
                color: {text_secondary};
                font-size: 14px;
                line-height: 1.6;
                background: transparent;
                font-family: Inter, Pretendard, sans-serif;
            }}
        """)
        container_layout.addWidget(explanation_label)

        # Spacer for better visual balance
        container_layout.addSpacing(8)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()

        # Cancel button (secondary style)
        cancel_btn = QPushButton("취소")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.setMinimumHeight(40)

        btn_secondary = self._theme_manager.get_color("btn_secondary")
        btn_secondary_hover = self._theme_manager.get_color("btn_secondary_hover")
        btn_secondary_text = self._theme_manager.get_color("btn_secondary_text")

        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_secondary};
                color: {btn_secondary_text};
                border: 1px solid {border_light};
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                font-family: Inter, Pretendard, sans-serif;
            }}
            QPushButton:hover {{
                background-color: {btn_secondary_hover};
                border-color: {primary};
            }}
            QPushButton:pressed {{
                background-color: {border_light};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # Subscribe button (primary style)
        subscribe_btn = QPushButton("구독 신청하기")
        subscribe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        subscribe_btn.setMinimumWidth(130)
        subscribe_btn.setMinimumHeight(40)

        primary_hover = self._theme_manager.get_color("primary_hover")
        primary_text = self._theme_manager.get_color("primary_text")

        subscribe_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {primary};
                color: {primary_text};
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
                font-family: Inter, Pretendard, sans-serif;
            }}
            QPushButton:hover {{
                background-color: {primary_hover};
            }}
            QPushButton:pressed {{
                background-color: {primary_hover};
                padding-top: 11px;
                padding-bottom: 9px;
            }}
        """)
        subscribe_btn.clicked.connect(self._on_subscribe_clicked)
        button_layout.addWidget(subscribe_btn)

        container_layout.addLayout(button_layout)

        # Add container to main layout
        main_layout.addWidget(container)

        # Adjust size to fit content
        self.adjustSize()

    def _on_subscribe_clicked(self):
        """Handle subscribe button click"""
        self.subscription_requested.emit()
        self.accept()

    def show_and_wait(self) -> bool:
        """
        Show dialog and wait for user response

        Returns:
            True if user clicked subscribe, False if cancelled
        """
        result = self.exec()
        return result == QDialog.DialogCode.Accepted


# Convenience function
def show_trial_limit_dialog(parent=None, used: int = 5, total: int = 5) -> bool:
    """
    Show trial limit dialog and return user's choice

    Args:
        parent: Parent widget
        used: Number of trials used
        total: Total number of trials allowed

    Returns:
        True if user wants to subscribe, False if cancelled
    """
    dialog = TrialLimitDialog(parent, used, total)
    return dialog.show_and_wait()
