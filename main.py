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

# 최상단에서 UTF-8 강제 — cp949 모지바케(제목/채널명 ????? 깨짐) 근본 차단.
import utils.utf8_boot  # noqa: F401  (import 시점에 force_utf8() 자동 적용)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow

import config

try:
    from startup.environment import setup_ffmpeg_path

    setup_ffmpeg_path()
except Exception:
    pass

# Platform-specific ffmpeg fallback locations.
# Windows: bundled UltData path. macOS: Homebrew (/opt/homebrew, /usr/local), MacPorts.
# Linux: common package-manager locations.
if sys.platform.startswith("win"):
    FFMPEG_FALLBACKS = [r"C:\Program Files (x86)\UltData\Resources\ffmpegs"]
elif sys.platform == "darwin":
    FFMPEG_FALLBACKS = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/opt/local/bin",
    ]
else:  # linux and others
    FFMPEG_FALLBACKS = ["/usr/bin", "/usr/local/bin"]

for _fb in FFMPEG_FALLBACKS:
    if os.path.isdir(_fb) and _fb not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _fb + os.pathsep + os.environ.get("PATH", "")

# imageio-ffmpeg / moviepy 호환: IMAGEIO_FFMPEG_EXE 설정
import shutil as _shutil
_ffmpeg_exe = _shutil.which("ffmpeg")
if not _ffmpeg_exe:
    _exe_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    for _fb in FFMPEG_FALLBACKS:
        _candidate = os.path.join(_fb, _exe_name)
        if os.path.isfile(_candidate):
            _ffmpeg_exe = _candidate
            break
