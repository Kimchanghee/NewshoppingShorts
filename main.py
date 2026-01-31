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

    # ---------------- UI -----------------
    def init_ui(self):
        d = self.design
        self.setWindowTitle("쇼핑 쇼츠 메이커 - Studio")
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

        # 1. Sidebar (StepNav)
        steps = [
            ("source", "소스 입력", "🧲"),
            ("style", "스타일", "🎨"),
            ("voice", "음성/TTS", "🎤"),
            ("queue", "대기/진행", "📋"),
            ("progress", "결과/로그", "📈"),
            ("subscription", "구독/결제", "💳"),
        ]
        self.step_nav = StepNav(steps)
        main_layout.addWidget(self.step_nav)

        # 2. Main Content Area (Right Side)
        content_container = QWidget()
        content_container.setObjectName("ContentContainer")
        content_container.setStyleSheet(f"#ContentContainer {{ background-color: {d.colors.bg_main}; }}")
        
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 2-1. Top Bar
        content_layout.addWidget(self._build_topbar())

        # 2-2. Stacked Pages
        self.stack = QStackedWidget()
        
        # Add padding around the stack for better visual balance
        stack_wrapper = QWidget()
        stack_layout = QVBoxLayout(stack_wrapper)
        stack_layout.setContentsMargins(40, 30, 40, 30)  # Generous padding
        stack_layout.addWidget(self.stack)
        
        content_layout.addWidget(stack_wrapper)
        main_layout.addWidget(content_container)

        # Build pages as cards
        self.url_input_panel = URLInputPanel(self.stack, self, theme_manager=self.theme_manager)
        self.style_tab = StyleTab(self.stack, self, theme_manager=self.theme_manager)
        self.voice_panel = VoicePanel(self.stack, self, theme_manager=self.theme_manager)
        self.queue_panel = QueuePanel(self.stack, self, theme_manager=self.theme_manager)
        self.progress_panel = ProgressPanel(self.stack, self, theme_manager=self.theme_manager)
        self.subscription_panel = SubscriptionPanel(self.stack, self)

        pages = [
            ("source", "소스 입력", "숏폼으로 변환할 쇼핑몰 링크나 영상을 추가하세요.", self.url_input_panel),
            ("style", "스타일", "자막, 배경음악, 폰트 등 영상 스타일을 설정합니다.", self.style_tab),
            ("voice", "음성/TTS", "AI 성우 목소리와 나레이션 스타일을 선택하세요.", self.voice_panel),
            ("queue", "대기/진행", "작업 대기열 및 진행 상황을 관리합니다.", self.queue_panel),
            ("progress", "결과/로그", "변환 결과물과 시스템 로그를 확인합니다.", self.progress_panel),
            ("subscription", "구독/결제", "요금제 관리 및 결제 내역을 확인합니다.", self.subscription_panel),
        ]

        self.page_index = {}
        for idx, (sid, title, subtitle, widget) in enumerate(pages):
            card = self._wrap_card(widget, title, subtitle)
            self.stack.addWidget(card)
            self.page_index[sid] = idx

        self.step_nav.step_selected.connect(self._on_step_selected)
        self._on_step_selected("source")

        # Status bar is separate at main window level or can be added to bottom of content
        # Adding to content layout to keep sidebar full height
        self.status_bar = StatusBar(self, self)
        content_layout.addWidget(self.status_bar)

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
        # Removing border-bottom here if we want a cleaner look, or keeping it subtle
        bar.setStyleSheet(f"""
            #TopBar {{
                background-color: {c.bg_header};
                border-bottom: 1px solid {c.border_light};
            }}
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(40, 20, 40, 20)  # Matching content padding
        layout.setSpacing(20)

        # Breadcrumbs / Title
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        
        app_title = QLabel("Shopping Shorts Maker")
        app_title.setFont(QFont(d.typography.font_family_heading, 14, QFont.Weight.Bold))
        app_title.setStyleSheet(f"color: {c.text_primary};")
        
        project_sub = QLabel("Project: New Video")
        project_sub.setFont(QFont(d.typography.font_family_body, 12))
        project_sub.setStyleSheet(f"color: {c.text_secondary};")
        
        title_box.addWidget(app_title)
        title_box.addWidget(project_sub)
        layout.addLayout(title_box)

        layout.addStretch()

        # Right side actions
        
        # Subscription Badge
        sub_badge = QLabel("PRO PLAN")
        sub_badge.setFont(QFont(d.typography.font_family_body, 10, QFont.Weight.Bold))
        sub_badge.setStyleSheet(f"""
            background-color: {c.primary_light};
            color: {c.primary};
            padding: 6px 12px;
            border-radius: 6px;
        """)
        layout.addWidget(sub_badge)

        # Settings Button
        settings_btn = QPushButton("Preferences")
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
