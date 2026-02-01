# -*- coding: utf-8 -*-
"""
Trial Limit Dialog Component for PyQt6
Modern dialog shown when user exceeds trial usage limit
Uses the design system v2 for consistent styling.
"""
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system, get_color


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
        theme_manager=None
    ):
        """
        Initialize trial limit dialog

        Args:
            parent: Parent widget
            used: Number of trials used
            total: Total number of trials allowed
            theme_manager: Optional theme manager instance (kept for compatibility)
        """
        super().__init__(parent)
        self.used = used
        self.total = total
        self.ds = get_design_system()
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        # Dialog configuration
        self.setWindowTitle("체험판 한도 초과")
        self.setModal(True)
        self.setMinimumWidth(450)

        # Get colors from design system
        bg_main = get_color('background')
        bg_card = get_color('surface')
        text_primary = get_color('text_primary')
        text_secondary = get_color('text_secondary')
        primary = get_color('primary')
        error = get_color('error')
        border_light = get_color('border_light')

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
                border-radius: {self.ds.border_radius.radius_md}px;
                margin: 2px;
            }}
        """)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6
        )
        container_layout.setSpacing(self.ds.spacing.space_5)

        # Header with icon and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(self.ds.spacing.space_3)

        # Warning icon
        icon_label = QLabel("!")
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {error};
                color: white;
                border-radius: {self.ds.border_radius.radius_full}px;
                font-weight: bold;
                font-size: {self.ds.typography.size_md}px;
                font-family: {self.ds.typography.font_family_primary};
            }}
        """)
        header_layout.addWidget(icon_label)

        # Title
        title_label = QLabel("체험판 한도 초과")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {text_primary};
                font-size: {self.ds.typography.size_md}px;
                font-weight: bold;
                background: transparent;
                font-family: {self.ds.typography.font_family_primary};
            }}
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        container_layout.addLayout(header_layout)

        # Usage information box
        usage_box = QFrame()
        usage_box.setStyleSheet(f"""
            QFrame {{
                background-color: {get_color('surface_variant')};
                border: 1px solid {error};
                border-radius: {self.ds.border_radius.radius_base}px;
                padding: {self.ds.spacing.space_4}px;
            }}
        """)
        usage_layout = QVBoxLayout(usage_box)
        usage_layout.setContentsMargins(
            self.ds.spacing.space_4,
            self.ds.spacing.space_4,
            self.ds.spacing.space_4,
            self.ds.spacing.space_4
        )
        usage_layout.setSpacing(self.ds.spacing.space_2)

        # Usage message
        usage_label = QLabel(f"체험판 사용 횟수를 모두 소진했습니다 ({self.used}/{self.total})")
        usage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        usage_label.setStyleSheet(f"""
            QLabel {{
                color: {error};
                font-size: {self.ds.typography.size_sm}px;
                font-weight: bold;
                background: transparent;
                font-family: {self.ds.typography.font_family_primary};
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
                font-size: {self.ds.typography.size_sm}px;
                line-height: {self.ds.typography.line_height_normal};
                background: transparent;
                font-family: {self.ds.typography.font_family_primary};
            }}
        """)
        container_layout.addWidget(explanation_label)

        # Spacer for better visual balance
        container_layout.addSpacing(self.ds.spacing.space_2)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(self.ds.spacing.space_3)
        button_layout.addStretch()

        # Get button size from design system
        btn_size = self.ds.get_button_size('md')

        # Cancel button (secondary style)
        cancel_btn = QPushButton("취소")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.setMinimumHeight(btn_size.height)

        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('surface_variant')};
                color: {text_primary};
                border: 1px solid {border_light};
                border-radius: {self.ds.border_radius.radius_base}px;
                padding: {self.ds.spacing.space_3}px {self.ds.spacing.space_5}px;
                font-size: {self.ds.typography.size_sm}px;
                font-weight: bold;
                font-family: {self.ds.typography.font_family_primary};
            }}
            QPushButton:hover {{
                background-color: {border_light};
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
        subscribe_btn.setMinimumHeight(btn_size.height)

        subscribe_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {primary};
                color: white;
                border: none;
                border-radius: {self.ds.border_radius.radius_base}px;
                padding: {self.ds.spacing.space_3}px {self.ds.spacing.space_6}px;
                font-size: {self.ds.typography.size_sm}px;
                font-weight: bold;
                font-family: {self.ds.typography.font_family_primary};
            }}
            QPushButton:hover {{
                background-color: {get_color('secondary')};
            }}
            QPushButton:pressed {{
                background-color: {get_color('secondary')};
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
