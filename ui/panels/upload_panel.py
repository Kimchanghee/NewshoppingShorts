# -*- coding: utf-8 -*-
"""
Upload Panel for PyQt6
Manages auto-upload settings for YouTube and other platforms (COMING SOON).
"""
from typing import Optional, TYPE_CHECKING
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QSlider, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system, get_color
from ui.components.base_widget import ThemedMixin
from managers.settings_manager import get_settings_manager

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI


class PlatformUploadSection(QFrame):
    """Section for a single platform's upload settings"""

    def __init__(
        self,
        platform_id: str,
        platform_name: str,
        platform_icon: str,
        platform_color: str,
        is_connected: bool = False,
        coming_soon: bool = False,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.platform_id = platform_id
        self._is_connected = is_connected
        self._coming_soon = coming_soon
        self.ds = get_design_system()

        self._setup_ui(platform_name, platform_icon, platform_color)

    def _setup_ui(self, name: str, icon: str, color: str):
        ds = self.ds
        c = ds.colors

        # Base styling
        bg_color = c.surface_variant if self._coming_soon else c.surface
        self.setStyleSheet(f"""
            PlatformUploadSection {{
                background-color: {bg_color};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()

        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI Symbol", 18))
        icon_label.setFixedSize(36, 36)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background-color: {color};
            color: white;
            border-radius: 6px;
            border: none;
        """)
        header_layout.addWidget(icon_label)

        # Title
        title_label = QLabel(name)
        title_label.setFont(QFont(ds.typography.font_family_primary, 14, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {c.text_primary}; border: none; background: transparent;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # COMING SOON badge
        if self._coming_soon:
            badge = QLabel("출시 예정")
            badge.setFont(QFont(ds.typography.font_family_primary, 10, QFont.Weight.Bold))
            badge.setStyleSheet(f"""
                background-color: {c.surface};
                color: {c.text_muted};
                border: 1px solid {c.border_light};
                border-radius: 4px;
                padding: 4px 8px;
            """)
            header_layout.addWidget(badge)

        layout.addLayout(header_layout)

        # Content (only for non-COMING SOON)
        if not self._coming_soon:
            self._setup_platform_content(layout)
        else:
            # Placeholder text
            placeholder = QLabel("이 기능은 곧 출시될 예정입니다.")
            placeholder.setFont(QFont(ds.typography.font_family_primary, 11))
            placeholder.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
            layout.addWidget(placeholder)

    def _setup_platform_content(self, layout: QVBoxLayout):
        """Setup platform-specific content - override in subclasses"""
        pass


class YouTubeUploadSection(PlatformUploadSection):
    """YouTube upload settings section"""

    def __init__(self, gui: "VideoAnalyzerGUI", parent: Optional[QWidget] = None):
        self.gui = gui
        self.settings = get_settings_manager()
        is_connected = self.settings.get_youtube_connected()
        super().__init__(
            platform_id="youtube",
            platform_name="유튜브",
            platform_icon="▶",
            platform_color="#FF0000",
            is_connected=is_connected,
            coming_soon=False,
            parent=parent
        )

    def _setup_platform_content(self, layout: QVBoxLayout):
        ds = self.ds
        c = ds.colors

        is_connected = self.settings.get_youtube_connected()

        if not is_connected:
            # Not connected - show message
            msg_layout = QVBoxLayout()
            msg_layout.setSpacing(8)

            msg = QLabel("유튜브 채널이 연결되지 않았습니다.")
            msg.setFont(QFont(ds.typography.font_family_primary, 12))
            msg.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
            msg_layout.addWidget(msg)

            link_btn = QPushButton("설정에서 채널 연결하기 →")
            link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            link_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c.primary};
                    border: none;
                    font-size: 12px;
                    font-weight: 500;
                    text-align: left;
                    padding: 4px 0;
                }}
                QPushButton:hover {{
                    text-decoration: underline;
                }}
            """)
            link_btn.clicked.connect(self._go_to_settings)
            msg_layout.addWidget(link_btn)

            layout.addLayout(msg_layout)
        else:
            # Connected - show settings
            channel_info = self.settings.get_youtube_channel_info()
            channel_name = channel_info.get("channel_name", "연결된 채널")

            # Connected status
            status_label = QLabel(f"✓ 연결됨: {channel_name}")
            status_label.setFont(QFont(ds.typography.font_family_primary, 11))
            status_label.setStyleSheet(f"color: {c.success}; border: none; background: transparent;")
            layout.addWidget(status_label)

            # Separator
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background-color: {c.border_light};")
            layout.addWidget(sep)

            # Auto-upload toggle
            auto_layout = QHBoxLayout()

            self.auto_upload_checkbox = QCheckBox("자동 업로드 활성화")
            self.auto_upload_checkbox.setFont(QFont(ds.typography.font_family_primary, 12))
            self.auto_upload_checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: {c.text_primary};
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border-radius: 4px;
                    border: 2px solid {c.border_light};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {c.primary};
                    border-color: {c.primary};
                }}
            """)
            self.auto_upload_checkbox.setChecked(self.settings.get_youtube_auto_upload())
            self.auto_upload_checkbox.stateChanged.connect(self._on_auto_upload_changed)
            auto_layout.addWidget(self.auto_upload_checkbox)

            auto_layout.addStretch()
            layout.addLayout(auto_layout)

            # Upload interval settings
            interval_widget = QWidget()
            interval_layout = QVBoxLayout(interval_widget)
            interval_layout.setContentsMargins(0, 8, 0, 0)
            interval_layout.setSpacing(8)

            interval_header = QHBoxLayout()
            interval_label = QLabel("업로드 간격:")
            interval_label.setFont(QFont(ds.typography.font_family_primary, 11))
            interval_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
            interval_header.addWidget(interval_label)

            self.interval_value_label = QLabel("1시간")
            self.interval_value_label.setFont(QFont(ds.typography.font_family_primary, 11, QFont.Weight.Bold))
            self.interval_value_label.setStyleSheet(f"color: {c.text_primary}; border: none; background: transparent;")
            interval_header.addWidget(self.interval_value_label)

            interval_header.addStretch()
            interval_layout.addLayout(interval_header)

            # Slider (1-4 hours)
            self.interval_slider = QSlider(Qt.Orientation.Horizontal)
            self.interval_slider.setMinimum(1)
            self.interval_slider.setMaximum(4)
            current_interval = self.settings.get_youtube_upload_interval() // 60
            self.interval_slider.setValue(current_interval)
            self.interval_slider.setStyleSheet(f"""
                QSlider::groove:horizontal {{
                    height: 6px;
                    background: {c.surface_variant};
                    border-radius: 3px;
                }}
                QSlider::handle:horizontal {{
                    background: {c.primary};
                    width: 16px;
                    height: 16px;
                    margin: -5px 0;
                    border-radius: 8px;
                }}
                QSlider::sub-page:horizontal {{
                    background: {c.primary};
                    border-radius: 3px;
                }}
            """)
            self.interval_slider.valueChanged.connect(self._on_interval_changed)
            interval_layout.addWidget(self.interval_slider)

            # Interval ticks
            ticks_layout = QHBoxLayout()
            for h in [1, 2, 3, 4]:
                tick = QLabel(f"{h}시간")
                tick.setFont(QFont(ds.typography.font_family_primary, 9))
                tick.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
                tick.setAlignment(Qt.AlignmentFlag.AlignCenter)
                ticks_layout.addWidget(tick)
            interval_layout.addLayout(ticks_layout)

            layout.addWidget(interval_widget)
            self._interval_widget = interval_widget

            # Daily limit info
            limit_label = QLabel("* 유튜브 정책: 24시간 내 최대 6개 영상 업로드 가능")
            limit_label.setFont(QFont(ds.typography.font_family_primary, 10))
            limit_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
            layout.addWidget(limit_label)

            # Update interval widget visibility
            self._update_interval_visibility()
            self._update_interval_label()

    def _go_to_settings(self):
        """Navigate to settings page"""
        if self.gui and hasattr(self.gui, '_on_step_selected'):
            self.gui._on_step_selected("settings")

    def _on_auto_upload_changed(self, state: int):
        """Handle auto-upload checkbox change"""
        enabled = self.auto_upload_checkbox.isChecked()
        self.settings.set_youtube_auto_upload(enabled)

        # Update app state
        if self.gui and hasattr(self.gui, 'state'):
            self.gui.state.youtube_auto_upload = enabled

        self._update_interval_visibility()

    def _update_interval_visibility(self):
        """Show/hide interval widget based on auto-upload state"""
        if hasattr(self, '_interval_widget'):
            self._interval_widget.setVisible(self.auto_upload_checkbox.isChecked())

    def _on_interval_changed(self, value: int):
        """Handle interval slider change"""
        interval_minutes = value * 60
        self.settings.set_youtube_upload_interval(interval_minutes)

        if self.gui and hasattr(self.gui, 'state'):
            self.gui.state.youtube_upload_interval_minutes = interval_minutes

        self._update_interval_label()

    def _update_interval_label(self):
        """Update the interval value label"""
        if hasattr(self, 'interval_slider') and hasattr(self, 'interval_value_label'):
            hours = self.interval_slider.value()
            self.interval_value_label.setText(f"{hours}시간")

    def refresh(self):
        """Refresh the section based on current settings"""
        # Update checkbox state from settings
        if hasattr(self, 'auto_upload_checkbox'):
            current = self.settings.get_youtube_auto_upload()
            if self.auto_upload_checkbox.isChecked() != current:
                self.auto_upload_checkbox.blockSignals(True)
                self.auto_upload_checkbox.setChecked(current)
                self.auto_upload_checkbox.blockSignals(False)
                self._update_interval_visibility()

        # Update slider value
        if hasattr(self, 'interval_slider'):
            current_interval = self.settings.get_youtube_upload_interval() // 60
            if self.interval_slider.value() != current_interval:
                self.interval_slider.blockSignals(True)
                self.interval_slider.setValue(current_interval)
                self.interval_slider.blockSignals(False)
                self._update_interval_label()


