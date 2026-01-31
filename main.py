# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - PyQt6 main application entry.
Option 1 shell: Header + StepNav + stacked cards.
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
from utils.logging_config import get_logger
from utils.error_handlers import global_exception_handler
from core.providers import VertexGeminiProvider
from ui.components.step_nav import StepNav

logger = get_logger(__name__)

URL_PATTERN = re.compile(r"https?://[^\\s\"'<>]+")


class VideoAnalyzerGUI(QMainWindow):
    # Signals for cross-thread logging/progress
    update_status_signal = None  # Placeholder signals removed for simplified UI
    log_signal = None

    def __init__(self, parent=None, login_data=None, preloaded_ocr=None):
        super().__init__(parent)
        self.login_data = login_data
        self.preloaded_ocr = preloaded_ocr
        self.state = AppState(root=self, login_data=login_data)
        self.theme_manager = get_theme_manager()

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
        self.setWindowTitle("쇼핑 쇼츠 메이커")
        icon_path = os.path.join(os.path.dirname(__file__), "resource", "mainTrayIcon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1360, 960)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        main_layout.addWidget(self._build_topbar())

        # Body with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizes([260, 1100])

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

        # Stacked pages
        self.stack = QStackedWidget()
        splitter.addWidget(self.stack)

        # Build pages as cards
        self.url_input_panel = URLInputPanel(self.stack, self, theme_manager=self.theme_manager)
        self.style_tab = StyleTab(self.stack, self, theme_manager=self.theme_manager)
        self.voice_panel = VoicePanel(self.stack, self, theme_manager=self.theme_manager)
        self.queue_panel = QueuePanel(self.stack, self, theme_manager=self.theme_manager)
        self.progress_panel = ProgressPanel(self.stack, self, theme_manager=self.theme_manager)
        self.subscription_panel = SubscriptionPanel(self.stack, self)

        pages = [
            ("source", "소스 입력", "링크 또는 파일을 추가하세요.", self.url_input_panel),
            ("style", "스타일", "추천 프리셋과 커스텀 스타일을 구성합니다.", self.style_tab),
            ("voice", "음성/TTS", "목소리 선택 및 미리듣기.", self.voice_panel),
            ("queue", "대기/진행", "진행 대기열과 상태 관리.", self.queue_panel),
            ("progress", "결과/로그", "실시간 로그와 결과 확인.", self.progress_panel),
            ("subscription", "구독/결제", "구독 플랜과 결제 상태를 관리합니다.", self.subscription_panel),
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
        # placeholder: connect to URLInputPanel logic if needed
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
        bar = QFrame()
        bar.setObjectName("TopBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        title = QLabel("Shopping Shorts Maker")
        title.setObjectName("AppTitle")
        title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        project = QLabel("프로젝트: 기본 작업")
        project.setObjectName("ProjectName")
        layout.addWidget(project)

        layout.addStretch()

        self.subscription_badge = QLabel("구독: 미설정")
        self.subscription_badge.setObjectName("SubBadge")
        self.subscription_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subscription_badge)

        help_btn = QPushButton("도움말")
        help_btn.setObjectName("GhostButton")
        layout.addWidget(help_btn)

        settings_btn = QPushButton("설정")
        settings_btn.setObjectName("PrimaryButton")
        settings_btn.clicked.connect(self.show_api_status)
        layout.addWidget(settings_btn)

        return bar

    def _wrap_card(self, widget: QWidget, title: str, subtitle: str) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)

        header = QLabel(title)
        header.setObjectName("CardTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("CardSubtitle")
        card_layout.addWidget(header)
        card_layout.addWidget(sub)
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
        self.setStyleSheet(
            """
            #TopBar { background:#0f172a; color:#e2e8f0; border-bottom:1px solid #1e293b; }
            #AppTitle { color:#e2e8f0; }
            #ProjectName { color:#94a3b8; }
            #SubBadge { padding:6px 12px; border-radius:12px; background:#1d4ed8; color:white; min-width:110px; }
            #GhostButton { background:transparent; color:#e2e8f0; border:1px solid #334155; padding:6px 12px; border-radius:8px; }
            #PrimaryButton { background:#2563eb; color:white; border:none; padding:6px 14px; border-radius:8px; }
            QSplitter::handle { background: #e2e8f0; width: 3px; }
            #StepNav { background:#111827; border-right:1px solid #1f2937; }
            #StepNav QPushButton { 
                background: #111827; color:#cbd5e1; border:1px solid #1f2937; 
                padding:10px 12px; border-radius:8px; text-align:left; 
                font-weight:600;
            }
            #StepNav QPushButton:checked { background:#1d4ed8; color:white; border-color:#1d4ed8; }
            #StepNav QPushButton:hover { background:#1f2937; }
            #Card { background:white; border:1px solid #e2e8f0; border-radius:16px; }
            #CardTitle { font-size:18px; font-weight:700; color:#0f172a; }
            #CardSubtitle { color:#475569; margin-bottom:4px; }
            """
        )


def main():
    sys.excepthook = global_exception_handler
    app = QApplication(sys.argv)
    gui = VideoAnalyzerGUI()
    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
