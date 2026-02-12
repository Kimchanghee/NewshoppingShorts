# -*- coding: utf-8 -*-
"""
Social Media Upload Settings Panel (PyQt6)

Provides channel connection, per-channel upload prompts (title, description,
hashtags), and YouTube-specific comment auto-upload settings.
"""
from typing import Optional, Dict, TYPE_CHECKING
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QSlider, QCheckBox, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system, get_color
from ui.components.base_widget import ThemedMixin
from ui.components.social_auth_card import SocialAuthCard, PLATFORM_CONFIG
from managers.settings_manager import get_settings_manager

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI

from utils.logging_config import get_logger
logger = get_logger(__name__)


class PromptInputGroup(QFrame):
    """Reusable group of prompt text inputs for a platform (title, description, hashtags)."""

    def __init__(self, platform_id: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.platform_id = platform_id
        self.ds = get_design_system()
        self.settings = get_settings_manager()
        self._setup_ui()
        self._load_prompts()

    def _setup_ui(self):
        ds = self.ds
        c = ds.colors

        self.setStyleSheet(f"""
            PromptInputGroup {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Section title
        title = QLabel("업로드 프롬프트 설정")
        title.setFont(QFont(ds.typography.font_family_primary, 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {c.text_primary}; border: none; background: transparent;")
        layout.addWidget(title)

        desc = QLabel("자동 업로드 시 AI가 아래 프롬프트를 참고하여 제목, 게시글, 해시태그를 작성합니다.")
        desc.setWordWrap(True)
        desc.setFont(QFont(ds.typography.font_family_primary, 10))
        desc.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
        layout.addWidget(desc)

        input_style = f"""
            QTextEdit {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 8px 10px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-size: 12px;
            }}
            QTextEdit:focus {{
                border: 1px solid {c.primary};
            }}
        """

        # Title prompt
        self.title_prompt = self._create_prompt_field(
            layout, "제목 프롬프트",
            "예: 쇼핑 꿀템 소개 영상의 제목을 작성해주세요. 궁금증을 유발하는 짧은 제목으로 만들어주세요.",
            input_style, max_height=60
        )

        # Description prompt
        self.description_prompt = self._create_prompt_field(
            layout, "게시글(설명) 프롬프트",
            "예: 상품의 장점을 강조하면서 구매 링크 클릭을 유도하는 설명을 작성해주세요.",
            input_style, max_height=80
        )

        # Hashtag prompt
        self.hashtag_prompt = self._create_prompt_field(
            layout, "해시태그 프롬프트",
            "예: 쇼핑, 추천, 꿀템 등 관련 해시태그를 10개 이내로 생성해주세요.",
            input_style, max_height=60
        )

        # Save button
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.save_btn = QPushButton("프롬프트 저장")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                padding: 8px 20px;
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {c.secondary};
            }}
        """)
        self.save_btn.clicked.connect(self._save_prompts)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

    def _create_prompt_field(self, parent_layout: QVBoxLayout, label_text: str,
                             placeholder: str, style: str, max_height: int = 60) -> QTextEdit:
        """Create a labeled text input for a prompt."""
        ds = self.ds
        c = ds.colors

        label = QLabel(label_text)
        label.setFont(QFont(ds.typography.font_family_primary, 11, QFont.Weight.Medium))
        label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        parent_layout.addWidget(label)

        text_edit = QTextEdit()
        text_edit.setPlaceholderText(placeholder)
        text_edit.setStyleSheet(style)
        text_edit.setMaximumHeight(max_height)
        text_edit.setAcceptRichText(False)
        parent_layout.addWidget(text_edit)

        return text_edit

    def _load_prompts(self):
        """Load saved prompts from settings."""
        prompts = self.settings.get_platform_prompts(self.platform_id)
        self.title_prompt.setPlainText(prompts.get("title_prompt", ""))
        self.description_prompt.setPlainText(prompts.get("description_prompt", ""))
        self.hashtag_prompt.setPlainText(prompts.get("hashtag_prompt", ""))

    def _save_prompts(self):
        """Save prompts to settings."""
        from ui.components.custom_dialog import show_info
        self.settings.set_platform_prompts(
            self.platform_id,
            title_prompt=self.title_prompt.toPlainText().strip(),
            description_prompt=self.description_prompt.toPlainText().strip(),
            hashtag_prompt=self.hashtag_prompt.toPlainText().strip(),
        )
        show_info(self, "저장 완료", "프롬프트가 저장되었습니다.")


