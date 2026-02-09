# -*- coding: utf-8 -*-
"""
Social Media Authentication Card Component (PyQt6)
Reusable card for social media platform authentication with COMING SOON support.
"""
from typing import Optional, Dict, Any, Callable
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

from ui.design_system_v2 import get_design_system, get_color


# Platform configuration
PLATFORM_CONFIG = {
    "youtube": {
        "name": "유튜브",
        "icon": "▶",
        "color": "#FF0000",
        "description": "구글 계정으로 로그인하여 채널을 연결합니다.",
    },
    "tiktok": {
        "name": "틱톡",
        "icon": "♪",
        "color": "#000000",
        "description": "틱톡 계정을 연결합니다.",
    },
    "instagram": {
        "name": "인스타그램",
        "icon": "📷",
        "color": "#E1306C",
        "description": "인스타그램 계정을 연결합니다.",
    },
    "threads": {
        "name": "스레드",
        "icon": "@",
        "color": "#000000",
        "description": "스레드 계정을 연결합니다.",
    },
    "x": {
        "name": "X (트위터)",
        "icon": "𝕏",
        "color": "#000000",
        "description": "X 계정을 연결합니다.",
    },
}


class SocialAuthCard(QFrame):
    """Social media authentication card with connect/disconnect functionality"""

    connect_clicked = pyqtSignal(str)  # platform_id
    disconnect_clicked = pyqtSignal(str)  # platform_id

    def __init__(
        self,
        platform_id: str,
        is_connected: bool = False,
        channel_info: Optional[Dict[str, Any]] = None,
        coming_soon: bool = False,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.platform_id = platform_id
        self._is_connected = is_connected
        self._channel_info = channel_info or {}
        self._coming_soon = coming_soon
        self.ds = get_design_system()

        self._setup_ui()
        self._update_state()

    def _setup_ui(self):
        """Setup the card UI"""
        ds = self.ds
        c = ds.colors
        config = PLATFORM_CONFIG.get(self.platform_id, {})

        # Card styling
        self.setStyleSheet(f"""
            SocialAuthCard {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Platform icon
        icon_label = QLabel(config.get("icon", "?"))
        icon_label.setFont(QFont("Segoe UI Symbol", 20))
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background-color: {config.get('color', '#666')};
            color: white;
            border-radius: 8px;
            border: none;
        """)
        layout.addWidget(icon_label)

        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Platform name
        name_label = QLabel(config.get("name", self.platform_id.title()))
        name_label.setFont(QFont(ds.typography.font_family_primary, 13, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {c.text_primary}; border: none; background: transparent;")
        info_layout.addWidget(name_label)

        # Status / Description
        self._status_label = QLabel(config.get("description", ""))
        self._status_label.setFont(QFont(ds.typography.font_family_primary, 11))
        self._status_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        info_layout.addWidget(self._status_label)

        layout.addLayout(info_layout, stretch=1)

        # Action button / COMING SOON badge
        self._action_btn = QPushButton("연결")
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setFixedHeight(36)
        self._action_btn.setMinimumWidth(80)
        self._action_btn.clicked.connect(self._on_action_click)
        layout.addWidget(self._action_btn)

        # COMING SOON overlay
        if self._coming_soon:
            self._apply_coming_soon_style()

    def _apply_coming_soon_style(self):
        """Apply COMING SOON styling"""
        c = self.ds.colors

        # Disable and gray out
        self._action_btn.setEnabled(False)
        self._action_btn.setText("출시 예정")
        self._action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_muted};
                border: 1px solid {c.border_light};
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
                padding: 0 12px;
            }}
        """)

        # Gray out the card
        self.setStyleSheet(f"""
            SocialAuthCard {{
                background-color: {c.surface_variant};
                border: 1px solid {c.border_light};
                border-radius: {self.ds.radius.base}px;
                opacity: 0.7;
            }}
        """)

    def _update_state(self):
        """Update UI based on connection state"""
        if self._coming_soon:
            return

        ds = self.ds
        c = ds.colors
        config = PLATFORM_CONFIG.get(self.platform_id, {})

        if self._is_connected:
            # Connected state
            channel_name = self._channel_info.get("name", self._channel_info.get("channel_name", "연결됨"))
            self._status_label.setText(f"✓ {channel_name}")
            self._status_label.setStyleSheet(f"color: {c.success}; border: none; background: transparent;")

            self._action_btn.setText("연결 해제")
            self._action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c.error};
                    border: 1px solid {c.error};
                    border-radius: 6px;
                    font-weight: 500;
                    padding: 0 16px;
                }}
                QPushButton:hover {{
                    background-color: {c.error};
                    color: white;
                }}
            """)
        else:
            # Disconnected state
            self._status_label.setText(config.get("description", ""))
            self._status_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")

            self._action_btn.setText("연결")
            self._action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {config.get('color', c.primary)};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    padding: 0 16px;
                }}
                QPushButton:hover {{
                    opacity: 0.9;
                }}
            """)

    def _on_action_click(self):
        """Handle action button click"""
        if self._is_connected:
            self.disconnect_clicked.emit(self.platform_id)
        else:
            self.connect_clicked.emit(self.platform_id)

    def set_connected(self, connected: bool, channel_info: Optional[Dict[str, Any]] = None):
        """Update connection state"""
        self._is_connected = connected
        self._channel_info = channel_info or {}
        self._update_state()

    @property
    def is_connected(self) -> bool:
        return self._is_connected
