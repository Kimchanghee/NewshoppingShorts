# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - PyQt6 main application entry.
Re-designed with Enhanced Design System (Industrial-Creative Hybrid)
"""
import sys
import os
import re
import shutil
import threading
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
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
from app.batch_handler import BatchHandler
from managers.queue_manager import QueueManager
from managers.voice_manager import VoiceManager
from managers.output_manager import OutputManager
from managers.progress_manager import ProgressManager
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from ui.panels import (
    URLInputPanel, VoicePanel, QueuePanel,
    ProgressPanel, SubscriptionPanel, FontPanel, CTAPanel,
)
from ui.panels.settings_tab import SettingsTab
from ui.panels.topbar_panel import TopBarPanel
from ui.components.status_bar import StatusBar
from ui.theme_manager import get_theme_manager
from ui.design_system_v2 import get_design_system
from utils.logging_config import get_logger
from utils.error_handlers import global_exception_handler
from utils.token_cost_calculator import TokenCostCalculator
from core.providers import VertexGeminiProvider
from core.api import ApiKeyManager
from app.login_handler import LoginHandler
from app.exit_handler import ExitHandler
from ui.components.step_nav import StepNav
from ui.components.tutorial_manager import show_guided_tutorial

logger = get_logger(__name__)


class VideoAnalyzerGUI(QMainWindow):
    # Signals for cross-thread logging/progress
    update_status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str, str)  # message, level

    def __init__(self, parent=None, login_data=None, preloaded_ocr=None):
        super().__init__(parent)
        self.login_data = login_data
        self.preloaded_ocr = preloaded_ocr
        self.config = config  # config 모듈 참조 (pipeline.py, tts_processor.py에서 app.config.X 접근)
        self.state = AppState(root=self, login_data=login_data)
        self.theme_manager = get_theme_manager()
        self.design = get_design_system()  # Load enhanced design system

        # --- Single source of truth: state owns data, GUI references it ---
        self.url_queue = self.state.url_queue
        self.url_status = self.state.url_status
        self.url_status_message = self.state.url_status_message
        self.url_timestamps = self.state.url_timestamps
        self.url_remarks = self.state.url_remarks

        self.output_folder_path = self.state.output_folder_path
        self.output_folder_label = None

        self.voice_profiles = self.state.voice_profiles
        self.voice_vars = self.state.voice_vars
        self.voice_sample_paths = self.state.voice_sample_paths
        self.multi_voice_presets = self.state.multi_voice_presets
        self.available_tts_voices = self.state.available_tts_voices
        self.max_voice_selection = self.state.max_voice_selection

        self.api_key_manager = None

        # --- Processing state ---
        self.batch_processing = False
        self.dynamic_processing = False
        self.batch_thread: Optional[threading.Thread] = None
        self.batch_processing_lock = threading.Lock()
        self.url_status_lock = threading.Lock()

        # --- State from AppState (direct references for processor.py compat) ---
        self.analysis_result = self.state.analysis_result
        self.translation_result = self.state.translation_result
        self.tts_file_path = self.state.tts_file_path
        self.tts_files = self.state.tts_files
        self.final_video_path = self.state.final_video_path
        self.final_video_temp_dir = self.state.final_video_temp_dir
        self.generated_videos = self.state.generated_videos
        self.speaker_voice_mapping = self.state.speaker_voice_mapping
        self.last_tts_segments = self.state.last_tts_segments
        self._per_line_tts = self.state._per_line_tts
        self.tts_sync_info = self.state.tts_sync_info
        self.progress_states = self.state.progress_states
        self.session_id = self.state.session_id
        self.base_tts_dir = self.state.base_tts_dir
        self.tts_output_dir = self.state.tts_output_dir
        self.voice_sample_dir = self.state.voice_sample_dir
        self._temp_downloaded_file = self.state._temp_downloaded_file
        self.fixed_tts_voice = self.state.fixed_tts_voice
        self.selected_tts_voice = self.state.selected_tts_voice
        self.last_voice_used = self.state.last_voice_used
        self.mirror_video = self.state.mirror_video
        self.add_subtitles = self.state.add_subtitles
        self.cached_video_width = self.state.cached_video_width
        self.cached_video_height = self.state.cached_video_height
        self.current_processing_index = self.state.current_processing_index
        self._current_processing_url = self.state._current_processing_url
        self.korean_subtitle_override = self.state.korean_subtitle_override
        self.korean_subtitle_mode = self.state.korean_subtitle_mode
        self.url_gap_seconds = self.state.url_gap_seconds
        self.center_subtitle_region = self.state.center_subtitle_region
        self.last_chinese_script_lines = self.state.last_chinese_script_lines
        self.last_chinese_script_text = self.state.last_chinese_script_text
        self.last_chinese_script_digest = self.state.last_chinese_script_digest
        self.ocr_reader = self.state.ocr_reader

        # --- Gemini client (direct reference for processor/analysis compat) ---
        self.genai_client = None

        # --- Token cost calculator ---
        self.token_calculator = TokenCostCalculator()

        # --- Managers ---
        self.queue_manager = QueueManager(self)
        self.voice_manager = VoiceManager(self)
        self.output_manager = OutputManager(self)
        self.api_handler = APIHandler(self)
        self.batch_handler = BatchHandler(self)

        # API 키를 먼저 로드한 후 Provider 초기화
        self.api_handler.load_saved_api_keys()

        # Initialize API key manager for key rotation during batch processing
        if config.GEMINI_API_KEYS:
            try:
                self.api_key_manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)
                # 초기 current_key 설정 (첫 번째 사용 가능 키)
                if self.api_key_manager.api_keys:
                    first_key_name = next(iter(self.api_key_manager.api_keys))
                    self.api_key_manager.current_key = first_key_name
                    logger.info(f"[Main] API key manager 초기화 완료: {len(self.api_key_manager.api_keys)}개 키, 현재: {first_key_name}")
            except Exception as e:
                logger.warning(f"[Main] API key manager init failed: {e}")

        self.model_provider = VertexGeminiProvider()
        self._warn_if_vertex_unset()

        # Set genai_client from model_provider for both state and self
        self.state.genai_client = self.model_provider.gemini_client
        self.genai_client = self.model_provider.gemini_client

        # Tutorial flag
        self._tutorial_shown = False
        self._check_first_run()

        self.init_ui()

        # ProgressManager (requires progress_panel to exist from init_ui)
        self.progress_manager = ProgressManager(self)

        # SessionManager
        self.session_manager = SessionManager(self)

        self.topbar.refresh_user_status()

        # 리사이즈 성능 최적화
        self._resize_throttle = QTimer(self)
        self._resize_throttle.setSingleShot(True)
        self._resize_throttle.setInterval(80)
        self._resize_throttle.timeout.connect(self._on_resize_done)
        self._is_resizing = False

        # 구독 상태 자동 갱신 매니저
        self.subscription_manager = SubscriptionManager(self)
        self.subscription_manager.start()

        # Login watch & exit handlers
        self.login_handler = LoginHandler(self)
        self.exit_handler = ExitHandler(self)
        if self.login_data:
            self.login_handler.start_login_watch()

        # Connect log_signal to progress panel
        self.log_signal.connect(self._on_log_signal)

    # ================================================================
    # Window close event
    # ================================================================
    def closeEvent(self, event):
        """Override QMainWindow closeEvent to handle safe exit."""
        if getattr(self, "_closing", False):
            event.accept()
            return

        if hasattr(self, "exit_handler"):
            # Check if batch processing - ask user to confirm
            if self.batch_processing:
                from ui.components.custom_dialog import show_question
                try:
                    result = show_question(
                        self,
                        "종료 확인",
                        "배치 처리가 진행 중입니다.\n\n"
                        "정말 종료하시겠습니까?\n"
                        "(현재 작업은 중단됩니다)",
                    )
                    if not result:
                        event.ignore()
                        return
                except Exception:
                    pass

            self._closing = True
            self.exit_handler.safe_exit()

        event.accept()

    # ================================================================
    # Gemini client re-initialization (API key rotation support)
    # ================================================================
    def init_client(self, use_specific_key=None) -> bool:
        """Gemini 클라이언트 재초기화 (API 키 교체 시)

        use_specific_key: 직접 지정할 API 키 값. None이면 api_key_manager에서 다음 키 자동 선택.
        """
        try:
            from google import genai

            key = use_specific_key
            key_name = "직접지정"

            # use_specific_key가 없으면 api_key_manager에서 다음 사용 가능한 키 선택
            if not key:
                mgr = getattr(self, "api_key_manager", None)
                if mgr is not None:
                    try:
                        key = mgr.get_available_key()
                        key_name = getattr(mgr, "current_key", "unknown")
                    except Exception as mgr_err:
                        logger.warning(f"[init_client] api_key_manager 키 선택 실패: {mgr_err}")
                        key = None

            # api_key_manager가 없거나 실패한 경우 provider에서 가져오기
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
            logger.info(f"[init_client] Gemini 클라이언트 재초기화 완료 (키: {key_name})")
            return True
        except Exception as e:
            logger.error(f"[init_client] 초기화 실패: {e}")
            return False

    # ================================================================
    # Logging (processor.py calls app.add_log)
    # ================================================================
    def add_log(self, message: str, level: str = "info"):
        """스레드 안전 로깅 - log_signal emit"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        try:
            self.log_signal.emit(full_msg, level)
        except RuntimeError:
            log_method = getattr(logger, level, logger.info)
            log_method(full_msg)

    def _on_log_signal(self, message: str, level: str):
        """메인 스레드에서 로그 표시"""
        panel = getattr(self, "progress_panel", None)
        if panel is not None and hasattr(panel, "append_log"):
            panel.append_log(message, level)
        else:
            log_method = getattr(logger, level, logger.info)
            log_method(message)

    # ================================================================
    # Progress state (delegated to ProgressManager if available)
    # ================================================================
    def update_progress_state(self, step: str, status: str, progress: float = 0, message: str = None):
        mgr = getattr(self, "progress_manager", None)
        if mgr is not None:
            mgr.update_progress_state(step, status, progress, message)
        else:
            self.progress_states[step] = {
                "status": status,
                "progress": progress,
                "message": message,
            }

    def update_step_progress(self, step: str, value: float):
        mgr = getattr(self, "progress_manager", None)
        if mgr is not None:
            mgr.update_step_progress(step, value)

    def reset_progress_states(self):
        mgr = getattr(self, "progress_manager", None)
        if mgr is not None:
            mgr.reset_progress_states()
        else:
            for step in self.progress_states:
                self.progress_states[step] = {
                    "status": "waiting",
                    "progress": 0,
                    "message": None,
                }

    def set_active_job(self, source: str, index: int = None, total: int = None):
        mgr = getattr(self, "progress_manager", None)
        if mgr is not None:
            mgr.set_active_job(source, index, total)

    def set_active_voice(self, voice_id: str, voice_index: int = None, voice_total: int = None):
        mgr = getattr(self, "progress_manager", None)
        if mgr is not None:
            mgr.set_active_voice(voice_id, voice_index, voice_total)

    def update_all_progress_displays(self):
        mgr = getattr(self, "progress_manager", None)
        if mgr is not None and hasattr(mgr, "update_all_progress_displays"):
            mgr.update_all_progress_displays()

    def update_overall_progress_display(self):
        mgr = getattr(self, "progress_manager", None)
        if mgr is not None and hasattr(mgr, "update_overall_progress"):
            mgr.update_overall_progress("overall", "processing")

    # ================================================================
    # Status update
    # ================================================================
    def update_status(self, status_text: str):
        """상태바 업데이트"""
        bar = getattr(self, "status_bar", None)
        if bar is not None and hasattr(bar, "update_status"):
            bar.update_status(status_text)

    # ================================================================
    # URL listbox (delegated to QueueManager)
    # ================================================================
    def update_url_listbox(self):
        self.queue_manager.update_url_listbox()

    # ================================================================
    # Video duration helper
    # ================================================================
    def get_video_duration_helper(self) -> float:
        """원본 영상 길이 반환"""
        try:
            from moviepy.editor import VideoFileClip
            source = getattr(self, "_temp_downloaded_file", None)
            if source and os.path.exists(source):
                clip = VideoFileClip(source)
                duration = clip.duration
                clip.close()
                return duration
        except Exception as e:
            logger.warning(f"[Duration] 영상 길이 확인 실패: {e}")
        return 0.0

    # ================================================================
    # Chinese subtitle removal (blur)
    # ================================================================
    def apply_chinese_subtitle_removal(self, video):
        """중국어 자막 블러 처리"""
        try:
            from processors.subtitle_processor import SubtitleProcessor
            processor = SubtitleProcessor(self)
            return processor.apply_chinese_subtitle_removal(video)
        except Exception as e:
            logger.warning(f"[Subtitle Removal] 실패: {e}")
            return video

    # ================================================================
    # Subtitle detection with OpenCV
    # ================================================================
    def detect_subtitles_with_opencv(self):
        """OCR 기반 자막 위치 감지"""
        try:
            from processors.subtitle_detector import SubtitleDetector
            detector = SubtitleDetector(self)
            return detector.detect_subtitles_with_opencv()
        except Exception as e:
            logger.warning(f"[OCR] 자막 감지 실패: {e}")
            return []

    # ================================================================
    # Script extraction (called by tts_generator.py as app.extract_...)
    # ================================================================
    def extract_clean_script_from_translation(self, max_len: int = 14) -> str:
        """번역 결과에서 한국어 대본 추출 (메타데이터/타임스탬프 제거)"""
        try:
            raw = (self.translation_result or "").strip()
            full_script = ""

            if raw:
                cleaned_lines = []
                for original_line in raw.splitlines():
                    line = original_line.strip()
                    if not line:
                        continue
                    if re.match(r"^[#*= -]{3,}$", line):
                        continue
                    line = re.sub(r"\[[^\]]*\]", "", line)
                    line = re.sub(r"\([^)]*\)", "", line)
                    line = re.sub(r"^\d+[\.)]\s*", "", line)
                    line = re.sub(r"^(?:-|\*|\u2022)\s*", "", line)
                    line = re.sub(r"\s+", " ", line).strip()
                    if len(line) < 2:
                        continue
                    cleaned_lines.append(line)

                if not cleaned_lines:
                    cleaned_lines = [
                        l.strip() for l in raw.splitlines() if l.strip()
                    ]
                full_script = re.sub(r"\s+", " ", " ".join(cleaned_lines)).strip()

            if not full_script:
                video_analysis = getattr(self, "video_analysis_result", None)
                if video_analysis:
                    if isinstance(video_analysis, str):
                        full_script = video_analysis.strip()
                    elif isinstance(video_analysis, dict):
                        full_script = video_analysis.get("description", "") or video_analysis.get("script", "")

            if not full_script and isinstance(getattr(self, "analysis_result", None), dict):
                alt = self.analysis_result.get("script")
                if isinstance(alt, list):
                    fallback = " ".join(
                        str(entry.get("text", "")).strip()
                        for entry in alt
                        if isinstance(entry, dict) and entry.get("text")
                    )
                    full_script = re.sub(r"\s+", " ", fallback).strip()

            if max_len and len(full_script) > max_len * 200:
                full_script = full_script[: max_len * 200].rsplit(" ", 1)[0].strip()

            return full_script
        except Exception as e:
            logger.error(f"[ScriptExtract] 스크립트 추출 오류: {e}")
            return re.sub(r"[^\w\s.,!?\uAC00-\uD7A3]", "", self.translation_result or "").strip()

    # ================================================================
    # Temp file cleanup
    # ================================================================
    def cleanup_temp_files(self):
        """임시 다운로드 파일 정리"""
        temp_file = getattr(self, "_temp_downloaded_file", None)
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                logger.debug(f"[정리] 임시 파일 삭제: {temp_file}")
            except Exception as e:
                logger.debug(f"[정리] 삭제 실패 (무시됨): {e}")
        self._temp_downloaded_file = None

    # ================================================================
    # Generated video registration and saving
    # ================================================================
    def register_generated_video(self, voice, output_path, duration, file_size, temp_dir):
        """생성된 영상 정보 등록"""
        if not hasattr(self, "generated_videos"):
            self.generated_videos = []
        self.generated_videos.append({
            "voice": voice,
            "path": output_path,
            "duration": duration,
            "file_size_mb": file_size,
            "temp_dir": temp_dir,
            "timestamp": datetime.now().isoformat(),
        })

    def save_generated_videos_locally(self, show_popup=True):
        """생성된 영상들을 출력 폴더로 복사"""
        if not hasattr(self, "generated_videos") or not self.generated_videos:
            return

        output_dir = getattr(self, "output_folder_path", None)
        if not output_dir:
            output_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        os.makedirs(output_dir, exist_ok=True)

        # URL별 하위 폴더 생성
        url = getattr(self, "_current_processing_url", "") or ""
        start_time = getattr(self, "_processing_start_time", datetime.now())
        timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")

        # URL에서 폴더명 생성
        import re
        url_slug = re.sub(r"[^0-9a-zA-Z가-힣-_]+", "_", url)[:60] if url else "local"
        subfolder_name = f"{timestamp_str}_{url_slug}"
        url_output_dir = os.path.join(output_dir, subfolder_name)
        os.makedirs(url_output_dir, exist_ok=True)

        saved_count = 0
        for video_info in self.generated_videos:
            src_path = video_info.get("path", "")
            if not src_path or not os.path.exists(src_path):
                continue
            dst_path = os.path.join(url_output_dir, os.path.basename(src_path))
            try:
                shutil.move(src_path, dst_path)
                video_info["saved_path"] = dst_path
                saved_count += 1
                logger.info(f"[저장] {os.path.basename(dst_path)} -> {url_output_dir}")
            except Exception as e:
                logger.error(f"[저장] 파일 이동 실패: {e}")
                try:
                    shutil.copy2(src_path, dst_path)
                    video_info["saved_path"] = dst_path
                    saved_count += 1
                except Exception as copy_err:
                    logger.error(f"[저장] 복사도 실패: {copy_err}")

        # 임시 디렉토리 정리
        for video_info in self.generated_videos:
            temp_dir = video_info.get("temp_dir")
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

        if saved_count > 0 and show_popup:
            from ui.components.custom_dialog import show_success
            show_success(
                self, "저장 완료",
                f"{saved_count}개 영상이 저장되었습니다.\n{url_output_dir}"
            )

    # ================================================================
    # Session management
    # ================================================================
    def _auto_save_session(self):
        """세션 자동 저장"""
        mgr = getattr(self, "session_manager", None)
        if mgr is not None:
            try:
                mgr.save_session()
            except Exception as e:
                logger.warning(f"[세션] 자동 저장 실패: {e}")

    def _check_first_run(self):
        """Always show tutorial on app launch"""
        self._should_show_tutorial = True

    def _mark_tutorial_complete(self):
        """Mark tutorial as completed"""
        config_dir = os.path.join(os.path.expanduser("~"), ".ssmaker")
        os.makedirs(config_dir, exist_ok=True)
        tutorial_flag = os.path.join(config_dir, ".tutorial_complete")
        with open(tutorial_flag, 'w') as f:
            f.write("1")

    def resizeEvent(self, event):
        """리사이즈 중 비필수 업데이트 일시 중지"""
        super().resizeEvent(event)
        if not self._is_resizing:
            self._is_resizing = True
            self.subscription_manager.pause_countdown()
        self._resize_throttle.start()

    def _on_resize_done(self):
        """리사이즈 완료 후 정상 복구"""
        self._is_resizing = False
        self.subscription_manager.resume_countdown()

    def showEvent(self, event):
        """Show tutorial on first launch"""
        super().showEvent(event)
        if hasattr(self, '_should_show_tutorial') and self._should_show_tutorial and not self._tutorial_shown:
            self._tutorial_shown = True
            QTimer.singleShot(500, self._show_tutorial)

    def _show_tutorial(self):
        """Display guided tutorial with spotlight effect"""
        self._tutorial_manager = show_guided_tutorial(self)

    def show_tutorial_manual(self):
        """Manually show tutorial (from settings or help menu)"""
        if hasattr(self, '_tutorial_manager') and self._tutorial_manager and self._tutorial_manager.is_running:
            self._tutorial_manager.stop()
        self._tutorial_manager = show_guided_tutorial(self)

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
        left_container.setMaximumWidth(280)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 1. Sidebar (StepNav)
        steps = [
            ("source", "소스 입력", "source"),
            ("voice", "음성 선택", "voice"),
            ("cta", "CTA 선택", "cta"),
            ("font", "폰트 선택", "font"),
            ("queue", "대기/진행", "queue"),
            ("settings", "설정", "settings"),
        ]
        self.step_nav = StepNav(steps)
        left_layout.addWidget(self.step_nav, stretch=0)

        # 2. Minimal spacer
        left_layout.addSpacing(4)

        # 3. Log Panel (ProgressPanel) - Bottom left, takes remaining space
        self.progress_panel = ProgressPanel(self, self, theme_manager=self.theme_manager)
        self.progress_panel.setMinimumHeight(360)
        self.progress_panel.setMaximumHeight(600)
        self.progress_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self.progress_panel, stretch=1)

        main_layout.addWidget(left_container)

        # 3. Main Content Area (Right Side)
        right_container = QWidget()
        right_container.setObjectName("RightContainer")
        right_container.setStyleSheet(f"#RightContainer {{ background-color: {d.colors.bg_main}; }}")

        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 3-1. Top Bar
        self.topbar = TopBarPanel(self, self.design)
        right_layout.addWidget(self.topbar)

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
        stack_layout.setContentsMargins(20, 16, 20, 16)
        stack_layout.addWidget(self.stack)

        content_layout.addWidget(stack_wrapper)
        right_layout.addWidget(content_container)
        main_layout.addWidget(right_container, stretch=1)

        # Build pages as cards
        self.url_input_panel = URLInputPanel(self.stack, self, theme_manager=self.theme_manager)
        self.voice_panel = VoicePanel(self.stack, self, theme_manager=self.theme_manager)
        self.cta_panel = CTAPanel(self.stack, self, theme_manager=self.theme_manager)
        self.font_panel = FontPanel(self.stack, self, theme_manager=self.theme_manager)
        self.queue_panel = QueuePanel(self.stack, self, theme_manager=self.theme_manager)
        self.settings_tab = SettingsTab(self.stack, self, theme_manager=self.theme_manager)
        self.api_key_section = self.settings_tab.api_section
        self.subscription_panel = SubscriptionPanel(self.stack, self)

        pages = [
            ("source", "소스 입력", "숏폼으로 변환할 쇼핑몰 링크나 영상을 추가하세요.", self.url_input_panel),
            ("voice", "음성 선택", "AI 성우 목소리와 나레이션 스타일을 선택하세요.", self.voice_panel),
            ("cta", "CTA 선택", "영상 마지막 클릭 유도 멘트를 선택하세요.", self.cta_panel),
            ("font", "폰트 선택", "자막에 사용할 폰트를 선택하세요.", self.font_panel),
            ("queue", "대기/진행", "작업 대기열 및 진행 상황을 관리합니다.", self.queue_panel),
            ("settings", "설정", "앱 설정 및 API 키를 관리합니다.", self.settings_tab),
            ("subscription", "구독 관리", "구독 상태 및 플랜을 관리합니다.", self.subscription_panel),
        ]

        self.page_index = {}
        for idx, (sid, title, subtitle, widget) in enumerate(pages):
            card = self._wrap_card(widget, title, subtitle)
            self.stack.addWidget(card)
            self.page_index[sid] = idx

        self.step_nav.step_selected.connect(self._on_step_selected)
        self._on_step_selected("source")

        # Status bar
        self.status_bar = StatusBar(self, self)
        right_layout.addWidget(self.status_bar)

    # ------------- URL helpers (delegated to QueueManager) -------------
    def add_url_from_entry(self):
        self.queue_manager.add_url_from_entry()

    def paste_and_extract(self):
        self.queue_manager.paste_and_extract()

    def remove_selected_url(self):
        self.queue_manager.remove_selected_url()

    def clear_url_queue(self):
        self.queue_manager.clear_url_queue()

    def clear_waiting_only(self):
        self.queue_manager.clear_waiting_only()

    # ------------- Batch processing (delegated to BatchHandler) -------------
    def _navigate_to_settings(self):
        """설정 탭으로 자동 이동"""
        self._on_step_selected("settings")

    def start_batch_processing(self):
        """배치 처리 시작 - BatchHandler에 위임"""
        self.batch_handler.start_batch_processing()

    def stop_batch_processing(self):
        """배치 처리 중지 - BatchHandler에 위임"""
        self.batch_handler.stop_batch_processing()

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
        """Check if Gemini API key is set."""
        if not config.GEMINI_API_KEYS:
            logger.info("[Provider] Gemini API 키를 설정에서 등록해주세요.")

    # ------------- Delegation stubs (backward compatibility) -------------
    def refresh_user_status(self):
        self.topbar.refresh_user_status()

    def _wrap_card(self, widget: QWidget, title: str, subtitle: str) -> QWidget:
        """컨텐츠 카드 래퍼 - STITCH 디자인 적용"""
        d = self.design

        card = QFrame()
        card.setObjectName("ContentCard")
        card.setStyleSheet(f"""
            #ContentCard {{
                background-color: {d.colors.surface};
                border: 1px solid {d.colors.border_light};
                border-radius: {d.radius.xl}px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(d.spacing.section)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(d.spacing.space_2)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(
            d.typography.font_family_heading,
            d.typography.size_lg,
            QFont.Weight.Bold
        ))
        title_lbl.setStyleSheet(f"""
            color: {d.colors.text_primary};
            letter-spacing: -0.5px;
        """)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(QFont(
            d.typography.font_family_body,
            d.typography.size_sm
        ))
        sub_lbl.setStyleSheet(f"color: {d.colors.text_secondary}; line-height: 1.5;")

        header_layout.addWidget(title_lbl)
        header_layout.addWidget(sub_lbl)

        card_layout.addLayout(header_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {d.colors.border_light};")
        card_layout.addWidget(line)

        card_layout.addWidget(widget)

        return card

    def _on_step_selected(self, step_id: str):
        idx = self.page_index.get(step_id, 0)
        self.stack.setCurrentIndex(idx)
        self.step_nav.set_active(step_id)

    def _show_subscription_panel(self):
        self.topbar.show_subscription_panel()

    def _update_subscription_info(self):
        """구독 정보 표시 갱신"""
        if hasattr(self, "topbar") and hasattr(self.topbar, "refresh_user_status"):
            self.topbar.refresh_user_status()


def main():
    sys.excepthook = global_exception_handler
    app = QApplication(sys.argv)

    gui = VideoAnalyzerGUI()
    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
