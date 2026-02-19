# -*- coding: utf-8 -*-
"""
Social Media Upload Settings Panel (PyQt6)

Provides channel connection, per-channel upload prompts (title, description,
hashtags), and YouTube-specific comment auto-upload settings.
"""
from typing import Optional, Dict, Any, TYPE_CHECKING
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QSlider, QCheckBox, QTextEdit, QFileDialog,
    QStackedWidget
)
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system
from ui.components.base_widget import ThemedMixin
from ui.components.social_auth_card import SocialAuthCard, PLATFORM_CONFIG
from managers.settings_manager import get_settings_manager

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI

from utils.logging_config import get_logger
logger = get_logger(__name__)


class _YouTubeOAuthWorker(QObject):
    """Runs potentially slow YouTube OAuth work off the UI thread."""

    finished = pyqtSignal(bool, object, str)

    def __init__(self, youtube_manager: Any, source_path: str):
        super().__init__()
        self._youtube_manager = youtube_manager
        self._source_path = source_path

    def run(self):
        try:
            installed_json = self._youtube_manager.install_client_secrets(self._source_path)
            success = self._youtube_manager.connect_channel(client_secrets_file=installed_json)
            if not success:
                error_message = self._youtube_manager.get_last_error() or (
                    "선택한 JSON으로 인증에 실패했습니다.\n"
                    "OAuth 클라이언트 타입/리디렉션 설정을 확인해주세요."
                )
                self.finished.emit(False, {}, error_message)
                return

            channel_info = self._youtube_manager.get_channel_info() or {}
            self.finished.emit(True, channel_info, "")
        except Exception as e:
            logger.error(f"[UploadPanel] OAuth JSON 연결 워커 실패: {e}")
            self.finished.emit(False, {}, str(e))


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

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.default_btn = QPushButton("기본 프롬프트 불러오기")
        self.default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.default_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_secondary};
                padding: 8px 14px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {c.surface};
                color: {c.text_primary};
            }}
        """)
        self.default_btn.clicked.connect(self._apply_default_prompts)
        btn_row.addWidget(self.default_btn)

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
        defaults = self._get_default_prompts()
        self.title_prompt.setPlainText(prompts.get("title_prompt", "") or defaults.get("title_prompt", ""))
        self.description_prompt.setPlainText(prompts.get("description_prompt", "") or defaults.get("description_prompt", ""))
        self.hashtag_prompt.setPlainText(prompts.get("hashtag_prompt", "") or defaults.get("hashtag_prompt", ""))

    def _get_default_prompts(self) -> Dict[str, str]:
        """Get platform-specific default prompt templates."""
        defaults = dict(self.settings.DEFAULT_PLATFORM_PROMPTS.get(self.platform_id, {}))
        if defaults:
            return defaults

        platform_name = PLATFORM_CONFIG.get(self.platform_id, {}).get("name", self.platform_id.title())
        return {
            "title_prompt": (
                f"{platform_name}용 짧은 영상 제목 1개를 작성하세요. "
                "상품명과 핵심 장점을 반영하고 클릭을 유도하되 과장 표현은 피하세요."
            ),
            "description_prompt": (
                f"{platform_name} 게시글용 설명을 작성하세요. "
                "한 줄 요약, 핵심 포인트 2개, 행동 유도 문구(CTA) 1개를 포함하세요."
            ),
            "hashtag_prompt": (
                f"{platform_name}에 맞는 해시태그를 8~10개 생성하세요. "
                "상품 카테고리, 사용 상황, 타깃 키워드를 반영하고 중복은 제외하세요."
            ),
        }

    def _apply_default_prompts(self):
        """Fill editors with default templates (does not auto-save)."""
        from ui.components.custom_dialog import show_info

        defaults = self._get_default_prompts()
        self.title_prompt.setPlainText(defaults.get("title_prompt", ""))
        self.description_prompt.setPlainText(defaults.get("description_prompt", ""))
        self.hashtag_prompt.setPlainText(defaults.get("hashtag_prompt", ""))
        show_info(self, "기본 프롬프트 적용", "기본 프롬프트를 불러왔습니다. 필요하면 수정 후 저장하세요.")

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
                background-color: transparent;
                border: none;
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
                background-color: transparent;
                border: none;
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


class UploadWorkflowSection(QFrame):
    """Step-based section wrapper for clearer upload workflow."""

    def __init__(self, step: str, title: str, description: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._setup_ui(step, title, description)

    def _setup_ui(self, step: str, title: str, description: str):
        ds = self.ds
        c = ds.colors

        self.setStyleSheet(f"""
            UploadWorkflowSection {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
            UploadWorkflowSection QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        step_badge = QLabel(step)
        step_badge.setFont(QFont(ds.typography.font_family_primary, 10, QFont.Weight.Bold))
        step_badge.setStyleSheet(f"""
            background-color: {c.primary_light};
            color: {c.primary};
            border: 1px solid {c.primary};
            border-radius: 10px;
            padding: 2px 8px;
        """)
        header_row.addWidget(step_badge, 0, Qt.AlignmentFlag.AlignTop)

        title_desc_wrap = QWidget(self)
        title_desc_wrap.setStyleSheet("background-color: transparent; border: none;")
        title_desc_layout = QVBoxLayout(title_desc_wrap)
        title_desc_layout.setContentsMargins(0, 0, 0, 0)
        title_desc_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setFont(QFont(ds.typography.font_family_primary, 13, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {c.text_primary}; background-color: transparent; border: none;")
        title_desc_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont(ds.typography.font_family_primary, 10))
        desc_label.setStyleSheet(f"color: {c.text_muted}; background-color: transparent; border: none;")
        title_desc_layout.addWidget(desc_label)

        header_row.addWidget(title_desc_wrap, 1)
        layout.addLayout(header_row)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        layout.addLayout(self.content_layout)

    def add_widget(self, widget: QWidget):
        """Append a widget inside the section body."""
        self.content_layout.addWidget(widget)


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
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
            }}
            QScrollArea QWidget {{
                background-color: transparent;
                border: none;
            }}
        """)

        content = QWidget()
        content.setStyleSheet("background-color: transparent; border: none;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 10, 12, 10)
        content_layout.setSpacing(14)

        content_layout.addWidget(self._create_intro_card(content))

        main_body = QWidget(content)
        main_body.setStyleSheet("background-color: transparent; border: none;")
        body_layout = QHBoxLayout(main_body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

        self._channel_tabs: Dict[str, QPushButton] = {}
        self._channel_index: Dict[str, int] = {}
        self._active_channel: str = "youtube"
        self._platform_order = ["youtube", "tiktok", "instagram", "threads", "x"]
        body_layout.addWidget(self._create_channel_sidebar(main_body))

        self._channel_stack = QStackedWidget(main_body)
        self._channel_stack.setStyleSheet("background-color: transparent; border: none;")

        stack_card = QFrame(main_body)
        stack_card.setStyleSheet(f"""
            QFrame {{
                background-color: {c.surface_variant};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
            QFrame QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)
        stack_layout = QVBoxLayout(stack_card)
        stack_layout.setContentsMargins(12, 12, 12, 12)
        stack_layout.setSpacing(0)
        stack_layout.addWidget(self._channel_stack)

        # YouTube page
        yt_page = self._build_youtube_channel_page(parent=content)
        self._channel_index["youtube"] = self._channel_stack.count()
        self._channel_stack.addWidget(yt_page)

        # Other platform pages
        for platform_id in ["tiktok", "instagram", "threads", "x"]:
            page = self._build_generic_channel_page(platform_id=platform_id, parent=content)
            self._channel_index[platform_id] = self._channel_stack.count()
            self._channel_stack.addWidget(page)

        body_layout.addWidget(stack_card, 1)
        content_layout.addWidget(main_body, 1)

        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        self._refresh_channel_tab_labels()
        self._set_active_channel("youtube")

    def _create_intro_card(self, parent: Optional[QWidget] = None) -> QFrame:
        """Top summary card explaining workflow and channel switching."""
        ds = self.ds
        c = ds.colors

        card = QFrame(parent)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
            QFrame QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("소셜 미디어 업로드 설정")
        title.setFont(QFont(ds.typography.font_family_primary, 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {c.text_primary}; background-color: transparent; border: none;")
        layout.addWidget(title)

        subtitle = QLabel("왼쪽에서 채널을 고르고, 오른쪽에서 연결 → 자동 업로드 → 프롬프트 순서로 설정하세요.")
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont(ds.typography.font_family_primary, 11))
        subtitle.setStyleSheet(f"color: {c.text_muted}; background-color: transparent; border: none;")
        layout.addWidget(subtitle)

        flow_row = QHBoxLayout()
        flow_row.setContentsMargins(0, 2, 0, 0)
        flow_row.setSpacing(8)
        flow_steps = [
            ("1", "채널 연결"),
            ("2", "자동 업로드"),
            ("3", "프롬프트 저장"),
        ]
        for num, text in flow_steps:
            pill = QLabel(f"{num}. {text}")
            pill.setFont(QFont(ds.typography.font_family_primary, 10, QFont.Weight.Bold))
            pill.setStyleSheet(f"""
                background-color: {c.surface_variant};
                color: {c.text_secondary};
                border: 1px solid {c.border_light};
                border-radius: 12px;
                padding: 3px 10px;
            """)
            flow_row.addWidget(pill)
        flow_row.addStretch()
        layout.addLayout(flow_row)

        return card

    def _create_channel_sidebar(self, parent: Optional[QWidget] = None) -> QFrame:
        """Create channel selection sidebar for clearer separation."""
        ds = self.ds
        c = ds.colors

        sidebar = QFrame(parent)
        sidebar.setFixedWidth(228)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
            QFrame QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("채널 목록")
        title.setFont(QFont(ds.typography.font_family_primary, 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {c.text_primary};")
        layout.addWidget(title)

        helper = QLabel("채널을 클릭하면 해당 설정으로 즉시 전환됩니다.")
        helper.setWordWrap(True)
        helper.setFont(QFont(ds.typography.font_family_primary, 10))
        helper.setStyleSheet(f"color: {c.text_muted};")
        layout.addWidget(helper)

        self._channel_summary_label = QLabel()
        self._channel_summary_label.setWordWrap(True)
        self._channel_summary_label.setFont(QFont(ds.typography.font_family_primary, 10, QFont.Weight.Medium))
        self._channel_summary_label.setStyleSheet(f"""
            background-color: {c.surface_variant};
            color: {c.text_secondary};
            border: 1px solid {c.border_light};
            border-radius: {ds.radius.sm}px;
            padding: 8px;
        """)
        layout.addWidget(self._channel_summary_label)

        for platform_id in self._platform_order:
            tab_btn = QPushButton()
            tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tab_btn.setCheckable(True)
            tab_btn.setMinimumHeight(62)
            tab_btn.clicked.connect(lambda checked, pid=platform_id: self._set_active_channel(pid))
            self._channel_tabs[platform_id] = tab_btn
            layout.addWidget(tab_btn)

        layout.addStretch()
        return sidebar

    def _create_channel_banner(self, platform_id: str, title: str, description: str, parent: Optional[QWidget] = None) -> QFrame:
        """Create per-channel summary banner."""
        ds = self.ds
        c = ds.colors
        platform_cfg = PLATFORM_CONFIG.get(platform_id, {})
        platform_color = platform_cfg.get("color", c.primary)

        banner = QFrame(parent)
        banner.setStyleSheet(f"""
            QFrame {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
            QFrame QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)
        layout = QVBoxLayout(banner)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        icon = QLabel(platform_cfg.get("icon", "•"))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(26, 26)
        icon.setFont(QFont("Segoe UI Symbol", 13))
        icon.setStyleSheet(f"""
            background-color: {platform_color};
            color: white;
            border-radius: 6px;
            border: none;
        """)
        header.addWidget(icon)

        title_label = QLabel(title)
        title_label.setFont(QFont(ds.typography.font_family_primary, 13, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {c.text_primary};")
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont(ds.typography.font_family_primary, 10))
        desc_label.setStyleSheet(f"color: {c.text_muted};")
        layout.addWidget(desc_label)

        return banner

    def _build_youtube_channel_page(self, parent: Optional[QWidget] = None) -> QWidget:
        """Build the YouTube settings page."""
        yt_connected = self.settings.get_youtube_connected()
        yt_channel = self.settings.get_youtube_channel_info()
        c = self.ds.colors

        page = QWidget(parent)
        page.setStyleSheet("background-color: transparent; border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(
            self._create_channel_banner(
                "youtube",
                "유튜브 채널 설정",
                "채널 연결 후 자동 업로드와 프롬프트를 설정하면 상품별 게시글이 자동 생성됩니다.",
                parent=page,
            )
        )

        self._yt_connection_state = QLabel()
        self._yt_connection_state.setWordWrap(True)
        self._yt_connection_state.setFont(QFont(self.ds.typography.font_family_primary, 10, QFont.Weight.Medium))
        self._yt_connection_state.setStyleSheet(
            f"color: {c.text_secondary}; background-color: transparent; border: none; padding: 2px 0;"
        )
        layout.addWidget(self._yt_connection_state)

        self.youtube_card = SocialAuthCard(
            platform_id="youtube",
            is_connected=yt_connected,
            channel_info={"name": yt_channel.get("channel_name", "")},
            coming_soon=False,
            parent=page,
        )
        self.youtube_card.connect_clicked.connect(self._connect_youtube)
        self.youtube_card.disconnect_clicked.connect(self._disconnect_youtube)
        connect_section = UploadWorkflowSection(
            "1단계",
            "채널 연결",
            "채널명을 입력할 필요 없이 OAuth JSON 파일만 업로드하면 자동으로 연결됩니다.",
            parent=page,
        )
        connect_section.add_widget(self.youtube_card)
        layout.addWidget(connect_section)

        self._yt_upload_settings = YouTubeUploadSettingsSection(self.gui, parent=page)
        upload_section = UploadWorkflowSection(
            "2단계",
            "자동 업로드 설정",
            "업로드 간격과 자동 업로드 활성화 여부를 설정하세요.",
            parent=page,
        )
        upload_section.add_widget(self._yt_upload_settings)
        layout.addWidget(upload_section)

        self._yt_prompts = PromptInputGroup("youtube", parent=page)
        prompt_section = UploadWorkflowSection(
            "3단계",
            "업로드 프롬프트 설정",
            "제목, 게시글, 해시태그 기본 프롬프트를 작성하고 저장하세요.",
            parent=page,
        )
        prompt_section.add_widget(self._yt_prompts)
        layout.addWidget(prompt_section)

        self._yt_comment = YouTubeCommentSection(parent=page)
        comment_section = UploadWorkflowSection(
            "4단계(선택)",
            "자동 댓글 설정",
            "영상 업로드 후 자동으로 달릴 댓글 문구를 설정하세요.",
            parent=page,
        )
        comment_section.add_widget(self._yt_comment)
        layout.addWidget(comment_section)

        layout.addStretch()
        self._set_youtube_feature_enabled(yt_connected)
        return page

    def _build_generic_channel_page(self, platform_id: str, parent: Optional[QWidget] = None) -> QWidget:
        """Build settings page for non-YouTube channels."""
        config = PLATFORM_CONFIG.get(platform_id, {})

        page = QWidget(parent)
        page.setStyleSheet("background-color: transparent; border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(
            self._create_channel_banner(
                platform_id,
                f"{config.get('name', platform_id.title())} 업로드 설정",
                "채널 연결 기능은 준비 중입니다. 프롬프트는 미리 작성/저장할 수 있습니다.",
                parent=page,
            )
        )

        coming_soon_section = UploadWorkflowSection(
            "1단계",
            "채널 연결",
            "해당 채널 연결 기능은 현재 준비 중입니다.",
            parent=page,
        )
        coming_soon_section.add_widget(PlatformComingSoonCard(platform_id, parent=page))
        layout.addWidget(coming_soon_section)

        prompt_section = UploadWorkflowSection(
            "2단계",
            "업로드 프롬프트 설정",
            "미리 프롬프트를 저장해두면 기능 오픈 후 바로 사용할 수 있습니다.",
            parent=page,
        )
        prompt_section.add_widget(PromptInputGroup(platform_id, parent=page))
        layout.addWidget(prompt_section)

        layout.addStretch()
        return page

    def _set_active_channel(self, platform_id: str):
        """Switch visible channel settings page."""
        if platform_id not in self._channel_index:
            return

        self._active_channel = platform_id
        self._channel_stack.setCurrentIndex(self._channel_index[platform_id])

        for pid, btn in self._channel_tabs.items():
            is_active = pid == platform_id
            btn.setChecked(is_active)
            self._apply_channel_tab_style(btn, platform_id=pid, active=is_active)

    def _get_channel_status_text(self, platform_id: str) -> str:
        """Get short status text for channel tab."""
        if platform_id == "youtube":
            return "연결됨" if self.settings.get_youtube_connected() else "연결 필요"
        if self.settings.get_social_connection_status(platform_id):
            return "연결됨"
        return "준비중"

    def _refresh_channel_tab_labels(self):
        """Refresh tab text and status hints."""
        connected_count = 0
        for platform_id, button in self._channel_tabs.items():
            cfg = PLATFORM_CONFIG.get(platform_id, {})
            name = cfg.get("name", platform_id.title())
            status = self._get_channel_status_text(platform_id)
            if status == "연결됨":
                connected_count += 1
            button.setText(f"{name}\n상태: {status}")
            button.setToolTip(f"{name} - {status}")

        if hasattr(self, "_channel_summary_label"):
            active_name = PLATFORM_CONFIG.get(self._active_channel, {}).get("name", self._active_channel)
            self._channel_summary_label.setText(
                f"연결된 채널: {connected_count}/{len(self._platform_order)}\n"
                f"현재 선택: {active_name}"
            )

    def _update_youtube_state_hint(self, connected: bool):
        """Update YouTube state helper text."""
        if not hasattr(self, "_yt_connection_state"):
            return

        c = self.ds.colors
        if connected:
            self._yt_connection_state.setText("현재 상태: 채널 연결 완료. 자동 업로드 기능을 사용할 수 있습니다.")
            self._yt_connection_state.setStyleSheet(
                f"color: {c.success}; background-color: transparent; border: none; padding: 2px 0;"
            )
            return

        self._yt_connection_state.setText("현재 상태: 채널 미연결. 먼저 1단계 채널 연결을 완료하세요.")
        self._yt_connection_state.setStyleSheet(
            f"color: {c.warning}; background-color: transparent; border: none; padding: 2px 0;"
        )

    def _apply_channel_tab_style(self, button: QPushButton, platform_id: str, active: bool):
        """Apply visual style for channel tab buttons."""
        ds = self.ds
        c = ds.colors
        platform_color = PLATFORM_CONFIG.get(platform_id, {}).get("color", c.primary)

        if active:
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c.surface};
                    color: {c.text_primary};
                    border: 1px solid {platform_color};
                    border-radius: {ds.radius.sm}px;
                    padding: 9px 10px;
                    font-size: 12px;
                    font-weight: 700;
                    text-align: left;
                    line-height: 1.3em;
                }}
            """)
        else:
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c.surface_variant};
                    color: {c.text_secondary};
                    border: 1px solid {c.border_light};
                    border-radius: {ds.radius.sm}px;
                    padding: 9px 10px;
                    font-size: 12px;
                    font-weight: 500;
                    text-align: left;
                    line-height: 1.3em;
                }}
                QPushButton:hover {{
                    background-color: {c.surface};
                    color: {c.text_primary};
                }}
            """)

    # ─── YouTube connection handlers ─────────────────────────────

    def _connect_youtube(self, platform_id: str):
        """Connect YouTube channel via OAuth."""
        from ui.components.custom_dialog import show_error

        try:
            self._show_youtube_json_connect()
        except Exception as e:
            logger.error(f"[UploadPanel] YouTube 연결 실패: {e}")
            show_error(self, "연결 실패", f"유튜브 채널 연결에 실패했습니다.\n\n{e}")

    def _show_youtube_json_connect(self):
        """Upload OAuth client JSON and connect YouTube channel."""
        from ui.components.custom_dialog import show_info, show_error
        from PyQt6.QtWidgets import QDialog

        ds = self.ds
        c = ds.colors
        selected_file = {"path": ""}
        connection_state = {"running": False, "thread": None, "worker": None}

        dialog = QDialog(self)
        dialog.setWindowTitle("유튜브 채널 연결")
        dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        dialog.setFixedSize(520, 330)
        dialog.setStyleSheet(f"background-color: {c.background}; color: {c.text_primary};")

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        inst = QLabel(
            "채널명을 직접 입력할 필요 없이 OAuth JSON 파일만 업로드하면 됩니다.\n\n"
            "1. 구글 클라우드 콘솔에서 OAuth 클라이언트 ID를 생성하세요.\n"
            "2. 다운로드한 client_secrets.json 파일을 선택하세요.\n"
            "3. 파일은 앱 설치 폴더 내부 보안 경로에 복사되어 보관됩니다."
        )
        inst.setWordWrap(True)
        inst.setFont(QFont(ds.typography.font_family_primary, 11))
        inst.setStyleSheet(f"color: {c.text_secondary};")
        layout.addWidget(inst)

        file_info = QLabel("선택된 파일: 없음")
        file_info.setWordWrap(True)
        file_info.setFont(QFont(ds.typography.font_family_primary, 10))
        file_info.setStyleSheet(f"color: {c.text_muted};")
        layout.addWidget(file_info)

        select_btn = QPushButton("OAuth JSON 파일 선택")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 8px 14px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.surface};
            }}
        """)
        layout.addWidget(select_btn)

        status_label = QLabel("")
        status_label.setWordWrap(True)
        status_label.setFont(QFont(ds.typography.font_family_primary, 10))
        status_label.setStyleSheet(f"color: {c.text_muted};")
        layout.addWidget(status_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        connect_btn = QPushButton("연결")
        connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        connect_btn.setEnabled(False)
        connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF0000;
                color: white;
                padding: 8px 20px;
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #CC0000; }}
            QPushButton:disabled {{
                background-color: {c.surface_variant};
                color: {c.text_muted};
            }}
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
        def set_connecting(running: bool, status_message: str = ""):
            connection_state["running"] = running
            select_btn.setEnabled(not running)
            cancel_btn.setEnabled(not running)
            connect_btn.setText("연결 중..." if running else "연결")
            connect_btn.setEnabled((not running) and bool(selected_file["path"]))
            status_label.setText(status_message if status_message else "")

        def on_cancel():
            if connection_state["running"]:
                status_label.setText("연결 처리 중입니다. 완료 후 다시 시도해주세요.")
                return
            dialog.reject()

        cancel_btn.clicked.connect(on_cancel)

        def choose_file():
            if connection_state["running"]:
                return
            file_path, _ = QFileDialog.getOpenFileName(
                dialog,
                "OAuth JSON 파일 선택",
                "",
                "JSON 파일 (*.json)"
            )
            if not file_path:
                return
            selected_file["path"] = file_path
            file_info.setText(f"선택된 파일: {file_path}")
            connect_btn.setEnabled(True)

        def on_connect_finished(success: bool, channel_info_obj: object, error_message: str):
            set_connecting(False)
            connection_state["thread"] = None
            connection_state["worker"] = None

            if success:
                channel_info = channel_info_obj if isinstance(channel_info_obj, dict) else {}
                channel_name = self._apply_youtube_connected_state(channel_info)
                dialog.accept()
                show_info(self, "연결 성공", f"유튜브 채널 '{channel_name}'이(가) 연결되었습니다.")
                return

            detail = error_message or (
                "선택한 JSON으로 인증에 실패했습니다.\n"
                "OAuth 클라이언트 타입/리디렉션 설정을 확인해주세요."
            )
            show_error(self, "연결 실패", detail)

        def do_connect():
            if connection_state["running"]:
                return
            if not selected_file["path"]:
                return

            if not (self.gui and hasattr(self.gui, 'youtube_manager') and self.gui.youtube_manager):
                show_error(self, "연결 실패", "YouTube 매니저를 초기화하지 못했습니다.")
                return

            set_connecting(True, "OAuth 인증을 진행 중입니다. 브라우저 승인 후 잠시만 기다려주세요.")
            yt_manager = self.gui.youtube_manager

            worker = _YouTubeOAuthWorker(yt_manager, selected_file["path"])
            thread = QThread(dialog)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(on_connect_finished)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)

            connection_state["thread"] = thread
            connection_state["worker"] = worker
            thread.start()

        select_btn.clicked.connect(choose_file)
        connect_btn.clicked.connect(do_connect)
        btn_layout.addWidget(connect_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _set_youtube_feature_enabled(self, connected: bool):
        """Enable features that require an actual connected channel."""
        self._yt_upload_settings.setEnabled(connected)
        self._yt_comment.setEnabled(connected)
        self._update_youtube_state_hint(connected)
        self._refresh_channel_tab_labels()

    def _apply_youtube_connected_state(self, channel_info: Optional[Dict[str, str]]) -> str:
        """Persist and apply connected YouTube channel state."""
        channel_info = channel_info or {}
        channel_name = (
            channel_info.get("title")
            or channel_info.get("channel_name")
            or channel_info.get("name")
            or "유튜브 채널"
        )
        channel_id = channel_info.get("id") or channel_info.get("channel_id", "")

        self.settings.set_youtube_connected(True, channel_id, channel_name)
        self.youtube_card.set_connected(True, {"name": channel_name})
        self._set_youtube_feature_enabled(True)
        self._refresh_channel_tab_labels()

        if self.gui and hasattr(self.gui, 'state'):
            self.gui.state.youtube_connected = True
            self.gui.state.youtube_channel_info = channel_info

        return channel_name

    def _disconnect_youtube(self, platform_id: str):
        """Disconnect YouTube channel."""
        from ui.components.custom_dialog import show_question, show_info

        if not show_question(self, "연결 해제", "유튜브 채널 연결을 해제하시겠습니까?\n자동 업로드가 중지됩니다."):
            return

        self.settings.set_youtube_connected(False, "", "")
        self.settings.set_youtube_auto_upload(False)
        self.youtube_card.set_connected(False)
        self._set_youtube_feature_enabled(False)
        self._refresh_channel_tab_labels()

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
        self.setStyleSheet(f"""
            UploadPanel {{
                background-color: {c.background};
                border: none;
            }}
            UploadPanel QLabel {{
                background-color: transparent;
                border: none;
            }}
            UploadPanel QCheckBox {{
                background-color: transparent;
            }}
        """)

    def refresh(self):
        """Refresh panel state when navigated to."""
        yt_connected = self.settings.get_youtube_connected()
        if yt_connected:
            channel = self.settings.get_youtube_channel_info()
            self.youtube_card.set_connected(True, {"name": channel.get("channel_name", "")})
        else:
            self.youtube_card.set_connected(False)
        self._refresh_channel_tab_labels()
        self._set_youtube_feature_enabled(yt_connected)
        self._set_active_channel(getattr(self, "_active_channel", "youtube"))
