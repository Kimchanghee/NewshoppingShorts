# -*- coding: utf-8 -*-

# ★★★ DPI 스케일링 설정은 ssmaker.py에서 처리됨 ★★★
import sys
import os
import re
import shutil
import hashlib
import threading
import queue  # For thread-safe UI updates
import time
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional, Iterable

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

import tkinter as tk
from tkinter import ttk, scrolledtext

try:
    import winsound
except ImportError:
    winsound = None

from caller import rest
from utils.tts_config import get_safe_tts_base_dir
from ui.panels import HeaderPanel, URLInputPanel, VoicePanel, QueuePanel, ProgressPanel
from ui.panels.settings_tab import SettingsTab
from ui.panels.style_tab import StyleTab
from ui.panels.queue_tab import QueueTab
from ui.panels.url_content_panel import URLContentPanel
from ui.components import StatusBar
from ui.components.custom_dialog import (
    show_info,
    show_warning,
    show_error,
    show_question,
)
from ui.components.sidebar_container import SidebarContainer
from ui.components.settings_button import SettingsButton
from ui.components.settings_modal import SettingsModal
from ui.components.theme_toggle import ThemeToggle
from ui.components.tutorial_overlay import TutorialOverlay
from ui.components.fixed_layout import LAYOUT, FixedLayoutConfig
from ui.theme_manager import get_theme_manager
from managers.settings_manager import get_settings_manager
from utils.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

URL_PATTERN = re.compile(r"https?://[^\s\"\'<>]+")


