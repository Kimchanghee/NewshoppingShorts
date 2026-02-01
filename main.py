# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - PyQt6 main application entry.
Re-designed with Enhanced Design System (Industrial-Creative Hybrid)
"""
import sys
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QFrame,
    QStackedWidget,
    QSizePolicy,
)

import config
# Ensure ffmpeg is discoverable for pydub
FFMPEG_FALLBACK = r"C:\Program Files (x86)\UltData\Resources\ffmpegs"
if os.path.isdir(FFMPEG_FALLBACK) and FFMPEG_FALLBACK not in os.environ.get("PATH", ""):
    os.environ["PATH"] = FFMPEG_FALLBACK + os.pathsep + os.environ.get("PATH", "")

from app.state import AppState
from app.api_handler import APIHandler
from managers.queue_manager import QueueManager
from managers.voice_manager import VoiceManager
from managers.output_manager import OutputManager
from ui.panels import HeaderPanel, URLInputPanel, VoicePanel, QueuePanel, ProgressPanel, SubscriptionPanel
from ui.panels.style_tab import StyleTab
from ui.components.status_bar import StatusBar
from ui.components.custom_dialog import show_info, show_warning
from ui.theme_manager import get_theme_manager
from ui.design_system_enhanced import get_design_system
from utils.logging_config import get_logger
from utils.error_handlers import global_exception_handler
from core.providers import VertexGeminiProvider
from ui.components.step_nav import StepNav
from caller import rest

logger = get_logger(__name__)

URL_PATTERN = re.compile(r"https?://[^\\s\"'<>]+")


class VideoAnalyzerGUI(QMainWindow):
    # Signals for cross-thread logging/progress
    update_status_signal = None
    log_signal = None

    def __init__(self, parent=None, login_data=None, preloaded_ocr=None):
        super().__init__(parent)
        self.login_data = login_data
        self.preloaded_ocr = preloaded_ocr
        self.state = AppState(root=self, login_data=login_data)
        self.theme_manager = get_theme_manager()
        self.design = get_design_system()  # Load enhanced design system

        self.url_queue: List[str] = []
        self.url_status: Dict[str, str] = {}
        self.url_status_message: Dict[str, str] = {}
        self.url_remarks: Dict[str, str] = {}
        self.url_timestamps: Dict[str, Any] = {}

        self.output_folder_path = self.state.output_folder_path
        self.output_folder_label = None

        self.voice_profiles = self.state.voice_profiles
        self.voice_vars = self.state.voice_vars
        self.voice_sample_paths = self.state.voice_sample_paths
        self.multi_voice_presets = self.state.multi_voice_presets
        self.available_tts_voices = self.state.available_tts_voices
        self.max_voice_selection = self.state.max_voice_selection

        self.api_key_manager = None

        self.queue_manager = QueueManager(self)
        self.voice_manager = VoiceManager(self)
        self.output_manager = OutputManager(self)
        self.api_handler = APIHandler(self)
        self.model_provider = VertexGeminiProvider()
        self._warn_if_vertex_unset()

        self.init_ui()
        self.api_handler.load_saved_api_keys()
        self.refresh_user_status()

    # ---------------- UI -----------------
    def init_ui(self):
        d = self.design
        self.setWindowTitle("쇼핑 숏폼 메이커 - 스튜디오")
        icon_path = os.path.join(os.path.dirname(__file__), "resource", "mainTrayIcon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1440, 960)

        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setStyleSheet(f"#CentralWidget {{ background-color: {d.colors.bg_main}; }}")
        self.setCentralWidget(central)

        # Main Horizontal Layout (Sidebar + Content)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left Container (Sidebar + Log Panel) - Vertical Split
        left_container = QWidget()
        left_container.setObjectName("LeftContainer")
        left_container.setStyleSheet(f"#LeftContainer {{ background-color: {d.colors.bg_main}; }}")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # 1. Sidebar (StepNav) - Removed progress and subscription
        steps = [
            ("source", "소스 입력", "🧲"),
            ("style", "스타일", "🎨"),
            ("voice", "음성/TTS", "🎤"),
            ("queue", "대기/진행", "📋"),
        ]
        self.step_nav = StepNav(steps)
        left_layout.addWidget(self.step_nav, stretch=1)
        
        # 2. Log Panel (ProgressPanel) - Bottom left, fixed height
        self.progress_panel = ProgressPanel(self, self, theme_manager=self.theme_manager)
        self.progress_panel.setMinimumHeight(200)
        self.progress_panel.setMaximumHeight(280)
        self.progress_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        left_layout.addWidget(self.progress_panel)
        
        main_layout.addWidget(left_container)

        # 3. Main Content Area (Right Side)
        right_container = QWidget()
        right_container.setObjectName("RightContainer")
        right_container.setStyleSheet(f"#RightContainer {{ background-color: {d.colors.bg_main}; }}")
        
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 3-1. Top Bar
        right_layout.addWidget(self._build_topbar())

        # 3-2. Main content area (stacked pages)
        content_container = QWidget()
        content_container.setObjectName("ContentContainer")
        content_container.setStyleSheet(f"#ContentContainer {{ background-color: {d.colors.bg_main}; }}")
        
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Stacked Pages
        self.stack = QStackedWidget()
        
        # Add padding around the stack for better visual balance
        stack_wrapper = QWidget()
        stack_layout = QVBoxLayout(stack_wrapper)
        stack_layout.setContentsMargins(40, 30, 40, 30)  # Generous padding
        stack_layout.addWidget(self.stack)
        
        content_layout.addWidget(stack_wrapper)
        right_layout.addWidget(content_container)
        main_layout.addWidget(right_container, stretch=1)

        # Build pages as cards (progress and subscription removed from stack, shown separately)
        self.url_input_panel = URLInputPanel(self.stack, self, theme_manager=self.theme_manager)
        self.style_tab = StyleTab(self.stack, self, theme_manager=self.theme_manager)
        self.voice_panel = VoicePanel(self.stack, self, theme_manager=self.theme_manager)
        self.queue_panel = QueuePanel(self.stack, self, theme_manager=self.theme_manager)
        self.subscription_panel = SubscriptionPanel(self.stack, self)

        pages = [
            ("source", "소스 입력", "숏폼으로 변환할 쇼핑몰 링크나 영상을 추가하세요.", self.url_input_panel),
            ("style", "스타일", "자막, 배경음악, 폰트 등 영상 스타일을 설정합니다.", self.style_tab),
            ("voice", "음성/TTS", "AI 성우 목소리와 나레이션 스타일을 선택하세요.", self.voice_panel),
            ("queue", "대기/진행", "작업 대기열 및 진행 상황을 관리합니다.", self.queue_panel),
        ]

        self.page_index = {}
        for idx, (sid, title, subtitle, widget) in enumerate(pages):
            card = self._wrap_card(widget, title, subtitle)
            self.stack.addWidget(card)
            self.page_index[sid] = idx

        self.step_nav.step_selected.connect(self._on_step_selected)
        self._on_step_selected("source")

        # Status bar is separate at main window level or can be added to bottom of content
        # Adding to right layout to keep sidebar full height
        self.status_bar = StatusBar(self, self)
        right_layout.addWidget(self.status_bar)

    # ------------- URL helpers -------------
    def add_url_from_entry(self):
        show_warning(self, "안내", "URL 추가 로직은 미구현 상태입니다.")

    def paste_and_extract(self):
        show_info(self, "안내", "클립보드 붙여넣기 로직은 미구현 상태입니다.")

    def remove_selected_url(self):
        self.queue_manager.remove_selected_url()

    def clear_url_queue(self):
        self.queue_manager.clear_url_queue()

    def clear_waiting_only(self):
        self.queue_manager.clear_waiting_only()

    # ------------- Batch stubs -------------
    def start_batch_processing(self):
        if not self.url_queue:
            show_warning(self, "안내", "대기열이 비어 있습니다.")
            return
        url = self.url_queue[0]
        self.url_status[url] = "processing"
        self.queue_manager.update_url_listbox()
        self.queue_manager.update_queue_count()
        try:
            preview = self.model_provider.generate_text("Health check: respond with 'OK'.")
            logger.info(f"Model response: {preview[:80]}")
        except Exception as e:
            logger.warning(f"Model call failed: {e}")
        show_info(self, "시작", "배치 처리를 시작합니다. (데모 모드)")

    def stop_batch_processing(self):
        show_info(self, "중지", "배치 처리를 중지했습니다. (데모 모드)")

    # ------------- Output / API -------------
    def select_output_folder(self):
        self.output_manager.select_output_folder()

    def show_api_key_manager(self):
        self.api_handler.show_api_key_manager()

    def show_api_status(self):
        self.api_handler.show_api_status()

    # ------------- Voice -------------
    def play_voice_sample(self, voice_id: str):
        self.voice_manager.play_voice_sample(voice_id)

    def _toggle_voice(self, voice_id: str):
        self.voice_manager.on_voice_card_clicked(voice_id)

    # ------------- Shell helpers -------------
    def _warn_if_vertex_unset(self):
        if not config.VERTEX_PROJECT_ID or not config.VERTEX_MODEL_ID:
            logger.warning("[Vertex] 프로젝트/모델 ID가 설정되지 않았습니다. GEMINI로 폴백됩니다.")
        if not (config.VERTEX_JSON_KEY_PATH or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")):
            logger.info("[Vertex] 서비스 계정 키 경로가 비어 있습니다. ADC 또는 기본 자격 증명 사용을 시도합니다.")

    def _build_topbar(self) -> QWidget:
        d = self.design
        c = d.colors
        
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setStyleSheet(f"""
            #TopBar {{
                background-color: {c.bg_header};
                border-bottom: 1px solid {c.border_light};
            }}
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)

        # Breadcrumbs / Title
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        
        app_title = QLabel("쇼핑 숏폼 메이커")
        app_title.setFont(QFont(d.typography.font_family_heading, 14, QFont.Weight.Bold))
        app_title.setStyleSheet(f"color: {c.text_primary};")
        
        project_sub = QLabel("프로젝트: 새 영상")
        project_sub.setFont(QFont(d.typography.font_family_body, 12))
        project_sub.setStyleSheet(f"color: {c.text_secondary};")
        
        title_box.addWidget(app_title)
        title_box.addWidget(project_sub)
        layout.addLayout(title_box)

        layout.addStretch()

        # Right side actions
        
        # User Credits Label
        self.credits_label = QLabel("")
        self.credits_label.setFont(QFont(d.typography.font_family_body, 11))
        self.credits_label.setStyleSheet(f"color: {c.text_secondary}; margin-right: 10px;")
        layout.addWidget(self.credits_label)

        # Subscription Badge (Clickable)
        self.sub_badge = QPushButton("게스트")
        self.sub_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sub_badge.setToolTip("구독/결제 페이지로 이동")
        self.sub_badge.setFont(QFont(d.typography.font_family_body, 10, QFont.Weight.Bold))
        self.sub_badge.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.bg_card};
                color: {c.text_secondary};
                padding: 6px 12px;
                border-radius: 6px;
                border: 1px solid {c.border_light};
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
                color: {c.text_primary};
            }}
        """)
        self.sub_badge.clicked.connect(self._show_subscription_panel)
        layout.addWidget(self.sub_badge)

        # Refresh User Status Button
        refresh_btn = QPushButton("↻")
        refresh_btn.setToolTip("상태 새로고침")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c.text_secondary};
                border: 1px solid {c.border_light};
                border-radius: 15px;
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
                color: {c.text_primary};
            }}
        """)
        refresh_btn.clicked.connect(self.refresh_user_status)
        layout.addWidget(refresh_btn)

        # Settings Button
        settings_btn = QPushButton("설정")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setFont(QFont(d.typography.font_family_body, 11))
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c.text_secondary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
                color: {c.text_primary};
            }}
        """)
        settings_btn.clicked.connect(self.show_api_status)
        layout.addWidget(settings_btn)

        return bar

    def refresh_user_status(self):
        """Update user subscription status and credits from server"""
        if not self.login_data:
            self.sub_badge.setText("게스트")
            return

        try:
            # Extract user ID safely
            # Structure: {'data': {'data': {'id': ...}}}
            data_part = self.login_data.get("data", {})
            if isinstance(data_part, dict):
                inner_data = data_part.get("data", {})
                user_id = inner_data.get("id")
            else:
                user_id = None
            
            if not user_id:
                # Fallback if structure is different
                user_id = self.login_data.get("userId")

            if user_id:
                # Call API
                info = rest.check_work_available(user_id)
                
                # Update Credits
                remaining = info.get("remaining", 0)
                total = info.get("total", 0)
                used = info.get("used", 0)
                
                # 'available' means user can still work
                is_available = info.get("available", False)
                
                self.credits_label.setText(f"크레딧: {remaining}/{total}")
                
                # Update Badge based on logic
                # You might want to get actual user_type if available from another API, 
                # but currently we can infer from credits or initial login data
                top_data = self.login_data.get("data", {}).get("data", {})
                user_type = top_data.get("user_type", "trial")
                
                d = self.design
                c = d.colors

                badge_text = user_type.upper()
                badge_bg = c.bg_card
                badge_color = c.text_secondary
                
                if user_type == "subscriber":
                    badge_text = "프로 플랜"
                    badge_bg = c.primary_light
                    badge_color = c.primary
                elif user_type == "admin":
                    badge_text = "관리자"
                    badge_bg = "#374151"  # Dark gray
                    badge_color = "#FFFFFF"
                else: # trial
                    badge_text = "체험판"
                    if remaining <= 0:
                        badge_bg = "#FEF2F2" # Red tint
                        badge_color = "#EF4444" # Red
                
                self.sub_badge.setText(badge_text)
                self.sub_badge.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {badge_bg};
                        color: {badge_color};
                        padding: 6px 12px;
                        border-radius: 6px;
                        font-weight: bold;
                        border: 1px solid {c.border_light};
                    }}
                    QPushButton:hover {{
                        background-color: {c.bg_hover};
                        opacity: 0.9;
                    }}
                """)
                
                logger.info(f"User status refreshed: {user_id} | {user_type} | {remaining}/{total}")
            else:
                logger.warning("Could not extract user_id from login_data for status refresh")
        except Exception as e:
            logger.error(f"Failed to refresh user status: {e}")

    def _wrap_card(self, widget: QWidget, title: str, subtitle: str) -> QWidget:
        d = self.design
        
        # We wrap the content in a container that provides the "Card" look
        card = QFrame()
        card.setObjectName("ContentCard")
        card.setStyleSheet(f"""
            #ContentCard {{
                background-color: {d.colors.bg_card};
                border: 1px solid {d.colors.border_card};
                border-radius: 16px;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(24)

        # Header Area
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)
        
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(d.typography.font_family_heading, 24, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {d.colors.text_primary};")
        
        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(QFont(d.typography.font_family_body, 13))
        sub_lbl.setStyleSheet(f"color: {d.colors.text_secondary};")
        
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(sub_lbl)
        
        card_layout.addLayout(header_layout)
        
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {d.colors.border_light};")
        card_layout.addWidget(line)
        
        # Content
        card_layout.addWidget(widget)
        
        return card

    def _on_step_selected(self, step_id: str):
        idx = self.page_index.get(step_id, 0)
        self.stack.setCurrentIndex(idx)
        self.step_nav.set_active(step_id)

    def _show_subscription_panel(self):
        """Show the subscription/payment panel"""
        self._on_step_selected("subscription")

    # Removed _apply_shell_styles as we now apply consistent styles via DesignSystem inline or in components


def main():
    sys.excepthook = global_exception_handler
    app = QApplication(sys.argv)
    
    # Load fonts if possible, or rely on system
    # here we assume fonts are installed or fallback to system sans-serif
    
    gui = VideoAnalyzerGUI()
    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