class YouTubeCommentSection(QFrame):
    """YouTube-specific comment auto-upload section."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ds = get_design_system()
        self.settings = get_settings_manager()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        ds = self.ds
        c = ds.colors

        self.setStyleSheet(f"""
            YouTubeCommentSection {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Checkbox
        self.comment_checkbox = QCheckBox("영상 업로드 후 자동 댓글 달기")
        self.comment_checkbox.setFont(QFont(ds.typography.font_family_primary, 12))
        self.comment_checkbox.setStyleSheet(f"""
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
        self.comment_checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.comment_checkbox)

        desc = QLabel("체크하면 영상 업로드 후 자동으로 댓글을 작성합니다. (셀프 댓글로 참여도를 높일 수 있습니다.)")
        desc.setWordWrap(True)
        desc.setFont(QFont(ds.typography.font_family_primary, 10))
        desc.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
        layout.addWidget(desc)

        # Comment prompt
        self.prompt_container = QWidget()
        prompt_layout = QVBoxLayout(self.prompt_container)
        prompt_layout.setContentsMargins(0, 4, 0, 0)
        prompt_layout.setSpacing(6)

        prompt_label = QLabel("댓글 프롬프트")
        prompt_label.setFont(QFont(ds.typography.font_family_primary, 11, QFont.Weight.Medium))
        prompt_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        prompt_layout.addWidget(prompt_label)

        self.comment_prompt = QTextEdit()
        self.comment_prompt.setPlaceholderText(
            "예: 이 영상에 나온 상품이 궁금하시면 프로필 링크를 확인해주세요! 질문은 댓글로 남겨주세요."
        )
        self.comment_prompt.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 8px 10px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-size: 12px;
            }}
            QTextEdit:focus {{
                border: 1px solid {c.primary};
            }}
        """)
        self.comment_prompt.setMaximumHeight(70)
        self.comment_prompt.setAcceptRichText(False)
        prompt_layout.addWidget(self.comment_prompt)

        # Save button
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_btn = QPushButton("댓글 설정 저장")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                padding: 8px 20px;
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {c.secondary};
            }}
        """)
        save_btn.clicked.connect(self._save_settings)
        btn_row.addWidget(save_btn)

        prompt_layout.addLayout(btn_row)
        layout.addWidget(self.prompt_container)

    def _load_settings(self):
        """Load saved comment settings."""
        enabled = self.settings.get_youtube_comment_enabled()
        self.comment_checkbox.setChecked(enabled)
        self.comment_prompt.setPlainText(self.settings.get_youtube_comment_prompt())
        self.prompt_container.setVisible(enabled)

    def _on_checkbox_changed(self, state: int):
        """Toggle comment prompt visibility."""
        enabled = self.comment_checkbox.isChecked()
        self.prompt_container.setVisible(enabled)
        self.settings.set_youtube_comment_enabled(enabled)

    def _save_settings(self):
        """Save comment settings."""
        from ui.components.custom_dialog import show_info
        self.settings.set_youtube_comment_enabled(self.comment_checkbox.isChecked())
        self.settings.set_youtube_comment_prompt(self.comment_prompt.toPlainText().strip())
        show_info(self, "저장 완료", "댓글 설정이 저장되었습니다.")


class YouTubeUploadSettingsSection(QFrame):
    """YouTube auto-upload interval settings."""

    def __init__(self, gui: "VideoAnalyzerGUI", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.settings = get_settings_manager()
        self._setup_ui()

    def _setup_ui(self):
        ds = self.ds
        c = ds.colors

        self.setStyleSheet(f"""
            YouTubeUploadSettingsSection {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Auto-upload toggle
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
        layout.addWidget(self.auto_upload_checkbox)

        # Interval widget (shown only when auto-upload enabled)
        self._interval_widget = QWidget()
        interval_layout = QVBoxLayout(self._interval_widget)
        interval_layout.setContentsMargins(0, 4, 0, 0)
        interval_layout.setSpacing(6)

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
        self.interval_slider.setValue(max(1, current_interval))
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

        # Tick labels
        ticks_layout = QHBoxLayout()
        for h in [1, 2, 3, 4]:
            tick = QLabel(f"{h}시간")
            tick.setFont(QFont(ds.typography.font_family_primary, 9))
            tick.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
            tick.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ticks_layout.addWidget(tick)
        interval_layout.addLayout(ticks_layout)

        layout.addWidget(self._interval_widget)

        # Rate limit info
        limit_label = QLabel("* 유튜브 정책: 24시간 내 최대 6개 영상 업로드 가능")
        limit_label.setFont(QFont(ds.typography.font_family_primary, 10))
        limit_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
        layout.addWidget(limit_label)

        # Initial state
        self._update_interval_label()
        self._interval_widget.setVisible(self.auto_upload_checkbox.isChecked())

    def _on_auto_upload_changed(self, state: int):
        enabled = self.auto_upload_checkbox.isChecked()
        self.settings.set_youtube_auto_upload(enabled)
        self._interval_widget.setVisible(enabled)
        if self.gui and hasattr(self.gui, 'state'):
            self.gui.state.youtube_auto_upload = enabled

    def _on_interval_changed(self, value: int):
        interval_minutes = value * 60
        self.settings.set_youtube_upload_interval(interval_minutes)
        self._update_interval_label()

    def _update_interval_label(self):
        hours = self.interval_slider.value()
        self.interval_value_label.setText(f"{hours}시간")


class PlatformComingSoonCard(QFrame):
    """Simple coming soon card for unreleased platforms."""

    def __init__(self, platform_id: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ds = get_design_system()
        config = PLATFORM_CONFIG.get(platform_id, {})
        self._setup_ui(config)

    def _setup_ui(self, config: dict):
        ds = self.ds
        c = ds.colors

        self.setStyleSheet(f"""
            PlatformComingSoonCard {{
                background-color: {c.surface_variant};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        # Icon
        icon_label = QLabel(config.get("icon", "?"))
        icon_label.setFont(QFont("Segoe UI Symbol", 16))
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background-color: {config.get('color', '#666')};
            color: white;
            border-radius: 6px;
            border: none;
        """)
        layout.addWidget(icon_label)

        # Name
        name_label = QLabel(config.get("name", ""))
        name_label.setFont(QFont(ds.typography.font_family_primary, 12, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        layout.addWidget(name_label)

        layout.addStretch()

        # Badge
        badge = QLabel("출시 예정")
        badge.setFont(QFont(ds.typography.font_family_primary, 10, QFont.Weight.Bold))
        badge.setStyleSheet(f"""
            background-color: {c.surface};
            color: {c.text_muted};
            border: 1px solid {c.border_light};
            border-radius: 4px;
            padding: 4px 8px;
        """)
        layout.addWidget(badge)


class UploadPanel(QFrame, ThemedMixin):
    """Social media upload settings panel.

    Provides channel connection, per-channel upload prompts, and
    YouTube-specific auto-upload/comment settings.
    """

    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.settings = get_settings_manager()
        self.__init_themed__(theme_manager)
        self._create_widgets()
        self._apply_theme()

    def _create_widgets(self):
        ds = self.ds
        c = ds.colors

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

        # ─── YouTube Section ────────────────────────────────────────
        yt_header = QLabel("유튜브")
        yt_header.setFont(QFont(ds.typography.font_family_primary, 15, QFont.Weight.Bold))
        yt_header.setStyleSheet(f"color: {c.text_primary}; border: none; background: transparent;")
        content_layout.addWidget(yt_header)

        # YouTube channel connection card
        yt_connected = self.settings.get_youtube_connected()
        yt_channel = self.settings.get_youtube_channel_info()
        self.youtube_card = SocialAuthCard(
            platform_id="youtube",
            is_connected=yt_connected,
            channel_info={"name": yt_channel.get("channel_name", "")},
            coming_soon=False,
            parent=content
        )
        self.youtube_card.connect_clicked.connect(self._connect_youtube)
        self.youtube_card.disconnect_clicked.connect(self._disconnect_youtube)
        content_layout.addWidget(self.youtube_card)

        # YouTube upload prompts (only visible when connected)
        self._yt_settings_container = QWidget()
        yt_settings_layout = QVBoxLayout(self._yt_settings_container)
        yt_settings_layout.setContentsMargins(0, 0, 0, 0)
        yt_settings_layout.setSpacing(12)

        # Upload interval settings
        self._yt_upload_settings = YouTubeUploadSettingsSection(self.gui, parent=content)
        yt_settings_layout.addWidget(self._yt_upload_settings)

        # Upload prompts
        self._yt_prompts = PromptInputGroup("youtube", parent=content)
        yt_settings_layout.addWidget(self._yt_prompts)

        # Comment settings
        self._yt_comment = YouTubeCommentSection(parent=content)
        yt_settings_layout.addWidget(self._yt_comment)

        content_layout.addWidget(self._yt_settings_container)
        self._yt_settings_container.setVisible(yt_connected)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {c.border_light};")
        content_layout.addWidget(sep)

        # ─── Other Platforms (Coming Soon) ──────────────────────────
        other_header = QLabel("기타 플랫폼")
        other_header.setFont(QFont(ds.typography.font_family_primary, 14, QFont.Weight.Bold))
        other_header.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        content_layout.addWidget(other_header)

        for platform_id in ["tiktok", "instagram", "threads", "x"]:
            card = PlatformComingSoonCard(platform_id, parent=content)
            content_layout.addWidget(card)

        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # ─── YouTube connection handlers ─────────────────────────────

    def _connect_youtube(self, platform_id: str):
        """Connect YouTube channel via OAuth."""
        from ui.components.custom_dialog import show_info, show_error

        try:
            if self.gui and hasattr(self.gui, 'youtube_manager') and self.gui.youtube_manager:
                yt_manager = self.gui.youtube_manager
                success = yt_manager.connect_channel()
                if success:
                    channel_info = yt_manager.get_channel_info()
                    channel_name = channel_info.get("title", "유튜브 채널")
                    channel_id = channel_info.get("id", "")

                    self.settings.set_youtube_connected(True, channel_id, channel_name)
                    self.youtube_card.set_connected(True, {"name": channel_name})
                    self._yt_settings_container.setVisible(True)

                    if hasattr(self.gui, 'state'):
                        self.gui.state.youtube_connected = True
                        self.gui.state.youtube_channel_info = channel_info

                    show_info(self, "연결 성공", f"유튜브 채널 '{channel_name}'이(가) 연결되었습니다.")
                    return

            # Fallback: manual connection dialog
            self._show_youtube_manual_connect()

        except Exception as e:
            logger.error(f"[UploadPanel] YouTube 연결 실패: {e}")
            show_error(self, "연결 실패", f"유튜브 채널 연결에 실패했습니다.\n\n{e}")

    def _show_youtube_manual_connect(self):
        """Fallback manual connection dialog when OAuth isn't configured."""
        from ui.components.custom_dialog import show_info
        from PyQt6.QtWidgets import QDialog, QLineEdit

        ds = self.ds
        c = ds.colors

        dialog = QDialog(self)
        dialog.setWindowTitle("유튜브 채널 연결")
        dialog.setFixedSize(460, 240)
        dialog.setStyleSheet(f"background-color: {c.background}; color: {c.text_primary};")

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        inst = QLabel(
            "유튜브 채널을 연결하려면 OAuth 인증이 필요합니다.\n\n"
            "1. 구글 클라우드 콘솔에서 OAuth 클라이언트 ID를 생성하세요.\n"
            "2. client_secrets.json 파일을 앱 폴더에 저장하세요.\n"
            "3. 또는 아래에 채널 이름을 입력하여 수동 연결할 수 있습니다."
        )
        inst.setWordWrap(True)
        inst.setFont(QFont(ds.typography.font_family_primary, 11))
        inst.setStyleSheet(f"color: {c.text_secondary};")
        layout.addWidget(inst)

        name_layout = QHBoxLayout()
        name_label = QLabel("채널 이름:")
        name_label.setFont(QFont(ds.typography.font_family_primary, 11))
        name_label.setStyleSheet(f"color: {c.text_secondary};")
        name_input = QLineEdit()
        name_input.setPlaceholderText("유튜브 채널 이름 입력")
        name_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 8px 12px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
            }}
        """)
        name_layout.addWidget(name_label)
        name_layout.addWidget(name_input, stretch=1)
        layout.addLayout(name_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        connect_btn = QPushButton("연결")
        connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF0000;
                color: white;
                padding: 8px 20px;
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #CC0000; }}
        """)

        cancel_btn = QPushButton("취소")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 8px 20px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
            }}
            QPushButton:hover {{ background-color: {c.surface}; }}
        """)
        cancel_btn.clicked.connect(dialog.reject)

        def do_connect():
            channel_name = name_input.text().strip() or "내 유튜브 채널"
            self.settings.set_youtube_connected(True, channel_id="manual", channel_name=channel_name)
            self.youtube_card.set_connected(True, {"name": channel_name})
            self._yt_settings_container.setVisible(True)
            if self.gui and hasattr(self.gui, 'state'):
                self.gui.state.youtube_connected = True
                self.gui.state.youtube_channel_info = {"name": channel_name}
            dialog.accept()
            show_info(self, "연결 성공", f"유튜브 채널 '{channel_name}'이(가) 연결되었습니다.")

        connect_btn.clicked.connect(do_connect)
        btn_layout.addWidget(connect_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _disconnect_youtube(self, platform_id: str):
        """Disconnect YouTube channel."""
        from ui.components.custom_dialog import show_question, show_info

        if not show_question(self, "연결 해제", "유튜브 채널 연결을 해제하시겠습니까?\n자동 업로드가 중지됩니다."):
            return

        self.settings.set_youtube_connected(False, "", "")
        self.settings.set_youtube_auto_upload(False)
        self.youtube_card.set_connected(False)
        self._yt_settings_container.setVisible(False)

        if self.gui and hasattr(self.gui, 'state'):
            self.gui.state.youtube_connected = False
            self.gui.state.youtube_channel_info = None
            self.gui.state.youtube_auto_upload = False

        if self.gui and hasattr(self.gui, 'youtube_manager') and self.gui.youtube_manager:
            try:
                self.gui.youtube_manager.disconnect_channel()
            except Exception:
                pass

        show_info(self, "연결 해제", "유튜브 채널 연결이 해제되었습니다.")

    def _apply_theme(self):
        c = self.ds.colors
        self.setStyleSheet(f"background-color: {c.background}; border: none;")

    def refresh(self):
        """Refresh panel state when navigated to."""
        yt_connected = self.settings.get_youtube_connected()
        if yt_connected:
            channel = self.settings.get_youtube_channel_info()
            self.youtube_card.set_connected(True, {"name": channel.get("channel_name", "")})
        else:
            self.youtube_card.set_connected(False)
        self._yt_settings_container.setVisible(yt_connected)
