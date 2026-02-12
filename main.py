# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - PyQt6 main application entry.

Refactored into modular mixins for maintainability:
- app/mixins/: StateBridge, Logging, Progress, WindowEvents, Delegation
- app/ui_initializer.py: UI construction
- app/video_helpers.py: Video processing helpers
- managers/generated_video_manager.py: Video output management
"""
import sys
import os
import threading
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow

import config

FFMPEG_FALLBACK = r"C:\Program Files (x86)\UltData\Resources\ffmpegs"
if os.path.isdir(FFMPEG_FALLBACK) and FFMPEG_FALLBACK not in os.environ.get("PATH", ""):
    os.environ["PATH"] = FFMPEG_FALLBACK + os.pathsep + os.environ.get("PATH", "")

from app.state import AppState
from app.mixins import (
    StateBridgeMixin,
    LoggingMixin,
    ProgressMixin,
    WindowEventsMixin,
    DelegationMixin,
)
from app.ui_initializer import UIInitializer
from app.video_helpers import VideoHelpers
from app.api_handler import APIHandler
from app.batch_handler import BatchHandler
from managers.queue_manager import QueueManager
from managers.voice_manager import VoiceManager
from managers.output_manager import OutputManager
from managers.progress_manager import ProgressManager
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from managers.generated_video_manager import GeneratedVideoManager
from managers.youtube_manager import get_youtube_manager
from managers.coupang_manager import CoupangManager
from managers.inpock_manager import get_inpock_manager
from managers.sourcing_manager import get_sourcing_manager
from ui.theme_manager import get_theme_manager
from ui.design_system_v2 import get_design_system
from pathlib import Path
from utils.logging_config import get_logger, AppLogger
from utils.error_handlers import global_exception_handler, thread_exception_handler
from utils.token_cost_calculator import TokenCostCalculator
from core.providers import VertexGeminiProvider
from core.api import ApiKeyManager
from app.login_handler import LoginHandler
from app.exit_handler import ExitHandler

logger = get_logger(__name__)


class VideoAnalyzerGUI(
    QMainWindow,
    StateBridgeMixin,
    LoggingMixin,
    ProgressMixin,
    WindowEventsMixin,
    DelegationMixin,
):
    """Main application window for Shopping Shorts Maker."""

    update_status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str, str)
    ui_callback_signal = pyqtSignal(object)

    def __init__(self, parent=None, login_data=None, preloaded_ocr=None, ocr_init_attempted: bool = False):
        super().__init__(parent)
        self.login_data = login_data
        self.preloaded_ocr = preloaded_ocr
        self.ocr_init_attempted = ocr_init_attempted
        self.config = config

        # Core state and design
        self.state = AppState(root=self, login_data=login_data)
        self.theme_manager = get_theme_manager()
        self.design = get_design_system()

        # Setup state aliases (from StateBridgeMixin)
        self._setup_state_aliases()
        self._setup_ocr_reader(preloaded_ocr, allow_fallback=not ocr_init_attempted)

        # Processing state
        self.api_key_manager = None
        self.batch_processing = False
        self.dynamic_processing = False
        self.batch_thread: Optional[threading.Thread] = None
        self.batch_processing_lock = threading.Lock()
        self.url_status_lock = threading.Lock()
        self.genai_client = None
        self.token_calculator = TokenCostCalculator()

        # Initialize managers
        self.queue_manager = QueueManager(self)
        self.voice_manager = VoiceManager(self)
        self.output_manager = OutputManager(self)
        self.api_handler = APIHandler(self)
        self.batch_handler = BatchHandler(self)
        self._video_helpers = VideoHelpers(self)
        self._generated_video_manager = GeneratedVideoManager(self)
        self.youtube_manager = get_youtube_manager(gui=self)
        self.coupang_manager = CoupangManager()
        # Selenium-based managers must not crash the app on machines without selenium/chrome.
        # Their heavy imports are guarded and the driver is created lazily.
        self.inpock_manager = get_inpock_manager()
        self.sourcing_manager = get_sourcing_manager()

        # Load API keys and initialize provider
        self.api_handler.load_saved_api_keys()
        self._init_api_key_manager()
        self.model_provider = VertexGeminiProvider()
        self._warn_if_vertex_unset()

        # Set genai_client from model_provider
        self.state.genai_client = self.model_provider.gemini_client
        self.genai_client = self.model_provider.gemini_client

        # Tutorial flag
        self._tutorial_shown = False
        self._check_first_run()

        # Build UI
        self.init_ui()

        # Post-UI managers
        self.progress_manager = ProgressManager(self)
        self.session_manager = SessionManager(self)
        self.topbar.refresh_user_status()

        # Resize throttle
        self._resize_throttle = QTimer(self)
        self._resize_throttle.setSingleShot(True)
        self._resize_throttle.setInterval(80)
        self._resize_throttle.timeout.connect(self._on_resize_done)
        self._is_resizing = False

        # Subscription manager
        self.subscription_manager = SubscriptionManager(self)
        self.subscription_manager.start()

        # Login/exit handlers
        self.login_handler = LoginHandler(self)
        self.exit_handler = ExitHandler(self)
        if self.login_data:
            self.login_handler.start_login_watch()

        # Connect signals
        self.log_signal.connect(self._on_log_signal)
        self.ui_callback_signal.connect(self._execute_ui_callback)

    def _init_api_key_manager(self):
        """Initialize API key manager for key rotation."""
        if config.GEMINI_API_KEYS:
            try:
                self.api_key_manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)
                if self.api_key_manager.api_keys:
                    first_key_name = next(iter(self.api_key_manager.api_keys))
                    self.api_key_manager.current_key = first_key_name
                    logger.info(f"[Main] API key manager: {len(self.api_key_manager.api_keys)}개 키")
            except Exception as e:
                logger.warning(f"[Main] API key manager init failed: {e}")

    def init_client(self, use_specific_key=None) -> bool:
        """Reinitialize Gemini client with new API key."""
        try:
            from google import genai
            key = use_specific_key
            key_name = "직접지정"

            if not key:
                mgr = getattr(self, "api_key_manager", None)
                if mgr:
                    try:
                        key = mgr.get_available_key()
                        key_name = getattr(mgr, "current_key", "unknown")
                    except Exception:
                        key = None

            if not key:
                key = self.model_provider._get_first_api_key()
                key_name = "config_fallback"

            if not key:
                logger.warning("[init_client] 사용 가능한 API 키가 없습니다.")
                return False

            client = genai.Client(api_key=key)
            self.genai_client = client
            self.state.genai_client = client
            self.model_provider.gemini_client = client
            self.model_provider._api_key_configured = True
            logger.info(f"[init_client] Gemini 클라이언트 재초기화 (키: {key_name})")
            return True
        except Exception as e:
            logger.error(f"[init_client] 초기화 실패: {e}")
            return False

    def _warn_if_vertex_unset(self):
        """Check if Gemini API key is set."""
        if not config.GEMINI_API_KEYS:
            logger.info("[Provider] Gemini API 키를 설정에서 등록해주세요.")

    def init_ui(self):
        """Initialize UI using UIInitializer."""
        initializer = UIInitializer(self)
        widgets = initializer.build_ui()

        # Store widget references
        self.step_nav = widgets["step_nav"]
        self.progress_panel = widgets["progress_panel"]
        self.topbar = widgets["topbar"]
        self.stack = widgets["stack"]
        self.page_index = widgets["page_index"]
        self.status_bar = widgets["status_bar"]

        # Store panel references
        self.mode_selection_panel = widgets["mode_selection_panel"]
        self.url_input_panel = widgets["url_input_panel"]
        self.voice_panel = widgets["voice_panel"]
        self.cta_panel = widgets["cta_panel"]
        self.font_panel = widgets["font_panel"]
        self.watermark_panel = widgets["watermark_panel"]
        self.upload_panel = widgets["upload_panel"]
        self.queue_panel = widgets["queue_panel"]
        self.settings_tab = widgets["settings_tab"]
        self.subscription_panel = widgets["subscription_panel"]
        self.api_key_section = widgets["api_key_section"]

        # Connect signals
        self.mode_selection_panel.mode_selected.connect(self._on_mode_selected)
        self.step_nav.step_selected.connect(self._on_step_selected)
        self._on_step_selected("mode")

    def _on_mode_selected(self, mode: str):
        """Handle mode selection."""
        logger.info(f"[Mode] 선택된 모드: {mode}")
        if hasattr(self, 'url_input_panel') and hasattr(self.url_input_panel, 'refresh_mode'):
            self.url_input_panel.refresh_mode()

    def _on_step_selected(self, step_id: str):
        """Handle step navigation."""
        idx = self.page_index.get(step_id, 0)
        self.stack.setCurrentIndex(idx)
        self.step_nav.set_active(step_id)

        try:
            from caller.rest import log_user_action
            log_user_action("메뉴 이동", f"사용자가 '{step_id}'(으)로 이동했습니다.")
        except Exception:
            pass


def main():
    sys.excepthook = global_exception_handler
    import threading
    threading.excepthook = thread_exception_handler
    AppLogger.setup(Path("logs"), level="INFO")

    # DPI awareness (must be before QApplication)
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    try:
        from startup.environment import setup_dpi_awareness
        setup_dpi_awareness()
    except Exception:
        pass

    app = QApplication(sys.argv)
    gui = VideoAnalyzerGUI()
    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