def _configure_stdio_utf8() -> None:
    """Force stdout/stderr to use UTF-8 so logging never crashes on Windows console."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        else:
            import io  # local import to avoid extra dependency when not needed

            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )
    except Exception:
        # If reconfiguration fails we simply continue; worst case the default encoding remains.
        pass


_configure_stdio_utf8()

try:
    from google import genai
    from google.genai import types

    GENAI_SDK_AVAILABLE = True
    GENAI_TYPES_AVAILABLE = True
except Exception as exc:  # pragma: no cover - informative log only
    genai = None
    types = None
    GENAI_SDK_AVAILABLE = False
    GENAI_TYPES_AVAILABLE = False
    warnings.warn(f"[경고] Gemini SDK를 불러오지 못했습니다: {exc}", ImportWarning)

try:
    import cv2  # type: ignore

    CV2_AVAILABLE = True
except Exception as exc:  # pragma: no cover - informative log only
    cv2 = None
    CV2_AVAILABLE = False
    warnings.warn(f"[경고] OpenCV를 불러오지 못했습니다: {exc}", ImportWarning)

try:
    # moviepy 1.x compatible imports
    from moviepy.editor import VideoFileClip, vfx

    MOVIEPY_AVAILABLE = True
except Exception as exc:  # pragma: no cover - informative log only
    VideoFileClip = None
    vfx = None
    MOVIEPY_AVAILABLE = False
    warnings.warn(f"[경고] moviepy를 불러오지 못했습니다: {exc}", ImportWarning)

try:
    from pydub import AudioSegment  # type: ignore

    PYDUB_AVAILABLE = True
except Exception as exc:  # pragma: no cover - informative log only
    AudioSegment = None
    PYDUB_AVAILABLE = False
    warnings.warn(f"[경고] pydub를 불러오지 못했습니다: {exc}", ImportWarning)

# OCR 사용 가능 여부 체크 - Python 버전에 따라 다른 방식
try:
    import importlib.util

    if sys.version_info >= (3, 13):
        # Python 3.13+: pytesseract 사용
        OCR_AVAILABLE = importlib.util.find_spec("pytesseract") is not None
    else:
        # Python 3.13 미만: RapidOCR 우선
        OCR_AVAILABLE = (
            importlib.util.find_spec("rapidocr_onnxruntime") is not None
            or importlib.util.find_spec("pytesseract") is not None
        )
except Exception:
    OCR_AVAILABLE = False

# GPU 가속을 위한 NumPy/CuPy 초기화
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except Exception as exc:
    np = None
    NUMPY_AVAILABLE = False
    warnings.warn(f"[경고] NumPy를 불러오지 못했습니다: {exc}", ImportWarning)

# CuPy 사용 가능 여부 확인 (GPU 가속)
# Python 3.13+에서는 CuPy 미지원 - NumPy만 사용
GPU_ACCEL_AVAILABLE = False
xp = np  # 기본값은 NumPy


def _check_and_install_cupy():
    """
    CuPy 설치 및 GPU 사용 가능 여부 확인
    Check CuPy installation and GPU availability

    Try to use CuPy regardless of Python version, graceful fallback if not compatible.
    Python 버전에 관계없이 CuPy 시도, 호환되지 않으면 자동으로 NumPy로 전환.
    """
    global GPU_ACCEL_AVAILABLE, xp

    # CUDA 경로를 PATH에 추가 (Windows)
    if sys.platform == "win32":
        cuda_paths = [
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin",
        ]
        for cuda_path in cuda_paths:
            if os.path.exists(cuda_path):
                if cuda_path not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = (
                        cuda_path + os.pathsep + os.environ.get("PATH", "")
                    )
                    logger.debug(f"[GPU 가속] CUDA 경로 추가: {cuda_path}")
                break

    try:
        import cupy as cp

        # GPU 사용 가능 여부 엄격 테스트 (DLL 로드 포함)
        test_array = cp.array([1, 2, 3])
        _ = test_array.sum()
        _ = cp.mean(test_array)  # 추가 테스트: NVRTC DLL 필요
        xp = cp
        GPU_ACCEL_AVAILABLE = True
        # CuPy available - GPU acceleration enabled
        return True
    except (ImportError, ModuleNotFoundError):
        # CuPy가 설치되지 않은 경우 - 설치 시도하지 않음 (CUDA 없을 가능성 높음)
        # Silently fallback to NumPy mode
        xp = np
        GPU_ACCEL_AVAILABLE = False
        return False
    except (RuntimeError, OSError, FileNotFoundError, Exception) as exc:
        # CuPy는 설치되었지만 CUDA DLL 없음 또는 GPU 사용 불가
        error_msg = str(exc)

        if (
            "nvrtc" in error_msg.lower()
            or "cuda" in error_msg.lower()
            or ".dll" in error_msg.lower()
        ):
            logger.warning(
                "[GPU 가속] CUDA 런타임 오류 - CuPy가 설치되어 있지만 CUDA가 제대로 설치되지 않았습니다."
            )
            logger.warning(f"[GPU 가속] 오류 상세: {error_msg[:200]}")
            logger.info("[GPU 가속] NumPy CPU 모드로 전환합니다. (GPU 가속 없이 작동)")
            logger.info("[GPU 가속] 팁: 불필요한 CuPy를 제거하려면: pip uninstall cupy")
        else:
            logger.warning(f"[GPU 가속] GPU 초기화 실패: {error_msg[:200]}")

        xp = np
        GPU_ACCEL_AVAILABLE = False
        return False


# NumPy 사용 가능한 경우에만 CuPy 체크 시도
if NUMPY_AVAILABLE:
    _check_and_install_cupy()
else:
    # NumPy not available - GPU acceleration disabled
    pass

from core.api import ApiKeyManager
import config
from voice_profiles import DEFAULT_MULTI_VOICE_PRESETS, VOICE_PROFILES

from managers.queue_manager import QueueManager
from managers.progress_manager import ProgressManager
from managers.voice_manager import VoiceManager
from managers.output_manager import OutputManager
from managers.session_manager import SessionManager
from processors.subtitle_detector import SubtitleDetector
from processors.subtitle_processor import SubtitleProcessor
from processors.tts_processor import TTSProcessor
from processors.video_composer import VideoComposer
from utils.token_cost_calculator import TokenCostCalculator

# Modular handlers for specific concerns
from app.api_handler import APIHandler
from app.batch_handler import BatchHandler
from app.login_handler import LoginHandler

YOUTUBE_API_AVAILABLE = True
INSTAGRAPI_AVAILABLE = True
YOUTUBE_UPLOAD_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def resource_path(relative_path: str) -> str:
    # PyInstaller로 빌드된 exe 인지 확인
    if getattr(sys, "frozen", False):
        # onefile 모드: _MEIPASS 임시 폴더 사용
        if hasattr(sys, "_MEIPASS"):
            meipass_path = os.path.join(sys._MEIPASS, relative_path)
            if os.path.exists(meipass_path):
                return meipass_path
        # onedir 모드: exe 폴더의 _internal 사용
        base_path = os.path.dirname(sys.executable)
        internal_path = os.path.join(base_path, "_internal", relative_path)
        if os.path.exists(internal_path):
            return internal_path
        # fallback: 기존 경로
        return os.path.join(base_path, relative_path)
    else:
        # 개발 중(파이썬 파일로 실행)일 때
        base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)


class VideoAnalyzerGUI:
    def __init__(self, root, login_data=None, preloaded_ocr=None):
        self.root = root
        self.login_data = login_data
        self.preloaded_ocr = preloaded_ocr  # 로딩창에서 미리 초기화된 OCR
        # Expose config module for helper classes (e.g., TTSProcessor)
        self.config = config

        self.root.title(f"쇼핑 숏폼 메이커")

        # Thread-safe UI update queue
        self.msg_queue = queue.Queue()
        self.root.after(100, self.check_queue)

        icon_path = resource_path(os.path.join("resource", "mainTrayIcon.png"))
        # Icon path verified silently
        self._root_icon = tk.PhotoImage(file=icon_path)
        self.root.iconphoto(True, self._root_icon)

        # 창 크기 설정 (고정 레이아웃 사용)
        # Window size settings (using fixed layout)
        self.root.geometry(f"{LAYOUT.WINDOW_WIDTH}x{LAYOUT.WINDOW_HEIGHT}")
        self.root.minsize(LAYOUT.WINDOW_MIN_WIDTH, LAYOUT.WINDOW_MIN_HEIGHT)
        self.root.maxsize(LAYOUT.WINDOW_MAX_WIDTH, LAYOUT.WINDOW_MAX_HEIGHT)
        self.root.resizable(True, True)

        # 창 크기 추적 변수 (고정 레이아웃)
        # Window size tracking (fixed layout)
        self.current_width = LAYOUT.WINDOW_WIDTH
        self.current_height = LAYOUT.WINDOW_HEIGHT
        self.scale_factor = 1.0  # 항상 1.0 유지 (고정 크기)

        # Chrome 브라우저 스타일 색상
        self.bg_color = "#ffffff"
        self.header_bg = "#f8f9fa"
        self.border_color = "#dee2e6"
        self.primary_color = "#1a73e8"
        self.text_color = "#202124"
        self.secondary_text = "#5f6368"
        self.success_color = "#34a853"
        self.warning_color = "#fbbc04"
        self.error_color = "#ea4335"

        self.root.configure(bg=self.bg_color)

        # URL 관련 변수
        self.url_queue = []
        self.url_status = {}
        self.url_status_message = {}  # URL별 상태 메시지 저장
        self.url_timestamps = {}  # URL별 처리 시작 시각 (폴더명 일관성 유지)
        self.url_remarks = {}  # URL별 비고 (제품 요약, 10자 이내)
        self.url_listbox = None
        self.url_entry = None
        self.current_processing_index = -1

        # API 키 저장 파일 경로
        self.api_keys_file = "api_keys_config.json"

        # 토큰 비용 계산기
        self.token_calculator = TokenCostCalculator()

        # 동적 처리 플래그
        self.dynamic_processing = False

        # 변수 초기화 (API 로드 전에 실행)
        self.video_source = tk.StringVar(value="none")
        self.local_file_path = ""
        self.tiktok_douyin_url = ""
        self._temp_downloaded_file = None
        self.source_video = ""

        # TTS 음성 고정 설정
        default_voice = DEFAULT_MULTI_VOICE_PRESETS[0]
        self.selected_tts_voice = tk.StringVar(value=default_voice)
        self.tts_gender = tk.StringVar(value="female")
        self.fixed_tts_voice = default_voice
        self.multi_voice_presets = list(DEFAULT_MULTI_VOICE_PRESETS)
        self.available_tts_voices = list(self.multi_voice_presets)
        self.tts_voice_mode = tk.StringVar(value="multi")
        self.selected_single_voice = tk.StringVar(value=self.available_tts_voices[0])
        self.voice_cycle_index = 0
        self.voice_section_scale = 0.45
        self.last_voice_used = self.available_tts_voices[0]
        self.voice_choice_combo = None
        self.voice_info_label = None
        self.tts_voice_mode.trace_add("write", self.on_voice_mode_change)
        self.selected_single_voice.trace_add("write", self.on_single_voice_change)

        # Sample voice catalog for the redesigned selector
        self.voice_profiles = [profile.copy() for profile in VOICE_PROFILES]
        self.voice_vars: Dict[str, tk.BooleanVar] = {}
        self.voice_sample_paths: Dict[str, str] = {}
        self.max_voice_selection = 10
        self.voice_summary_var = tk.StringVar(value="선택된 음성: 없음")
        self._active_sample_player = None

        # 배치 처리용 변수
        self.url_list = []
        self.batch_processing = False
        self.batch_output_dir = None  # legacy attribute retained for compatibility
        self.url_gap_seconds = 10
        self.current_batch_index = 0
        self.url_list_text = None
        self.batch_processing_lock = threading.Lock()  # 중복 배치 실행 방지
        self.url_status_lock = threading.Lock()  # url_status 접근 동기화
        self.batch_thread = None  # 현재 실행 중인 배치 스레드

        # self.output_folder_path = os.path.join(os.getcwd(), "outputs")
        # os.makedirs(self.output_folder_path, exist_ok=True)

        # ★ 저장된 출력 폴더 경로 불러오기 ★
        try:
            settings = get_settings_manager()
            saved_output_folder = settings.get_output_folder()
            if saved_output_folder and os.path.isdir(saved_output_folder):
                output_path = saved_output_folder
                # Using saved output folder
            else:
                # 저장된 경로가 없거나 유효하지 않으면 바탕화면 사용
                desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                if not os.path.isdir(desktop_path):
                    desktop_path = os.path.join(os.getcwd(), "outputs")
                output_path = desktop_path
                # Using default output folder
        except Exception:
            # 예외 발생 시에도 안전하게 폴백
            output_path = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.isdir(output_path):
                output_path = os.path.join(os.getcwd(), "outputs")

        os.makedirs(output_path, exist_ok=True)
        self.output_folder_path = output_path
        # Output folder configured silently

        self.output_folder_var = tk.StringVar(value=self.output_folder_path)
        self.output_folder_button = None
        self.output_folder_label = None
        self.start_batch_button = None
        self.stop_batch_button = None

        # 결과 저장용 변수
        self.analysis_result = {}
        self.last_chinese_script_lines: List[str] = []
        self.last_chinese_script_text: str = ""
        self.last_chinese_script_digest: Optional[str] = None
        self.center_subtitle_region: Optional[Dict[str, Any]] = None
        self.translation_result = ""
        self.tts_file_path = ""
        self.tts_files = []
        self.final_video_path = ""
        self.final_video_temp_dir = None
        self.generated_videos: List[Dict[str, Any]] = []
        self.korean_subtitle_override = None
        self.korean_subtitle_mode = "default"
        self.cached_video_width: Optional[int] = None
        self.cached_video_height: Optional[int] = None

        # TTS 관련 변수
        self.speaker_voice_mapping = {}
        self.last_tts_segments = []
        self._per_line_tts = []

        self.tts_sync_info = {}
        self.current_task_var = tk.StringVar(value="대기 중")
        self._current_job_header = None
        # 진행상황 관리
        self.progress_states = {
            "download": {"status": "waiting", "progress": 0, "message": None},
            "analysis": {"status": "waiting", "progress": 0, "message": None},
            "ocr_analysis": {"status": "waiting", "progress": 0, "message": None},
            "subtitle": {"status": "waiting", "progress": 0, "message": None},
            "translation": {"status": "waiting", "progress": 0, "message": None},
            "tts": {"status": "waiting", "progress": 0, "message": None},
            "video": {"status": "waiting", "progress": 0, "message": None},
            # 세밀한 싱크 파이프라인 단계
            "tts_audio": {"status": "waiting", "progress": 0, "message": None},
            "audio_merge": {"status": "waiting", "progress": 0, "message": None},
            "audio_analysis": {"status": "waiting", "progress": 0, "message": None},
            "subtitle_overlay": {"status": "waiting", "progress": 0, "message": None},
            "post_tasks": {"status": "waiting", "progress": 0, "message": None},
            "finalize": {"status": "waiting", "progress": 0, "message": None},
        }

        self.stage_messages = {
            "download": [
                "현재 원본 동영상을 찾고 있습니다.",
                "링크 속 숨은 명장면을 뒤지는 중이에요.",
                "다운로드 터널 속에서 영상을 끌어오는 중입니다.",
            ],
            "analysis": [
                "AI가 동영상을 분석하고 있습니다.",
                "씬별 포인트를 캐치하고 있어요.",
                "내용을 샅샅이 뜯어보고 있습니다.",
            ],
            "ocr_analysis": [
                "중국어 자막을 찾고 있습니다.",
                "프레임마다 글자를 탐색 중이에요.",
                "OCR로 자막 위치를 분석하고 있습니다.",
            ],
            "subtitle": [
                "중국어 자막을 분석하고 있습니다.",
                "프레임 속 글자를 한 줄씩 추적하는 중이에요.",
                "자막 위치를 확대경으로 살피고 있습니다.",
            ],
            "translation": [
                "번역과 각색을 하고 있습니다.",
                "한국어 감성으로 문장을 다듬는 중이에요.",
                "의미를 살리며 자연스럽게 고쳐 쓰고 있습니다.",
            ],
            "tts": [
                "목소리를 입히는 중이에요.",
                "톤과 감정을 맞춰 한 줄씩 녹음하고 있어요.",
                "듣기 좋은 보이스를 믹싱 중입니다.",
            ],
            "video": [
                "영상을 최종 인코딩 하고 있습니다.",
                "장면을 이어 붙이며 피날레를 완성 중이에요.",
                "렌더링 엔진이 열심히 팬을 돌리고 있습니다.",
            ],
            "tts_audio": [
                "TTS 음성을 조물조물 빚는 중입니다.",
                "대사를 가장 자연스러운 목소리로 녹음하고 있어요.",
                "보이스 배우가 마이크 앞에서 열연 중입니다.",
            ],
            "audio_merge": [
                "갓 구운 TTS를 영상에 살포시 얹는 중입니다.",
                "오디오와 영상이 한 몸이 되도록 맞붙이고 있어요.",
                "볼륨과 템포를 맞춰 한 컷에 담는 중입니다.",
            ],
            "audio_analysis": [
                "오디오를 세밀하게 들으며 자막 타이밍을 측정 중입니다.",
                "파형 위를 탐정처럼 훑으며 싱크를 계산하고 있어요.",
                "귀로 들은 시간을 숫자로 바꾸는 중입니다.",
            ],
            "subtitle_overlay": [
                "계산한 타이밍으로 자막을 딱 맞춰 붙이고 있습니다.",
                "문장마다 화면에 착 붙도록 자막을 얹는 중이에요.",
                "자막이 화면 위에서 춤출 준비를 하고 있습니다.",
            ],
            "post_tasks": [
                "마지막 다듬기를 하며 군더더기를 정리하고 있어요.",
                "마무리 전 필수 점검 항목을 체크 중입니다.",
                "잔잔바리 작업들을 싹 쓸어 담는 중입니다.",
            ],
            "finalize": [
                "피날레 렌더링으로 결과물을 포장 중입니다.",
                "이제 곧 완성본이 탄생합니다. 조금만 기다려 주세요!",
                "완성본을 반짝이 리본으로 묶는 중입니다.",
            ],
        }
        self._stage_message_cache = {}

        # 세션별 고유 TTS 디렉토리 생성 (안전한 경로 사용)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
        self.base_tts_dir = get_safe_tts_base_dir()
        self.tts_output_dir = os.path.join(
            self.base_tts_dir, f"session_{self.session_id}"
        )
        os.makedirs(self.tts_output_dir, exist_ok=True)
        self.voice_sample_dir = os.path.join(self.base_tts_dir, "voice_samples")
        os.makedirs(self.voice_sample_dir, exist_ok=True)
        # Session TTS directory created silently

        # OCR 리더 초기화 (로딩창에서 미리 초기화된 경우 재사용)
        if self.preloaded_ocr is not None:
            self.ocr_reader = self.preloaded_ocr
            # Preloaded OCR reader used
        else:
            self.ocr_reader = None
            # OCR reader not preloaded - subtitle detection may be limited

        # 비디오 옵션 변수들
        self.mirror_video = tk.BooleanVar(value=False)
        self.add_subtitles = tk.BooleanVar(value=True)
        self.output_quality = tk.StringVar(value="medium")
        self.apply_blur = tk.BooleanVar(value=True)

        # Initialize managers
        self.queue_manager = QueueManager(self)
        self.progress_manager = ProgressManager(self)
        self.voice_manager = VoiceManager(self)
        self.output_manager = OutputManager(self)
        self.session_manager = SessionManager(self)

        # Initialize processors
        self.subtitle_detector = SubtitleDetector(self)
        self.subtitle_processor = SubtitleProcessor(self)
        self.tts_processor = TTSProcessor(self)
        self.video_composer = VideoComposer(self)

        # Initialize handlers for specific concerns
        self.api_handler = APIHandler(self)
        self.batch_handler = BatchHandler(self)
        self.login_handler = LoginHandler(self)

        # UI 구성
        self.setup_ui()

        # 고정 레이아웃 값 초기화
        # Initialize fixed layout values
        self.update_ui_scale()

        # 윈도우 닫기 프로토콜 설정
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_request)

        # 세션 복구 확인 (UI가 준비된 후)
        self.root.after(500, self._check_and_restore_session)

        # 비동기 API 키 로드 및 초기화
        threading.Thread(target=self._async_load_and_init, daemon=True).start()

        # 로그인 상태 감시 시작
        logger.info("[MainApp] Initialization complete. Starting login watch...")
        self._start_login_watch()
        logger.info("[MainApp] Main window ready and event loop running.")

    def check_queue(self):
        """Thread-safe UI update queue worker"""
        try:
            while True:
                task = self.msg_queue.get_nowait()
                task()
        except queue.Empty:
            pass
        self.root.after(100, self.check_queue)

    def _async_load_and_init(self):
        """비동기 API 키 로드 및 초기화"""
        try:
            # Working directory verified silently
            # API 키 로드
            self.load_saved_api_keys()

            # API 매니저 초기화
            self.api_key_manager = ApiKeyManager.APIKeyManager()

            # Gemini 클라이언트 초기화
            self.init_client()
            try:
                self.ensure_voice_samples(force=False)
            except Exception:
                # Voice sample preparation failed silently
                pass

            # API keys loaded and initialized silently
            self.root.after(0, self.refresh_output_folder_display)

        except Exception:
            # Async initialization error handled silently
            pass

    def load_saved_api_keys(self):
        """저장된 API 키 자동 로드 - Delegated to APIHandler"""
        return self.api_handler.load_saved_api_keys()

    def show_api_key_manager(self):
        """API 키 관리 창 - Delegated to APIHandler"""
        return self.api_handler.show_api_key_manager()

    def save_api_keys_from_ui(self, window):
        """UI에서 입력받은 API 키 저장 - Delegated to APIHandler"""
        return self.api_handler.save_api_keys_from_ui(window)

    def clear_all_api_keys(self, window):
        """모든 API 키 입력 필드 초기화 - Delegated to APIHandler"""
        return self.api_handler.clear_all_api_keys(window)

    def save_api_keys_to_file(self):
        """API 키를 파일로 영구 저장 - Delegated to APIHandler"""
        return self.api_handler.save_api_keys_to_file()

    def process_url_input(self, raw_input):
        """URL 입력 텍스트 처리 - 슬래시 포함 버전

        Extracts Douyin and TikTok URLs from input text.
        Uses regex for extraction and APIValidator for validation.
        """
        from utils.validators import validate_url

        if not raw_input or not raw_input.strip():
            return []

        lines = raw_input.strip().split("\n")
        all_urls = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            # v.douyin.com 형태 - 마지막 슬래시 포함!
            douyin_matches = re.findall(
                r"https://v\.douyin\.com/[A-Za-z0-9_\-]+/", line
            )
            all_urls.extend(douyin_matches)

            # vm.tiktok.com 형태
            tiktok_matches = re.findall(
                r"https://vm\.tiktok\.com/[A-Za-z0-9_\-]+/", line
            )
            all_urls.extend(tiktok_matches)

            logger.debug(
                f"[URL 처리] 라인 {line_num}: {len(douyin_matches + tiktok_matches)}개 URL 발견"
            )

        # 중복 제거 및 검증 (슬래시 포함 상태로)
        unique_urls = []
        seen_urls = set()

        for url in all_urls:
            if url not in seen_urls:
                # URL 형식 검증
                if validate_url(url):
                    seen_urls.add(url)
                    unique_urls.append(url)
                else:
                    logger.warning(f"[URL 처리] 잘못된 URL 형식 무시: {url}")

        return unique_urls[:30]  # 최대 30개

    def cleanup_temp_files(self):
        logger.debug("cleanup_temp_files in")
        if hasattr(self, "_temp_downloaded_file") and self._temp_downloaded_file:
            try:
                temp_dir = os.path.dirname(self._temp_downloaded_file)
                if temp_dir and os.path.exists(temp_dir):
                    # 파일이 사용 중일 수 있으므로 잠시 대기
                    time.sleep(2)

                    logger.debug(f"temp_dir : {temp_dir}")
                    # 여러 번 시도
                    for attempt in range(3):
                        try:
                            shutil.rmtree(temp_dir)
                            logger.info(f"[정리] 임시 폴더 삭제: {temp_dir}")
                            break
                        except Exception as e:
                            if attempt < 2:
                                time.sleep(2)  # 2초 더 대기 후 재시도
                            else:
                                # 마지막 시도에서도 실패하면 무시
                                logger.warning(
                                    f"[정리] 임시 파일 삭제 실패 (무시): {str(e)}"
                                )
                                pass
            except Exception as e:
                # 정리 실패는 치명적이지 않으므로 무시
                logger.warning(f"[정리 경고] {str(e)}")
                pass
            finally:
                self._temp_downloaded_file = None

    def init_client(self, use_specific_key=None):
        """Gemini API 클라이언트 초기화"""
        try:
            if not GENAI_SDK_AVAILABLE:
                # Gemini SDK not available - cannot create client
                return False
            if not config.GEMINI_API_KEYS:
                # No API keys registered - skip initialization silently
                return False

            if use_specific_key:
                api_key = use_specific_key
                # Using specified API key
            else:
                api_key = self.api_key_manager.get_available_key()

            # google.genai 클라이언트 생성
            self.genai_client = genai.Client(api_key=api_key)

            # Ensure configured TTS model is available; fall back to the first available TTS model if not.
            try:
                tts_models = []
                for m in self.genai_client.models.list():
                    name = getattr(m, "name", "")
                    if "tts" in name.lower():
                        tts_models.append(name.replace("models/", ""))
                configured_tts = config.GEMINI_TTS_MODEL.replace("models/", "")
                if tts_models and configured_tts not in tts_models:
                    fallback = tts_models[0]
                    logger.warning(
                        f"[API 초기화] 설정된 TTS 모델({configured_tts})을 사용할 수 없어 {fallback}로 대체합니다."
                    )
                    config.GEMINI_TTS_MODEL = fallback
                elif not tts_models:
                    # No available TTS models found - TTS calls may fail
                    pass
            except Exception:
                # TTS model check failed - silently handled
                pass

            logger.info(f"[API 초기화] 완료")
            logger.info(f"- 비디오 분석 모델: {config.GEMINI_VIDEO_MODEL}")
            logger.info(f"- 텍스트 처리 모델: {config.GEMINI_TEXT_MODEL}")
            logger.info(f"- TTS 생성 모델: {config.GEMINI_TTS_MODEL}")

            return True
        except Exception as e:
            logger.error(f"[API 오류] 초기화 실패: {str(e)}")
            return False

    def update_progress_state(self, step, status, progress=None, message=None):
        """진행상황 상태 업데이트"""
        return self.progress_manager.update_progress_state(
            step, status, progress, message
        )

    def update_all_progress_displays(self):
        """모든 탭의 진행상황 표시 업데이트 - 단순화"""
        return self.progress_manager.update_all_progress_displays()

    def reset_progress_states(self):
        """모든 단계 진행상황을 초기화"""
        return self.progress_manager.reset_progress_states()

    def _format_job_source(self, source: str) -> str:
        """사용자에게 보여줄 작업 식별 텍스트를 생성한다."""
        return self.progress_manager._format_job_source(source)

    def get_voice_label(self, voice_id: str) -> str:
        """음성 ID를 한글 이름으로 변환"""
        return self.voice_manager.get_voice_label(voice_id)

    def set_active_voice(
        self,
        voice_id: str,
        voice_index: Optional[int] = None,
        voice_total: Optional[int] = None,
    ) -> None:
        """현재 처리 중인 음성 정보를 진행 카드에 반영"""
        return self.progress_manager.set_active_voice(
            voice_id, voice_index, voice_total
        )

    def set_active_job(
        self, source: str, index: Optional[int] = None, total: Optional[int] = None
    ) -> None:
        """현재 처리 중인 작업 정보를 진행 카드에 반영한다."""
        return self.progress_manager.set_active_job(source, index, total)

    def get_stage_message(self, step, status):
        """단계별 UX 메시지 생성"""
        return self.progress_manager.get_stage_message(step, status)

    def refresh_stage_indicator(self, step, status, progress=None):
        """진행현황 카드 단계 라벨/게이지 업데이트"""
        return self.progress_manager.refresh_stage_indicator(step, status, progress)

    def get_status_color(self, status):
        """상태에 따른 색상 반환"""
        return self.progress_manager.get_status_color(status)

    def get_status_text(self, status):
        """상태에 따른 텍스트 반환"""
        return self.progress_manager.get_status_text(status)

    def setup_ui(self):
        """전체 UI 구성 - 사이드바 기반 레이아웃"""
        # ===== 테마 관리자 초기화 =====
        self.theme_manager = get_theme_manager()

        # 저장된 테마 설정 로드
        try:
            settings = get_settings_manager()
            saved_theme = settings.get_theme()
            if saved_theme in ("light", "dark"):
                self.theme_manager.set_theme(saved_theme)
                # Saved theme loaded silently
        except Exception:
            # Theme loading failed silently
            pass

        self._apply_theme_colors()

        # 테마 변경 옵저버 등록
        self.theme_manager.register_observer(self._on_theme_changed)

        self.root.configure(bg=self.bg_color)

        # Style configuration - Coupang Theme
        self._configure_ttk_styles()

        # ===== 헤더 영역 (고정 높이) =====
        # Header area (fixed height)
        self._header_frame = tk.Frame(
            self.root, bg=self.header_bg, height=LAYOUT.HEADER_HEIGHT
        )
        self._header_frame.pack(fill=tk.X)
        self._header_frame.pack_propagate(False)

        # 로고/타이틀
        self._title_frame = tk.Frame(self._header_frame, bg=self.header_bg)
        self._title_frame.pack(side=tk.LEFT, padx=20, pady=10)

        self._main_title_label = tk.Label(
            self._title_frame,
            text="쇼핑 숏폼 메이커",
            font=("맑은 고딕", 16, "bold"),
            bg=self.header_bg,
            fg=self.primary_color,
        )
        self._main_title_label.pack(side=tk.LEFT)

        self._sub_title_label = tk.Label(
            self._title_frame,
            text="AI 기반 숏폼 자동 제작",
            font=("맑은 고딕", 10),
            bg=self.header_bg,
            fg=self.secondary_text,
        )
        self._sub_title_label.pack(side=tk.LEFT, padx=(12, 0))

        # 우측: 구독 정보 + 설정 버튼 + 테마 토글
        self._right_frame = tk.Frame(self._header_frame, bg=self.header_bg)
        self._right_frame.pack(side=tk.RIGHT, padx=20, pady=10)

        # 테마 토글 (제거됨 - 라이트 모드 고정)
        # self.theme_toggle = ThemeToggle(
        #     self._right_frame,
        #     theme_manager=self.theme_manager,
        #     on_toggle=self._toggle_theme,
        # )
        # self.theme_toggle.pack(side=tk.RIGHT)

        # 설정 버튼 (톱니바퀴)
        self.settings_button = SettingsButton(
            self._right_frame,
            theme_manager=self.theme_manager,
            on_click=self._open_settings_modal,
        )
        self.settings_button.pack(side=tk.RIGHT, padx=(0, 12))

        # 구독 상태 위젯
        from ui.components.subscription_status import SubscriptionStatusWidget
        from ui.components.subscription_popup import show_subscription_prompt

        self.subscription_widget = SubscriptionStatusWidget(
            self._right_frame,
            on_request_subscription=self._on_request_subscription,
            theme_manager=self.theme_manager,
        )
        self.subscription_widget.pack(side=tk.RIGHT, padx=(0, 20))

        # 구독 정보 업데이트
        self._update_subscription_info()

        # 헤더 하단 구분선
        self._header_divider = tk.Frame(self.root, bg=self.border_color, height=1)
        self._header_divider.pack(fill=tk.X)

        # ===== 사이드바 컨테이너 (고정 너비) =====
        # Sidebar container (fixed width)
        self.sidebar_container = SidebarContainer(
            self.root,
            theme_manager=self.theme_manager,
            sidebar_width=LAYOUT.SIDEBAR_WIDTH,
            gui=self,
        )
        self.sidebar_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # 메뉴 추가: URL 입력 (1단계), 스타일 (2단계), 작업 (3단계)
        self.url_panel = URLContentPanel(
            self.sidebar_container.content_frame, self, theme_manager=self.theme_manager
        )
        self.sidebar_container.add_menu_item(
            "url", "URL 입력", self.url_panel, step_number=1, icon=""
        )

        self.style_tab = StyleTab(
            self.sidebar_container.content_frame, self, theme_manager=self.theme_manager
        )
        self.sidebar_container.add_menu_item(
            "style", "스타일", self.style_tab, step_number=2, icon=""
        )

        self.queue_tab = QueueTab(
            self.sidebar_container.content_frame, self, theme_manager=self.theme_manager
        )
        self.sidebar_container.add_menu_item(
            "queue", "작업", self.queue_tab, step_number=3, icon=""
        )

        # 기본 메뉴 선택 (URL 입력이 첫 단계)
        self.sidebar_container.select_menu("url")

        # 호환성을 위한 별칭
        self.settings_tab = self.url_panel
        self.tab_container = self.sidebar_container  # 레거시 호환

        # ===== 상태 표시줄 =====
        self.status_bar = StatusBar(self.root, self)

        # 더미 위젯 (호환성)
        self.create_dummy_widgets()

        # 기존 패널에서 사용하던 위젯 참조 설정 (호환성)
        self._setup_legacy_widget_references()

        # UI 초기화
        self.update_analyze_button()
        self.refresh_output_folder_display()

        # 반응형 창 크기 이벤트 바인딩
        self.root.bind("<Configure>", self.on_window_resize)

        # 스크린샷 캡처 단축키 (Ctrl+Shift+S)
        self.root.bind("<Control-Shift-s>", self._capture_all_pages)
        self.root.bind("<Control-Shift-S>", self._capture_all_pages)

        # ===== 첫 실행 시 튜토리얼 표시 =====
        self._show_tutorial_if_first_run()

    def _show_tutorial_if_first_run(self):
        """첫 실행 시 튜토리얼 오버레이 표시"""
        try:
            settings = get_settings_manager()
            if settings.is_first_run():
                # 약간의 지연 후 튜토리얼 표시 (UI가 완전히 로드된 후)
                self.root.after(500, lambda: self._show_tutorial(settings))
        except Exception as e:
            logger.warning(f"튜토리얼 표시 확인 실패: {e}")

    def _show_tutorial(self, settings=None):
        """튜토리얼 오버레이 표시"""

        def on_tutorial_complete():
            if settings:
                settings.mark_tutorial_completed()
            logger.info("튜토리얼 완료")
            self._tutorial_overlay = None  # 참조 해제

        # PyQt5 위젯 참조 유지 (가비지 컬렉션 방지)
        self._tutorial_overlay = TutorialOverlay(
            self.root,
            on_complete=on_tutorial_complete,
            theme_manager=self.theme_manager,
        )
        self._tutorial_overlay.show()

    def show_tutorial(self):
        """수동으로 튜토리얼 표시 (설정에서 호출 가능)"""
        self._show_tutorial()

    def _open_settings_modal(self):
        """설정 모달 열기"""
        SettingsModal(self.root, self, theme_manager=self.theme_manager)

    def _apply_theme_colors(self):
        """테마 관리자에서 색상 가져와 적용"""
        tm = self.theme_manager

        # 기존 코드와의 호환성을 위해 인스턴스 변수로 색상 설정
        self.bg_color = tm.get_color("bg_main")
        self.header_bg = tm.get_color("bg_header")
        self.card_bg = tm.get_color("bg_card")
        self.border_color = tm.get_color("border_light")
        self.primary_color = tm.get_color("primary")
        self.accent_color = tm.get_color("primary_hover")
        self.text_color = tm.get_color("text_primary")
        self.secondary_text = tm.get_color("text_secondary")
        self.success_color = tm.get_color("success")
        self.warning_color = tm.get_color("warning")
        self.error_color = tm.get_color("error")

        # 추가 컬러 (버튼 및 UI 요소용)
        self.button_hover = tm.get_color("primary_hover")
        self.light_red = tm.get_color("primary_light")
        self.light_gray = tm.get_color("bg_secondary")
        self.highlight_color = tm.get_color("bg_selected")

        # 둥근 모서리 설정
        self.border_radius = 8

    def _configure_ttk_styles(self):
        """ttk 스타일 설정"""
        style = ttk.Style()

        # 'clam' 테마 사용 - Windows에서 배경색 등 커스터마이징 가능
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass  # 테마 사용 불가 시 기본 테마 유지

        style.configure(
            "Task.Horizontal.TProgressbar",
            troughcolor=self.theme_manager.get_color("progress_bg"),
            bordercolor=self.theme_manager.get_color("progress_bg"),
            background=self.primary_color,
            lightcolor=self.primary_color,
            darkcolor=self.accent_color,
        )
        style.layout(
            "Task.Horizontal.TProgressbar",
            [
                (
                    "Horizontal.Progressbar.trough",
                    {
                        "children": [
                            (
                                "Horizontal.Progressbar.pbar",
                                {"side": "left", "sticky": "ns"},
                            )
                        ],
                        "sticky": "nswe",
                    },
                )
            ],
        )

        # 스크롤바 스타일 설정
        style.configure(
            "Queue.Vertical.TScrollbar",
            background=self.theme_manager.get_color("scrollbar_thumb"),
            troughcolor=self.theme_manager.get_color("scrollbar_bg"),
            borderwidth=0,
            relief=tk.FLAT,
            arrowsize=12,
        )
        style.map(
            "Queue.Vertical.TScrollbar",
            background=[
                ("active", self.primary_color),
                ("pressed", self.accent_color),
                ("!active", self.theme_manager.get_color("scrollbar_thumb")),
            ],
        )

        # Treeview 스타일
        style.configure(
            "Queue.Treeview",
            font=("맑은 고딕", 9),
            rowheight=32,
            background=self.card_bg,
            fieldbackground=self.card_bg,
            foreground=self.text_color,
            borderwidth=0,
            relief=tk.FLAT,
        )
        style.configure(
            "Queue.Treeview.Heading",
            font=("맑은 고딕", 9, "bold"),
            background=self.theme_manager.get_color("bg_secondary"),
            foreground=self.text_color,
            relief=tk.FLAT,
            borderwidth=0,
        )
        style.map(
            "Queue.Treeview",
            background=[("selected", self.light_red)],
            foreground=[("selected", self.text_color)],
        )
        style.map(
            "Queue.Treeview.Heading",
            background=[("active", self.theme_manager.get_color("bg_hover"))],
            relief=[("active", tk.FLAT)],
        )

        # 테마 스크롤바 스타일
        style.configure(
            "Themed.Vertical.TScrollbar",
            background=self.theme_manager.get_color("scrollbar_thumb"),
            troughcolor=self.theme_manager.get_color("scrollbar_bg"),
            borderwidth=0,
            relief=tk.FLAT,
            arrowsize=12,
        )

    def _setup_legacy_widget_references(self):
        """기존 패널에서 사용하던 위젯 참조 설정 (호환성)"""
        # URLContentPanel에서 url_entry 가져오기
        if hasattr(self, "url_panel") and hasattr(self.url_panel, "url_entry"):
            self.url_entry = self.url_panel.url_entry

        # QueueTab에서 queue_panel과 progress_panel 가져오기
        if hasattr(self, "queue_tab") and hasattr(self.queue_tab, "queue_panel"):
            # queue_panel에 있는 위젯들은 QueuePanel 생성 시 self.gui.xxx로 설정됨
            pass

        # progress_panel은 이제 사이드바에서 표시됨 (queue_tab에서 제거됨)
        # 호환성을 위해 None으로 설정
        self.progress_panel = None

    def _toggle_theme(self, new_theme: str = None):
        """테마 토글 콜백 (ThemeToggle에서 호출됨)"""
        # ThemeToggle이 이미 toggle_theme()을 호출했으므로
        # 여기서는 추가 작업 불필요 (옵저버가 _on_theme_changed 호출)
        pass

    def _on_request_subscription(self, message: str = ""):
        """구독 신청 버튼 클릭 처리"""
        if not hasattr(self, "login_data") or not self.login_data:
            return

        user_data = self.login_data.get("data", {}).get("data", {})
        user_id = user_data.get("id")

        if not user_id:
            return

        # 권한 검증: 체험판 사용자만 구독 신청 가능
        work_count = user_data.get("work_count", -1)
        user_type = user_data.get("user_type", "")

        # 체험판 사용자인지 확인 (백엔드와 동일한 로직)
        is_trial = user_type == "trial" or (work_count > 0 and work_count != -1)

        if not is_trial:
            # 체험판 사용자가 아니면 메시지 표시
            self._show_error_message(
                "구독 신청 불가",
                "구독 신청은 체험판 사용자만 가능합니다.\n\n"
                "이미 구독 중이거나 무제한 사용자입니다.",
            )
            return

        # 이미 구독 신청 대기 중인지 확인
        if hasattr(self, "subscription_widget"):
            widget_data = self.subscription_widget.get_current_status()
            if widget_data.get("has_pending_request", False):
                self._show_error_message(
                    "구독 신청 대기 중",
                    "이미 구독 신청이 접수되어 승인 대기 중입니다.\n\n"
                    "관리자의 승인을 기다려주세요.",
                )
                return

        # 메시지가 제공되지 않았으면 다이얼로그 표시
        if not message:
            # 구독 신청 다이얼로그 표시
            from ui.components.subscription_popup import show_subscription_prompt

            work_used = user_data.get("work_used", 0)

            def on_submit(msg: str):
                self._submit_subscription_request(user_id, msg)

            # 구독 안내 팝업 표시
            show_subscription_prompt(
                self.root, work_count, work_used, on_submit, self.theme_manager
            )
        else:
            # 메시지가 제공되었으면 직접 요청 제출
            self._submit_subscription_request(user_id, message)

    def _submit_subscription_request(self, user_id: str, message: str):
        """구독 신청 API 호출"""
        from caller import rest
        import threading

        def submit_request():
            result = rest.safe_subscription_request(user_id, message)
            if result.get("success"):
                # 성공 시 상태 갱신
                self.root.after(0, lambda: self._refresh_subscription_status())
                # 체험판 팝업 플래그 리셋 (구독 신청 시)
                if hasattr(self, "_trial_exhaustion_shown"):
                    self._trial_exhaustion_shown = False
            else:
                # 실패 시 메시지 표시
                error_msg = result.get("message", "구독 신청에 실패했습니다.")
                self.root.after(
                    0, lambda: self._show_error_message("구독 신청 실패", error_msg)
                )

        threading.Thread(target=submit_request, daemon=True).start()

    def _show_error_message(self, title: str, message: str):
        """에러 메시지 표시"""
        import tkinter.messagebox as messagebox

        messagebox.showerror(title, message)

    def _refresh_subscription_status(self):
        """구독 상태 새로고침"""
        if not hasattr(self, "login_data") or not self.login_data:
            return

        user_data = self.login_data.get("data", {}).get("data", {})
        user_id = user_data.get("id")

        if not user_id:
            return

        # 백그라운드에서 구독 상태 조회
        from caller import rest
        import threading

        def fetch_status():
            result = rest.get_subscription_status_with_consistency(user_id)
            if result.get("success"):
                # 작업 횟수가 증가했는지 확인 (체험판 팝업 플래그 리셋)
                current_work_used = result.get("work_used", 0)
                if hasattr(self, "_last_work_used"):
                    if current_work_used > self._last_work_used:
                        # 작업 횟수가 증가했으면 팝업 플래그 리셋
                        if hasattr(self, "_trial_exhaustion_shown"):
                            self._trial_exhaustion_shown = False
                self._last_work_used = current_work_used

                # 성공 시 UI 업데이트 (Thread-safe)
                self.msg_queue.put(lambda: self._update_subscription_widget(result))
            # 실패 시 무시 (기존 데이터 유지)

        threading.Thread(target=fetch_status, daemon=True).start()

    def _update_subscription_widget(self, status_data: dict):
        """구독 상태 위젯 업데이트"""
        if not hasattr(self, "subscription_widget"):
            return

        self.subscription_widget.update_status(
            is_trial=status_data.get("is_trial", True),
            work_count=status_data.get("work_count", 3),
            work_used=status_data.get("work_used", 0),
            can_work=status_data.get("can_work", True),
            has_pending_request=status_data.get("has_pending_request", False),
        )

        # 체험판 소진 시 구독 안내 팝업 표시
        self._check_trial_exhaustion(status_data)

    def _check_trial_exhaustion(self, status_data: dict):
        """체험판 소진 여부 확인 및 팝업 표시"""
        is_trial = status_data.get("is_trial", True)
        work_count = status_data.get("work_count", 3)
        work_used = status_data.get("work_used", 0)
        can_work = status_data.get("can_work", True)
        has_pending_request = status_data.get("has_pending_request", False)

        # 체험판 사용자이고 작업 횟수를 모두 사용했으며, 구독 신청 대기 중이 아닐 때
        if (
            is_trial
            and work_count > 0
            and work_used >= work_count
            and not can_work
            and not has_pending_request
        ):
            # 이미 팝업이 표시되었는지 확인 (중복 표시 방지)
            if not hasattr(self, "_trial_exhaustion_shown"):
                self._trial_exhaustion_shown = False

            if not self._trial_exhaustion_shown:
                self._trial_exhaustion_shown = True

                # 잠시 후 팝업 표시 (UI 업데이트 완료 후)
                self.root.after(
                    1000,
                    lambda: self._show_trial_exhaustion_popup(work_count, work_used),
                )

    def _show_trial_exhaustion_popup(self, work_count: int, work_used: int):
        """체험판 소진 시 구독 안내 팝업 표시"""
        from ui.components.subscription_popup import show_subscription_prompt

        def on_submit(message: str):
            """구독 신청 콜백"""
            self._on_request_subscription(message)

        # 구독 안내 팝업 표시
        show_subscription_prompt(
            self.root, work_count, work_used, on_submit, self.theme_manager
        )

    def _update_subscription_info(self):
        """구독 정보 업데이트 (기존 호환성 유지)"""
        from datetime import datetime

        # SubscriptionStatusWidget이 있으면 업데이트
        if hasattr(self, "subscription_widget"):
            try:
                # login_data에서 구독 정보 추출
                user_data = {}
                if self.login_data:
                    user_data = self.login_data.get("data", {}).get("data", {})

                work_count = user_data.get("work_count", -1)
                work_used = user_data.get("work_used", 0)
                user_type = user_data.get("user_type", "")

                # 백엔드와 동일한 is_trial 계산 로직
                # user_type이 "trial"이거나 work_count > 0이고 work_count != -1이면 체험판
                is_trial = user_type == "trial" or (work_count > 0 and work_count != -1)
                remaining = -1 if work_count == -1 else max(0, work_count - work_used)
                can_work = work_count == -1 or remaining > 0

                # 기본값으로 위젯 업데이트 (실제 상태는 _refresh_subscription_status에서 가져옴)
                self.subscription_widget.update_status(
                    is_trial=is_trial,
                    work_count=work_count,
                    work_used=work_used,
                    can_work=can_work,
                    has_pending_request=False,  # API 호출 후 업데이트
                )

                # 백그라운드에서 실제 상태 조회
                self._refresh_subscription_status()

            except Exception as e:
                print(f"구독 정보 업데이트 오류: {e}")

        # 기존 _sub_info_labels 업데이트 (호환성)
        if hasattr(self, "_sub_info_labels") and self._sub_info_labels:
            try:
                # login_data에서 구독 정보 추출
                user_data = {}
                if self.login_data:
                    user_data = self.login_data.get("data", {}).get("data", {})

                # 최근 로그인 (현재 컴퓨터 시간 기준)
                now = datetime.now()
                login_str = now.strftime("%Y/%m/%d %H:%M")
                self._sub_info_labels["login"].config(text=f"최근 로그인: {login_str}")

                # 구독 만료일
                expires_at = user_data.get("subscription_expires_at", "")
                if expires_at:
                    try:
                        exp_dt = datetime.fromisoformat(
                            expires_at.replace("Z", "+00:00")
                        )
                        now = (
                            datetime.now(exp_dt.tzinfo)
                            if exp_dt.tzinfo
                            else datetime.now()
                        )
                        days_left = (exp_dt - now).days
                        if days_left < 0:
                            expires_str = "만료됨"
                            color = "#e31639"
                        elif days_left <= 7:
                            expires_str = f"{days_left}일"
                            color = "#ffc107"
                        else:
                            expires_str = f"{days_left}일"
                            color = self.secondary_text
                        self._sub_info_labels["expires"].config(
                            text=f"구독: {expires_str}", fg=color
                        )
                    except:
                        self._sub_info_labels["expires"].config(text="구독: -")
                else:
                    self._sub_info_labels["expires"].config(text="구독: -")

                # 남은 작업 횟수
                work_count = user_data.get("work_count", -1)
                work_used = user_data.get("work_used", 0)
                if work_count == -1:
                    count_str = "무제한"
                    color = "#00c853"
                else:
                    remaining = max(0, work_count - work_used)
                    count_str = f"{remaining}회"
                    color = "#ffc107" if remaining <= 10 else self.secondary_text
                self._sub_info_labels["count"].config(
                    text=f"횟수: {count_str}", fg=color
                )

            except Exception as e:
                logger.debug(f"구독 정보 업데이트 실패: {e}")

    def _on_theme_changed(self, new_theme: str):
        """테마 변경 시 호출"""
        self._apply_theme_colors()
        self._configure_ttk_styles()
        self.root.configure(bg=self.bg_color)

        # 헤더 영역 테마 적용
        self._update_header_theme()

        # 사이드바 컨테이너에 테마 적용
        if hasattr(self, "sidebar_container"):
            self.sidebar_container.apply_theme()

        # 패널들에 테마 적용
        if hasattr(self, "url_panel"):
            self.url_panel.apply_theme()
        if hasattr(self, "style_tab"):
            self.style_tab.apply_theme()
        if hasattr(self, "queue_tab"):
            self.queue_tab.apply_theme()

        # 설정 버튼에 테마 적용
        if hasattr(self, "settings_button"):
            self.settings_button.apply_theme()

        # 테마 토글에 테마 적용
        if hasattr(self, "theme_toggle"):
            self.theme_toggle.apply_theme()

        # 상태 바에 테마 적용
        if hasattr(self, "status_bar") and self.status_bar is not None:
            self.status_bar.apply_theme()

        # 테마 설정 저장
        try:
            settings = get_settings_manager()
            settings.set_theme(new_theme)
        except Exception as e:
            logger.error(f"[테마] 설정 저장 실패: {e}")

    def _update_header_theme(self):
        """헤더 영역 테마 업데이트"""
        try:
            # 헤더 프레임 배경색 업데이트
            if hasattr(self, "_header_frame"):
                self._header_frame.configure(bg=self.header_bg)

            if hasattr(self, "_title_frame"):
                self._title_frame.configure(bg=self.header_bg)

            if hasattr(self, "_right_frame"):
                self._right_frame.configure(bg=self.header_bg)

            # 타이틀 레이블 색상 업데이트
            if hasattr(self, "_main_title_label"):
                self._main_title_label.configure(
                    bg=self.header_bg, fg=self.primary_color
                )

            if hasattr(self, "_sub_title_label"):
                self._sub_title_label.configure(
                    bg=self.header_bg, fg=self.secondary_text
                )

            # 구독 정보 프레임 테마 업데이트
            if hasattr(self, "_subscription_frame"):
                self._subscription_frame.configure(bg=self.header_bg)
                for child in self._subscription_frame.winfo_children():
                    child.configure(bg=self.header_bg)
                # 색상 정보 재설정
                self._update_subscription_info()

            # 헤더 하단 구분선 색상 업데이트
            if hasattr(self, "_header_divider"):
                self._header_divider.configure(bg=self.border_color)

        except Exception as e:
            logger.error(f"[테마] 헤더 업데이트 실패: {e}")

    def _capture_all_pages(self, _event=None):
        """
        모든 페이지 스크린샷 캡처 (Ctrl+Shift+S)
        Capture screenshots of all pages
        """
        try:
            from utils.page_capture import capture_all_app_pages
            from ui.components.custom_dialog import show_info
            import os

            self.update_status("스크린샷 캡처 중...")
            self.root.update()

            # 모든 페이지 캡처
            results = capture_all_app_pages(self, include_themes=True)

            # 결과 표시
            show_info(
                self.root,
                "캡처 완료",
                f"총 {results['total']}개의 스크린샷이 저장되었습니다.\n\n"
                f"저장 위치:\n{results['directory']}",
            )

            # 폴더 열기 (Windows)
            if sys.platform == "win32":
                os.startfile(results["directory"])

            self.update_status("스크린샷 캡처 완료")

        except ImportError as e:
            logger.error(f"캡처 모듈 로드 실패: {e}")
            self.update_status("캡처 실패: Pillow가 필요합니다")
        except Exception as e:
            logger.error(f"스크린샷 캡처 실패: {e}")
            self.update_status(f"캡처 실패: {e}")

    def on_window_resize(self, event):
        """
        창 크기 변경 이벤트 핸들러
        Window resize event handler

        고정 레이아웃 모드: UI 요소 크기는 변경하지 않고 창 크기만 추적
        Fixed layout mode: Track window size without changing UI element sizes
        """
        # 루트 윈도우의 크기 변경만 처리
        if event.widget != self.root:
            return

        new_width = event.width
        new_height = event.height

        # 크기가 실제로 변경되었을 때만 처리 (최적화)
        if (
            abs(new_width - self.current_width) < 5
            and abs(new_height - self.current_height) < 5
        ):
            return

        self.current_width = new_width
        self.current_height = new_height

        # 고정 레이아웃: 스케일 팩터는 항상 1.0 유지
        # Fixed layout: Keep scale factor at 1.0
        self.scale_factor = 1.0

    def update_ui_scale(self):
        """
        UI 스케일 설정 (고정 크기)
        UI scale settings (fixed sizes)

        모든 해상도에서 동일한 크기를 유지하기 위해 고정 값 사용
        Using fixed values to maintain consistent sizes across all resolutions
        """
        try:
            # 음성 선택 섹션 - 고정 비율
            # Voice section - fixed ratio
            if hasattr(self, "voice_section_scale"):
                self.voice_section_scale = 0.45

            # 폰트 크기 - 고정 (동적 스케일링 없음)
            # Font sizes - fixed (no dynamic scaling)
            self.scaled_fonts = {
                "title": 18,
                "subtitle": 11,
                "normal": 10,
                "small": 9,
                "tiny": 8,
            }

            # 패딩 - 고정
            # Padding - fixed
            self.scaled_padding = 18

        except Exception as e:
            logger.error(f"[고정레이아웃] UI 설정 오류: {e}")

    def create_header(self, parent):
        """Create header (now handled by HeaderPanel)"""
        return HeaderPanel(parent, self)

    def create_url_input_section(self, parent):
        """Create URL input section (now handled by URLInputPanel)"""
        return URLInputPanel(parent, self)

    def create_voice_selection_section(self, parent):
        """Create voice selection section (now handled by VoicePanel)"""
        return VoicePanel(parent, self)

    def get_voice_profile(self, voice_id: str) -> Optional[Dict[str, Any]]:
        return self.voice_manager.get_voice_profile(voice_id)

    def on_voice_card_clicked(self, voice_id: str):
        """음성 카드 클릭 시 토글 처리"""
        return self.voice_manager.on_voice_card_clicked(voice_id)

    def on_voice_checkbox_toggled(self, voice_id: str):
        """체크박스 토글 (하위 호환성을 위해 유지)"""
        return self.voice_manager.on_voice_checkbox_toggled(voice_id)

    def on_voice_card_hover(self, voice_id: str, is_hovering: bool):
        """마우스 호버 시 카드 스타일 변경"""
        return self.voice_manager.on_voice_card_hover(voice_id, is_hovering)

    def update_voice_card_styles(self):
        """선택 상태에 따라 카드 스타일 업데이트"""
        return self.voice_manager.update_voice_card_styles()

    def update_voice_summary(self):
        return self.voice_manager.update_voice_summary()

    def play_voice_sample(self, voice_id: str):
        return self.voice_manager.play_voice_sample(voice_id)

    def ensure_voice_samples(self, force: bool = False) -> bool:
        """Ensure each voice has a playable preview sample produced by Gemini."""
        return self.voice_manager.ensure_voice_samples(force)

    def _generate_tts_sample(
        self, profile: Dict[str, Any], dest_path: str, duration: float = 3.0
    ) -> bool:
        """Use Gemini TTS to create a trimmed preview sample if possible."""
        return self.voice_manager._generate_tts_sample(profile, dest_path, duration)

    def _is_api_key_error(self, exc: Exception) -> bool:
        return self.voice_manager._is_api_key_error(exc)

    def _write_trimmed_sample(
        self, dest_path: str, audio_data: Any, duration: float
    ) -> None:
        """Persist audio data, trimming or padding to the target duration."""
        return self.voice_manager._write_trimmed_sample(dest_path, audio_data, duration)

    def _notify_api_missing(self) -> None:
        """Notify user that Gemini API configuration is required."""
        return self.voice_manager._notify_api_missing()

    def create_url_queue_section(self, parent):
        """Create URL queue section (now handled by QueuePanel)"""
        return QueuePanel(parent, self)

    def create_progress_section(self, parent):
        """Create progress section (now handled by ProgressPanel)"""
        return ProgressPanel(parent, self)

    def remove_selected_url(self):
        """선택된 URL을 큐에서 제거"""
        return self.queue_manager.remove_selected_url()

    def clear_url_queue(self):
        """큐를 초기화 (진행 중 항목 제외)"""
        return self.queue_manager.clear_url_queue()

    def clear_waiting_only(self):
        """대기 상태 URL만 제거"""
        return self.queue_manager.clear_waiting_only()

    def update_url_listbox(self):
        """URL 리스트를 현재 상태에 맞게 갱신"""
        return self.queue_manager.update_url_listbox()

    def update_queue_count(self):
        """Queue 상태 숫자 집계"""
        return self.queue_manager.update_queue_count()

    def extract_urls_from_text(self, text: str) -> List[str]:
        return self.queue_manager.extract_urls_from_text(text)

    def add_urls_to_queue(self, urls: List[str]) -> int:
        return self.queue_manager.add_urls_to_queue(urls)

    def add_url_from_entry(self, event=None):
        return self.queue_manager.add_url_from_entry(event)

    def paste_and_extract(self, event=None):
        return self.queue_manager.paste_and_extract(event)

    def add_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.info(f"[{timestamp}] {message}")

    def _build_script_lines(
        self, script_entries: Optional[Iterable[Dict[str, Any]]]
    ) -> List[str]:
        lines: List[str] = []
        if not script_entries:
            return lines

        for entry in script_entries:
            if not isinstance(entry, dict):
                continue
            timestamp = str(entry.get("timestamp", "00:00")).strip() or "00:00"
            speaker = str(entry.get("speaker", "") or "").strip() or "발화자"
            text = str(entry.get("text", "") or "").strip()
            if not text:
                continue
            tone = str(entry.get("tone_marker", "") or "").strip()
            head = f"[{timestamp}] [{speaker}]"
            payload = f"{tone} {text}".strip() if tone else text
            line = f"{head} {payload}".strip()
            lines.append(line)

        return lines

    def record_analysis_script(
        self, script_entries: Optional[Iterable[Dict[str, Any]]]
    ) -> None:
        lines = self._build_script_lines(script_entries)
        self.last_chinese_script_lines = lines
        if not lines:
            self.last_chinese_script_text = ""
            self.last_chinese_script_digest = None
            self.add_log("[중국어 분석] 분석된 원문이 비어 있습니다.")
            return

        serialized = "\n".join(lines)
        self.last_chinese_script_text = serialized
        digest = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
        self.last_chinese_script_digest = digest
        self.add_log(f"[중국어 분석] 원문 {len(lines)}줄 확보 (digest {digest[:10]})")
        for line in lines:
            self.add_log(f"[중국어 원문] {line}")

    def verify_translation_source(
        self, script_entries: Optional[Iterable[Dict[str, Any]]]
    ) -> bool:
        lines = self._build_script_lines(script_entries)
        if not lines:
            self.add_log("[번역 검증] 번역 대상 원문이 비어 있어 확인하지 못했습니다.")
            return False

        serialized = "\n".join(lines)
        digest = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
        if not self.last_chinese_script_digest:
            self.add_log("[번역 검증] 이전 분석 기록이 없어 비교하지 못했습니다.")
            return False

        if digest != self.last_chinese_script_digest:
            self.add_log("[번역 검증] 분석 원문과 다른 콘텐츠가 감지되었습니다.")
            self.add_log(
                f"[번역 검증] 기존 digest {self.last_chinese_script_digest[:10]}, 현재 {digest[:10]}"
            )
            return False

        self.add_log(f"[번역 검증] 원문 일치 확인 (digest {digest[:10]})")
        return True

    def _compute_centered_subtitle_region(
        self, subtitle_positions: Optional[Iterable[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        return self.subtitle_processor._compute_centered_subtitle_region(
            subtitle_positions
        )

    def prepare_centered_subtitle_layout(
        self, subtitle_positions: Optional[Iterable[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        return self.subtitle_processor.prepare_centered_subtitle_layout(
            subtitle_positions
        )

    def create_status_bar(self):
        """Create status bar (now handled by StatusBar)"""
        return StatusBar(self.root, self)

    def create_dummy_widgets(self):
        """호환성을 위한 더미 위젯들"""
        self.script_progress = {
            "progress_bar": ttk.Progressbar(self.root),
            "status_label": tk.Label(self.root, text=""),
        }
        self.translation_progress = {
            "progress_bar": ttk.Progressbar(self.root),
            "status_label": tk.Label(self.root, text=""),
        }
        self.tts_progress = {
            "progress_bar": ttk.Progressbar(self.root),
            "status_label": tk.Label(self.root, text=""),
        }

        # 더미 프레임 생성
        dummy_frame = tk.Frame(self.root)

        self.script_text = scrolledtext.ScrolledText(dummy_frame)
        self.translation_text = scrolledtext.ScrolledText(dummy_frame)
        self.tts_result_text = scrolledtext.ScrolledText(dummy_frame)
        self.tts_status_label = tk.Label(dummy_frame, text="")
        self.create_final_video_button = tk.Button(
            dummy_frame, text="", state=tk.DISABLED
        )
        self.save_path_label = tk.Label(dummy_frame, text="")

    def update_analyze_button(self):
        """
        분석 버튼 상태 업데이트.

        Note: 현재 UI 구조에서는 analyze_button이 QueueTab에서 관리되므로
        이 메서드는 호환성을 위해 유지됩니다. 실제 버튼 상태 업데이트는
        QueueTab.update_start_button_state()에서 처리됩니다.
        """
        # analyze_button은 queue_tab에서 관리됨 - 호환성 유지용 스텁
        pass

    def update_step_progress(self, step, value):
        """단계 진행률 갱신"""
        return self.progress_manager.update_step_progress(step, value)

    def update_script_progress(self):
        """대본 탭 진행상황 업데이트"""
        return self.progress_manager.update_script_progress()

    def update_translation_progress(self):
        """번역 탭 진행상황 업데이트"""
        return self.progress_manager.update_translation_progress()

    def update_tts_progress(self):
        """TTS 탭 진행상황 업데이트"""
        return self.progress_manager.update_tts_progress()

    def update_overall_progress_display(self):
        """전체 진행률 표시 업데이트"""
        return self.progress_manager.update_overall_progress_display()

    def _build_overall_witty_message(
        self, progress: float, completed: int, total: int
    ) -> str:
        return self.progress_manager._build_overall_witty_message(
            progress, completed, total
        )

    def update_overall_progress(self, step, status, progress=None):
        """전체 진행현황 표시 업데이트"""
        return self.progress_manager.update_overall_progress(step, status, progress)

    def select_output_folder(self):
        """로컬 출력 폴더 선택"""
        return self.output_manager.select_output_folder()

    def get_output_directory(self) -> str:
        return self.output_manager.get_output_directory()

    def refresh_output_folder_display(self):
        return self.output_manager.refresh_output_folder_display()

    def start_batch_processing(self):
        """배치 처리 시작 - Delegated to BatchHandler"""
        return self.batch_handler.start_batch_processing()

    def _batch_processing_wrapper(self):
        """배치 처리 래퍼 - Delegated to BatchHandler"""
        return self.batch_handler._batch_processing_wrapper()

    def _reset_batch_ui_on_complete(self):
        """배치 처리 완료 시 UI 상태 복구 - Delegated to BatchHandler"""
        return self.batch_handler._reset_batch_ui_on_complete()

    def stop_batch_processing(self):
        """배치 처리 중지 - Delegated to BatchHandler"""
        return self.batch_handler.stop_batch_processing()

    def on_voice_mode_change(self, *_):
        return self.voice_manager.on_voice_mode_change(*_)

    def on_single_voice_change(self, *_):
        return self.voice_manager.on_single_voice_change(*_)

    def update_voice_controls(self):
        return self.voice_manager.update_voice_controls()

    def update_voice_info_label(self, latest_voice: str = None):
        return self.voice_manager.update_voice_info_label(latest_voice)

    def get_voice_status_text(self) -> str:
        return self.voice_manager.get_voice_status_text()

    def refresh_voice_status_display(self, latest_voice: str = None):
        return self.voice_manager.refresh_voice_status_display(latest_voice)

    def prepare_tts_voice(self) -> str:
        return self.voice_manager.prepare_tts_voice()

    def register_generated_video(
        self,
        voice: str,
        path: str,
        duration: float,
        size_mb: float,
        temp_dir: Optional[str] = None,
        features: Optional[List[str]] = None,
    ) -> None:
        return self.output_manager.register_generated_video(
            voice, path, duration, size_mb, temp_dir, features
        )

    def _generate_folder_name_for_url(self, url: str, timestamp: Optional[Any]) -> str:
        """Generate folder name in format: YYYYMMDD_HHMMSS_itemname"""
        return self.output_manager._generate_folder_name_for_url(url, timestamp)

    def save_generated_videos_locally(self, show_popup: bool = True) -> None:
        return self.output_manager.save_generated_videos_locally(show_popup)

    # VideoAnalyzerGUI 안의 기존 메서드 교체
    def derive_product_keyword(self, max_words: int = 3, max_length: int = 24) -> str:
        """
        파일명 등에 쓸 짧은 키워드 생성 (TTSProcessor에 의존하지 않음).
        한국어/영어 토큰에서 의미 없는 단어를 제거하고 선두 몇 개를 결합.
        """
        try:
            # 1) 우선 번역 텍스트에서 추출
            text = (self.translation_result or "").strip()

            # 2) 없으면 중국어 원문(로마자/영문이 섞였을 수도 있으니 백업으로)
            if not text:
                text = (self.last_chinese_script_text or "").strip()

            # 3) 더 없으면 현재 URL
            if not text:
                cur = getattr(self, "_current_processing_url", "") or ""
                text = cur.rsplit("/", 1)[-1] or cur

            # 4) 토큰화(한글/영문/숫자), 너무 짧은 것 제거
            import re

            tokens = re.findall(r"[0-9A-Za-z가-힣]{2,}", text)

            # 간단한 불용어(한국어/영어)
            stop = {
                "영상",
                "제품",
                "보기",
                "확인",
                "해주세요",
                "해요",
                "입니다",
                "그",
                "이",
                "저",
                "그리고",
                "the",
                "this",
                "that",
                "and",
                "for",
                "with",
                "you",
                "your",
                "please",
                "check",
                "video",
            }

            # 첫 글자/숫자 기반의 러프한 제품 키워드 후보
            cand = [t for t in tokens if t.lower() not in stop]
            if not cand:
                cand = tokens

            # 맨 앞쪽에서 몇 개만 가져와 파일친화적으로 결합
            key = "_".join(cand[:max_words]) if cand else "video"

            # 길이 제한 및 공백/슬래시 제거
            key = key.replace(" ", "_").replace("/", "-")
            if len(key) > max_length:
                key = key[:max_length].rstrip("_-")

            # 완전 비어있지 않도록 최종 안전장치
            return key or "video"
        except Exception:
            return "video"

    def show_api_status(self):
        """API 키 상태를 팝업으로 표시 - Delegated to APIHandler"""
        return self.api_handler.show_api_status()

    def extract_clean_script_from_translation(self, max_len: int = 14) -> str:
        """Clean translation text so it can be used for Korean subtitles."""
        return self.tts_processor.extract_clean_script_from_translation(max_len)

    def _split_script_for_tts(self, script: str, max_chars: int = 13) -> List[str]:
        return self.tts_processor._split_script_for_tts(script, max_chars)

    def _rebalance_subtitle_segments(
        self, segments: Iterable[str], max_chars: int
    ) -> List[str]:
        return self.tts_processor._rebalance_subtitle_segments(segments, max_chars)

    def build_tts_metadata(
        self,
        script: str,
        total_duration: float,
        tts_path: str,
        speaker: str,
        max_chars: int = 13,
    ) -> List[Dict[str, Any]]:
        return self.tts_processor.build_tts_metadata(
            script, total_duration, tts_path, speaker, max_chars
        )

    def _filter_chinese_regions(
        self, subtitle_positions: Optional[Iterable[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        return self.subtitle_detector._filter_chinese_regions(subtitle_positions)

    def apply_chinese_subtitle_removal(self, video):
        """OCR 기반 중국어 자막 블러 처리 - 중복 실행 방지"""
        return self.subtitle_processor.apply_chinese_subtitle_removal(video)

    def _update_korean_subtitle_layout(self, subtitle_positions):
        """중국어 자막 위치에 따라 한글 자막 배치 전략을 갱신한다."""
        return self.subtitle_detector._update_korean_subtitle_layout(subtitle_positions)

    def _gpu_check_chinese_chars(self, texts):
        """GPU/NumPy 가속으로 중국어 문자 개수 계산

        Args:
            texts: 텍스트 리스트

        Returns:
            각 텍스트의 중국어 문자 개수 리스트
        """
        return self.subtitle_detector._gpu_check_chinese_chars(texts)

    def _gpu_process_bbox_batch(self, bboxes, W, H):
        """GPU/NumPy 가속으로 bbox 좌표를 배치 처리

        Args:
            bboxes: bbox 리스트 (각각 4개 포인트)
            W: 비디오 너비
            H: 비디오 높이

        Returns:
            처리된 영역 정보 리스트 (x%, y%, width%, height%)
        """
        return self.subtitle_detector._gpu_process_bbox_batch(bboxes, W, H)

    def _gpu_aggregate_regions(self, all_regions):
        """GPU/NumPy 가속으로 영역 빈도 계산 및 집계

        Args:
            all_regions: 모든 감지된 영역 리스트

        Returns:
            빈도 기반 필터링된 신뢰할 수 있는 영역 리스트
        """
        return self.subtitle_detector._gpu_aggregate_regions(all_regions)

    def detect_subtitles_with_opencv(self):
        """OCR을 사용한 중국어 자막 감지 - GPU/NumPy 가속, 1초 간격, 위치 중복 시 조기 종료"""
        return self.subtitle_detector.detect_subtitles_with_opencv()

    def apply_opencv_blur_enhanced(self, video, subtitle_positions, w, h):
        """
        감지된 박스에 페더(Feather) 마스크를 적용한 자연스러운 블러.
        입력/출력 시그니처 기존 유지.
        """
        return self.subtitle_processor.apply_opencv_blur_enhanced(
            video, subtitle_positions, w, h
        )

    def get_video_duration_helper(self):
        """원본 영상 길이 측정 헬퍼 함수"""
        return self.video_composer.get_video_duration_helper()

    def _trim_script_for_attempt(self, script: str, reduction_rate: float) -> str:
        return self.tts_processor._trim_script_for_attempt(script, reduction_rate)

    def generate_tts_for_voice(self, voice: str):
        return self.tts_processor.generate_tts_for_voice(voice)

    def _create_videos_for_presets(self, source_video: str):
        return self.video_composer._create_videos_for_presets(source_video)

    def create_final_video(self):
        return self.video_composer.create_final_video()

    def update_status(self, message):
        """상태 표시줄 업데이트"""
        self.root.after(0, lambda: self.status_bar.config(text=message))

    def _start_login_watch(self):
        """로그인 상태 감시 시작 - Delegated to LoginHandler"""
        return self.login_handler.start_login_watch()

    def _login_watch_loop(self):
        """5초마다 로그인 상태 확인 - Delegated to LoginHandler"""
        return self.login_handler._login_watch_loop()

    def exitProgramOtherPlace(self, status: str):
        """다른 장소에서 로그인 시 종료 - Delegated to LoginHandler"""
        return self.login_handler.exit_program_other_place(status)

    def errorProgramForceClose(self, status: str):
        """서버 강제 종료 - Delegated to LoginHandler"""
        return self.login_handler.error_program_force_close(status)

    def processBeforeExitProgram(self):
        """
        Logout from server before app exit (safe for both Qt/Tk).
        서버 로그아웃 후 앱 종료 (Qt/Tk 모두 안전하게 시도).
        """
        try:
            # Validate login_data structure with safe dictionary access
            # login_data 구조 검증 (안전한 딕셔너리 접근)
            if not self.login_data or not isinstance(self.login_data, dict):
                logger.info("No login data - skipping logout")
                return

            # Safe nested dictionary access
            user_data = self.login_data.get("data", {}).get("data", {})
            user_id = user_data.get("id")
            token = self.login_data.get("data", {}).get("token") or user_data.get("token")

            if not user_id:
                logger.warning("User ID not found in login data - skipping logout")
                return

            # Attempt logout
            data = {"userId": user_id, "key": token or "ssmaker"}
            try:
                rest.logOut(**data)
                logger.info("Logout successful")
            except Exception as e:
                logger.warning(f"Logout failed (ignored): {e}")

        except (AttributeError, TypeError, KeyError) as e:
            logger.error(f"Logout data structure error (ignored): {e}")
        except Exception as e:
            logger.exception(f"Unexpected logout error (ignored): {e}")

        # 1) Qt 앱이 살아있다면 먼저 종료 시도
        try:
            from PyQt5.QtWidgets import QCoreApplication

            app = QCoreApplication.instance()
            if app is not None:
                app.quit()
                logger.info("[종료] QCoreApplication.quit() 호출")
        except Exception:
            pass

        # 2) Tk 쪽 종료
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _check_and_restore_session(self, retry_count: int = 0):
        """
        프로그램 시작 시 저장된 세션 확인 및 복구

        Args:
            retry_count: 현재 재시도 횟수
        """
        MAX_RETRIES = 3
        RETRY_DELAY_MS = 500  # 재시도 간격 (ms)

        try:
            # 저장된 세션이 있는지 확인
            if not self.session_manager.has_saved_session():
                return

            # 세션 정보 읽기
            session_data = self.session_manager.get_session_info()
            if not session_data:
                return

            # 복구 확인 메시지 생성
            message = self.session_manager.get_restore_confirmation_message(
                session_data
            )

            # 사용자에게 복구 여부 확인
            from ui.components.custom_dialog import show_question

            restore = show_question(self.root, "🔄 이전 작업 복구", message)

            if restore:
                # 세션 복구 시도
                success = self.session_manager.restore_session(session_data)
                if success:
                    from ui.components.custom_dialog import show_info

                    show_info(
                        self.root,
                        "복구 완료",
                        "이전 작업을 성공적으로 복구했습니다.\n\n"
                        "대기 중인 URL은 '작업 시작' 버튼을 눌러\n"
                        "이어서 처리할 수 있습니다.",
                    )
                else:
                    # UI 미준비로 인한 실패인 경우 재시도
                    if retry_count < MAX_RETRIES:
                        logger.warning(
                            f"[세션] 복구 실패 - {RETRY_DELAY_MS}ms 후 재시도 ({retry_count + 1}/{MAX_RETRIES})"
                        )
                        # 세션 파일은 보존하고 재시도
                        self.root.after(
                            RETRY_DELAY_MS,
                            lambda: self._retry_restore_session(
                                session_data, retry_count + 1
                            ),
                        )
                    else:
                        # 최대 재시도 횟수 초과 - 실패로 처리하되 세션 파일은 보존
                        from ui.components.custom_dialog import show_error

                        show_error(
                            self.root,
                            "복구 실패",
                            "세션 복구 중 오류가 발생했습니다.\n\n"
                            "세션 파일은 보존되어 다음 실행 시 다시 복구를 시도합니다.\n"
                            "세션을 삭제하려면 '새로 시작'을 선택하세요.",
                        )
                        logger.error("[세션] 최대 재시도 횟수 초과 - 세션 파일 보존")
            else:
                # 새로 시작 - 세션 파일 삭제
                self.session_manager.clear_session()
                self.add_log("[세션] 새로 시작 - 이전 세션 삭제")

        except Exception as e:
            logger.exception(f"[세션] 복구 확인 중 오류: {e}")

    def _retry_restore_session(self, session_data: dict, retry_count: int):
        """
        세션 복구 재시도 (사용자 확인 없이)

        Args:
            session_data: 복구할 세션 데이터
            retry_count: 현재 재시도 횟수
        """
        MAX_RETRIES = 3
        RETRY_DELAY_MS = 500

        try:
            success = self.session_manager.restore_session(session_data)
            if success:
                from ui.components.custom_dialog import show_info

                show_info(
                    self.root,
                    "복구 완료",
                    "이전 작업을 성공적으로 복구했습니다.\n\n"
                    "대기 중인 URL은 '작업 시작' 버튼을 눌러\n"
                    "이어서 처리할 수 있습니다.",
                )
            else:
                # 재시도
                if retry_count < MAX_RETRIES:
                    logger.warning(
                        f"[세션] 복구 재시도 실패 - {RETRY_DELAY_MS}ms 후 재시도 ({retry_count + 1}/{MAX_RETRIES})"
                    )
                    self.root.after(
                        RETRY_DELAY_MS,
                        lambda: self._retry_restore_session(
                            session_data, retry_count + 1
                        ),
                    )
                else:
                    # 최대 재시도 횟수 초과
                    from ui.components.custom_dialog import show_error

                    show_error(
                        self.root,
                        "복구 실패",
                        "세션 복구 중 오류가 발생했습니다.\n\n"
                        "세션 파일은 보존되어 다음 실행 시 다시 복구를 시도합니다.\n"
                        "세션을 삭제하려면 '새로 시작'을 선택하세요.",
                    )
                    logger.error("[세션] 최대 재시도 횟수 초과 - 세션 파일 보존")
        except Exception as e:
            logger.exception(f"[세션] 재시도 중 오류: {e}")

    def _auto_save_session(self):
        """작업 중 자동으로 세션 저장"""
        try:
            if self.session_manager.should_auto_save():
                self.session_manager.save_session()
        except Exception as e:
            logger.error(f"[세션] 자동 저장 실패: {e}")

    def _safe_exit(self):
        """
        Safe application exit with proper cleanup.
        적절한 정리 작업을 수행하는 안전한 종료

        Security: Uses sys.exit() instead of os._exit() to:
        - Flush all file buffers
        - Run atexit handlers
        - Close file handles properly
        - Allow cleanup of temporary files

        Falls back to os._exit() only if sys.exit() hangs.
        """
        # Try to destroy the Tkinter root window first
        try:
            self.root.quit()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

        # Give daemon threads a brief moment to finish
        # (daemon threads auto-terminate when main thread exits)
        time.sleep(0.1)

        # Attempt graceful exit first
        try:
            sys.exit(0)
        except SystemExit:
            # SystemExit is expected - let it propagate
            # If we reach here, sys.exit() worked
            pass
        except Exception as e:
            logger.warning(f"[종료] sys.exit() 실패: {e}, os._exit() 사용")
            # Fallback to os._exit() if sys.exit() fails
            os._exit(0)

    def _on_close_request(self):
        """프로그램 종료 전 확인 및 세션 저장"""
        try:
            # 종료 확인 팝업 (커스텀 다이얼로그 사용)
            result = show_question(self.root, "프로그램 종료", "정말 종료하시겠습니까?")
            if not result:
                return  # 사용자가 "아니오" 선택 시 종료 취소
        except Exception as e:
            logger.error(f"[종료] 확인 다이얼로그 오류: {e}")
            # 다이얼로그 오류 시에도 종료 진행

        try:
            # 진행 중이거나 대기 중인 작업이 있으면 세션 저장
            if self.session_manager.should_auto_save():
                self.session_manager.save_session()
                logger.info("[세션] 종료 전 세션 저장 완료")
            else:
                # 작업이 없으면 세션 파일 삭제
                self.session_manager.clear_session()
        except Exception as e:
            logger.error(f"[세션] 종료 전 저장 실패: {e}")

        try:
            self.processBeforeExitProgram()
        except Exception as e:
            logger.error(f"[종료] 종료 전 처리 실패: {e}")

        # Safe exit: Try graceful exit first, then force if needed
        # 안전 종료: 먼저 정상 종료 시도, 필요시 강제 종료
        self._safe_exit()


def main():
    root = tk.Tk()
    app = VideoAnalyzerGUI(root)

    root.mainloop()


if __name__ == "__main__":
    main()