class UploadPanel(QFrame, ThemedMixin):
    """Upload settings panel with platform sections"""

    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self._create_widgets()
        self._apply_theme()

    def _create_widgets(self):
        ds = self.ds
        c = ds.colors

        # Main layout with scroll
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {c.background}; border: none;")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # Description
        desc = QLabel("완성된 영상을 소셜 미디어에 자동으로 업로드합니다.\n채널 연결은 설정 페이지에서 할 수 있습니다.")
        desc.setFont(QFont(ds.typography.font_family_primary, 11))
        desc.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        desc.setWordWrap(True)
        content_layout.addWidget(desc)

        # YouTube section (COMING SOON)
        youtube_section = PlatformUploadSection(
            platform_id="youtube",
            platform_name="유튜브",
            platform_icon="▶",
            platform_color="#FF0000",
            coming_soon=True,
            parent=content
        )
        content_layout.addWidget(youtube_section)

        # TikTok section (COMING SOON)
        tiktok_section = PlatformUploadSection(
            platform_id="tiktok",
            platform_name="틱톡",
            platform_icon="♪",
            platform_color="#000000",
            coming_soon=True,
            parent=content
        )
        content_layout.addWidget(tiktok_section)

        # Instagram section (COMING SOON)
        instagram_section = PlatformUploadSection(
            platform_id="instagram",
            platform_name="인스타그램",
            platform_icon="📷",
            platform_color="#E1306C",
            coming_soon=True,
            parent=content
        )
        content_layout.addWidget(instagram_section)

        # Threads section (COMING SOON)
        threads_section = PlatformUploadSection(
            platform_id="threads",
            platform_name="스레드",
            platform_icon="@",
            platform_color="#000000",
            coming_soon=True,
            parent=content
        )
        content_layout.addWidget(threads_section)

        # X section (COMING SOON)
        x_section = PlatformUploadSection(
            platform_id="x",
            platform_name="X (트위터)",
            platform_icon="𝕏",
            platform_color="#000000",
            coming_soon=True,
            parent=content
        )
        content_layout.addWidget(x_section)

        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _apply_theme(self):
        c = self.ds.colors
        self.setStyleSheet(f"background-color: {c.background}; border: none;")

    def refresh(self):
        """Refresh the panel when navigated to"""
        return