if _ffmpeg_exe:
    os.environ.setdefault("IMAGEIO_FFMPEG_EXE", _ffmpeg_exe)

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
from managers.tiktok_manager import get_tiktok_manager
from managers.instagram_manager import get_instagram_manager
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
        self.tiktok_manager = get_tiktok_manager(gui=self)
        self.instagram_manager = get_instagram_manager(gui=self)
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

        # 첫 실행: 아직 모드를 고르지 않았으므로 모드 종속 탭(영상 넣기 / 전체 자동 만들기 /
        # 다계정 자동화)을 모두 비활성화한다. '만들기 방식'에서 모드를 고르면 활성화된다.
        self._apply_mode_visibility(None)

    def _on_mode_selected(self, mode: str):
        """Handle mode selection.

        Shows/hides sidebar steps depending on the selected mode:
        - single / mix : show 'source', hide 'sourcing'
        - sourcing     : show 'sourcing', hide 'source'
        """
        logger.info(f"[Mode] 선택된 모드: {mode}")
        # Keep GUI alias consistent with AppState.processing_mode
        self.processing_mode = mode
        if hasattr(self, 'state'):
            self.state.processing_mode = mode

        if hasattr(self, 'url_input_panel') and hasattr(self.url_input_panel, 'refresh_mode'):
            self.url_input_panel.refresh_mode()

        # Mode-specific sidebar visibility
        self._apply_mode_visibility(mode)

    def _apply_mode_visibility(self, mode: str):
        """Enable/disable mode-gated left-nav tabs based on the chosen mode.

        - source(영상 넣기): 단일 영상 / 믹스 모드에서만 활성 (직접 영상 입력).
        - sourcing(전체 자동 만들기) · multi_account(다계정 자동화): 전체 자동(풀 자동화)에서만 활성.
        - 첫 실행(모드 미선택, mode=None): 세 탭 모두 비활성 → 모드 선택을 유도.
        비활성 탭은 회색으로 표시되고 클릭·이동이 막힌다.
        """
        step_nav = getattr(self, 'step_nav', None)
        if step_nav is None or not hasattr(step_nav, 'set_step_enabled'):
            return
        is_sourcing = (mode == "sourcing")
        is_manual = mode in ("single", "mix")
        enable_rules = {
            "source": is_manual,           # 단일/믹스 전용
            "sourcing": is_sourcing,       # 전체 자동 전용
            "multi_account": is_sourcing,  # 다계정 = 풀 자동화 전용
        }
        for step_id, enabled in enable_rules.items():
            step_nav.set_step_enabled(step_id, enabled)

    def _on_step_selected(self, step_id: str):
        """Handle step navigation."""
        # '올리기 설정'(upload)은 '설정' 화면의 '영상 올리기' 탭으로 편입됨.
        # 과거 'upload' 타깃으로 들어오는 내비게이션은 설정 화면 + 해당 탭으로 보낸다.
        if step_id == "upload":
            settings_idx = self.page_index.get("settings")
            if settings_idx is not None:
                self.stack.setCurrentIndex(settings_idx)
                self.step_nav.set_active("settings")
                st = getattr(self, "settings_tab", None)
                if st is not None and hasattr(st, "select_upload_tab"):
                    QTimer.singleShot(0, st.select_upload_tab)
                if hasattr(self, "upload_panel"):
                    try:
                        self.upload_panel.refresh()
                    except Exception:
                        pass
            return
        if step_id not in self.page_index:
            # 알 수 없는 step_id로 인해 사용자가 0번(모드 선택) 화면으로 조용히
            # 튕기는 것을 방지한다. (예: 'linktree_setup' 같은 가상 타깃이 폴백 경로로
            # 흘러들어오는 경우) 호출부에서 별도 처리해야 하므로 여기서는 무시한다.
            logger.warning("[Nav] 알 수 없는 step_id '%s' 무시 (페이지 이동 안 함)", step_id)
            return
        idx = self.page_index[step_id]
        self.stack.setCurrentIndex(idx)
        self.step_nav.set_active(step_id)

        try:
            from caller.rest import log_user_action
            log_user_action("메뉴 이동", f"사용자가 '{step_id}'(으)로 이동했습니다.")
        except Exception:
            pass

    def open_api_key_settings(self) -> None:
        """Move to Settings tab and focus API key input area."""
        self._on_step_selected("settings")
        settings_tab = getattr(self, "settings_tab", None)
        if settings_tab and hasattr(settings_tab, "focus_api_key_setup"):
            QTimer.singleShot(0, settings_tab.focus_api_key_setup)

    def open_coupang_settings(self) -> None:
        """Move to Settings tab and reveal/focus the Coupang Partners key fields."""
        self._on_step_selected("settings")
        settings_tab = getattr(self, "settings_tab", None)
        if settings_tab and hasattr(settings_tab, "focus_coupang_setup"):
            QTimer.singleShot(0, settings_tab.focus_coupang_setup)

    def open_youtube_connect(self) -> None:
        """Go to the Upload Settings page and start the YouTube channel connect flow."""
        self._on_step_selected("upload")
        panel = getattr(self, "upload_panel", None)
        if panel is None:
            return
        for name in ("start_youtube_connect", "_show_youtube_json_connect"):
            fn = getattr(panel, name, None)
            if callable(fn):
                QTimer.singleShot(0, fn)
                return

    def refresh_settings_from_manager(self) -> None:
        """Apply synced SettingsManager values to live panels and managers."""
        try:
            from managers.settings_manager import get_settings_manager

            settings = get_settings_manager()
            output_folder = settings.get_output_folder()
            if output_folder:
                self.output_folder_path = output_folder
                if hasattr(self, "state"):
                    self.state.output_folder_path = output_folder

            if hasattr(self, "state"):
                self.state.youtube_auto_upload = settings.get_youtube_auto_upload()
                self.state.youtube_upload_interval_minutes = settings.get_youtube_upload_interval()

            yt_manager = getattr(self, "youtube_manager", None)
            if yt_manager and hasattr(yt_manager, "apply_settings_manager_upload_settings"):
                yt_manager.apply_settings_manager_upload_settings(start_upload=False)

            for attr, method in (
                ("subtitle_settings_panel", "_load_settings"),
                ("watermark_panel", "_load_settings"),
                ("sourcing_panel", "refresh_match_policy"),
                ("settings_tab", "_load_link_automation_settings"),
                ("upload_panel", "refresh"),
            ):
                panel = getattr(self, attr, None)
                callback = getattr(panel, method, None) if panel is not None else None
                if callable(callback):
                    callback()

            logger.info("[SettingsSync] Applied synced settings to live UI")
        except Exception as exc:
            logger.debug("[SettingsSync] Live settings refresh skipped: %s", exc)


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
