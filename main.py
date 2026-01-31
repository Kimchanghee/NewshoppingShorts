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
        self.setWindowTitle("쇼핑 쇼츠 메이커 - Studio")
        icon_path = os.path.join(os.path.dirname(__file__), "resource", "mainTrayIcon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1440, 960)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        main_layout.addWidget(self._build_topbar())

        # Body with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizes([260, 1180])
        splitter.setHandleWidth(1)

        # Sidebar steps
        steps = [
            ("source", "소스 입력", "🧲"),
            ("style", "스타일", "🎨"),
            ("voice", "음성/TTS", "🎤"),
            ("queue", "대기/진행", "📋"),
            ("progress", "결과/로그", "📈"),
            ("subscription", "구독/결제", "💳"),
        ]
        self.step_nav = StepNav(steps)
        splitter.addWidget(self.step_nav)

        # Main Content Area
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(20)

        # Stacked pages
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        splitter.addWidget(content_area)

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

        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = StatusBar(self, self)
        main_layout.addWidget(self.status_bar)

        self._apply_shell_styles()

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
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # Logo / Brand
        logo_label = QLabel("SS")
        logo_label.setObjectName("BrandLogo")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setFixedSize(36, 36)
        layout.addWidget(logo_label)

        title = QLabel("쇼핑 쇼츠 메이커")
        title.setObjectName("AppTitle")
        title.setFont(QFont(d.typography.font_family_heading, 18, QFont.Weight.Bold))
        layout.addWidget(title)

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedSize(1, 20)
        sep.setStyleSheet(f"background-color: {c.border_light};")
        layout.addWidget(sep)

        project = QLabel("프로젝트: 기본 작업")
        project.setObjectName("ProjectName")
        project.setFont(QFont(d.typography.font_family_body, 14))
        layout.addWidget(project)

        layout.addStretch()

        # Subscription Badge
        self.subscription_badge = QLabel("PRO")
        self.subscription_badge.setObjectName("SubBadge")
        self.subscription_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subscription_badge)

        # Action Buttons
        help_btn = QPushButton("도움말")
        help_btn.setObjectName("GhostButton")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(help_btn)

        settings_btn = QPushButton("설정")
        settings_btn.setObjectName("PrimaryButton")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.show_api_status)
        layout.addWidget(settings_btn)

        return bar

    def _wrap_card(self, widget: QWidget, title: str, subtitle: str) -> QWidget:
        d = self.design
        
        card = QFrame()
        card.setObjectName("ContentCard")
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(16)

        # Header Area
        header_frame = QFrame()
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 8)
        header_layout.setSpacing(4)
        
        title_lbl = QLabel(title)
        title_lbl.setObjectName("PageTitle")
        title_lbl.setFont(QFont(d.typography.font_family_heading, 28, QFont.Weight.Bold))
        
        sub_lbl = QLabel(subtitle)
        sub_lbl.setObjectName("PageSubtitle")
        sub_lbl.setFont(QFont(d.typography.font_family_body, 14))
        
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(sub_lbl)
        
        card_layout.addWidget(header_frame)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {d.colors.border_light}; max-height: 1px;")
        card_layout.addWidget(line)
        
        # Content
        card_layout.addSpacing(16)
        card_layout.addWidget(widget)
        
        return card

    def _on_step_selected(self, step_id: str):
        idx = self.page_index.get(step_id, 0)
        self.stack.setCurrentIndex(idx)
        self.step_nav.set_active(step_id)

    def _show_subscription_panel(self):
        """Show the subscription/payment panel"""
        self._on_step_selected("subscription")

    def _apply_shell_styles(self):
        d = self.design
        c = d.colors
        t = d.typography
        r = d.radius

        self.setStyleSheet(
            f"""
            /* Global Reset */
            QMainWindow {{
                background-color: {c.bg_main};
            }}
            
            /* Top Bar */
            #TopBar {{
                background-color: {c.bg_header};
                border-bottom: 1px solid {c.border_light};
            }}
            #BrandLogo {{
                background-color: {c.primary};
                color: white;
                border-radius: 8px;
                font-family: {t.font_family_heading};
                font-weight: 800;
                font-size: 16px;
            }}
            #AppTitle {{
                color: {c.text_primary};
            }}
            #ProjectName {{
                color: {c.text_secondary};
            }}
            
            /* Badges & Buttons */
            #SubBadge {{
                background-color: {c.primary_light};
                color: {c.primary};
                padding: 4px 12px;
                border-radius: 12px;
                font-weight: 700;
                font-size: 11px;
            }}
            #GhostButton {{
                background-color: transparent;
                color: {c.text_secondary};
                border: 1px solid {c.border_light};
                padding: 6px 16px;
                border-radius: 8px;
                font-weight: 600;
            }}
            #GhostButton:hover {{
                background-color: {c.bg_hover};
                color: {c.text_primary};
                border-color: {c.border_medium};
            }}
            #PrimaryButton {{
                background-color: {c.primary};
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 8px;
                font-weight: 600;
            }}
            #PrimaryButton:hover {{
                background-color: {c.primary_hover};
            }}
            
            /* Navigation Splitter */
            QSplitter::handle {{
                background: {c.border_light};
                width: 1px;
            }}
            
            /* Sidebar (StepNav) Styles controlled in StepNav component directly or here */
            #StepNav {{
                background-color: {c.bg_sidebar};
                border-right: 1px solid {c.border_light};
            }}
            #StepNav QPushButton {{
                background-color: transparent;
                color: {c.text_secondary};
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                text-align: left;
                font-family: {t.font_family_body};
                font-size: 14px;
                font-weight: 500;
                margin: 0 8px;
            }}
            #StepNav QPushButton:hover {{
                background-color: {c.bg_hover};
                color: {c.text_primary};
            }}
            #StepNav QPushButton:checked {{
                background-color: {c.bg_selected};
                color: {c.primary};
                font-weight: 700;
            }}
            
            /* Content Cards */
            #ContentCard {{
                background-color: {c.bg_card};
                border: 1px solid {c.border_card};
                border-radius: 20px;
                /* Shadows are not supported well in QSS on all widgets, using border for clean look */
            }}
            #PageTitle {{
                color: {c.text_primary};
            }}
            #PageSubtitle {{
                color: {c.text_tertiary};
            }}
            
            /* Scrollbars */
            QScrollBar:vertical {{
                background: {c.bg_main};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {c.scrollbar_thumb};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """
        )


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
