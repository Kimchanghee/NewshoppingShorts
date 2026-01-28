"""
Application State Container

This module contains all application state variables previously scattered
throughout the VideoAnalyzerGUI __init__ method.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import tkinter as tk
import os
from ssmaker import get_safe_tts_base_dir
from utils.logging_config import get_logger

logger = get_logger(__name__)


class AppState:
    """Container for all application state variables"""

    def __init__(self, root: tk.Tk, login_data=None):
        # Core references
        self.root = root
        self.login_data = login_data

        # Configuration (will be set by main_app)
        self.config = None

        # Window properties
        self.current_width = 1300
        self.current_height = 950
        self.scale_factor = 1.0

        # Color scheme (Chrome-inspired)
        self.bg_color = "#F5F2FC"
        self.header_bg = "#F5F2FC"
        self.card_bg = "#ffffff"
        self.border_color = "#e2dcd1"
        self.primary_color = "#7c6ef2"
        self.accent_color = "#5e52d6"
        self.text_color = "#2c2642"
        self.secondary_text = "#7e7794"
        self.success_color = "#37c986"
        self.warning_color = "#f9a63a"
        self.error_color = "#e0565b"

        # URL queue and status
        self.url_queue: List[str] = []
        self.url_status: Dict[str, str] = {}
        self.url_status_message: Dict[str, str] = {}
        self.url_timestamps: Dict[str, Any] = {}
        self.url_remarks: Dict[str, str] = {}
        self.url_listbox = None
        self.url_entry = None
        self.current_processing_index = -1

        # API configuration
        self.api_keys_file = "api_keys_config.json"
        self.api_key_manager = None
        self.genai_client = None
        self.api_key_entries: List[tk.Entry] = []

        # Token cost calculator
        from utils.token_cost_calculator import TokenCostCalculator
        self.token_calculator = TokenCostCalculator()

        # Processing flags
        self.dynamic_processing = False
        self.batch_processing = False

        # Video source variables
        self.video_source = tk.StringVar(value="none")
        self.local_file_path = ""
        self.tiktok_douyin_url = ""
        self._temp_downloaded_file = None
        self.source_video = ""

        # TTS voice configuration
        from voice_profiles import DEFAULT_MULTI_VOICE_PRESETS, VOICE_PROFILES

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

        # Voice profiles and selection
        self.voice_profiles = [profile.copy() for profile in VOICE_PROFILES]
        self.voice_vars: Dict[str, tk.BooleanVar] = {}
        self.voice_sample_paths: Dict[str, str] = {}
        self.max_voice_selection = 10
        self.voice_summary_var = tk.StringVar(value="선택된 음성: 없음")
        self._active_sample_player = None

        # Batch processing variables
        self.url_list: List[str] = []
        self.batch_output_dir = None
        self.url_gap_seconds = 10
        self.current_batch_index = 0
        self.url_list_text = None
        import threading
        self.batch_processing_lock = threading.Lock()
        self.batch_thread = None

        # Output folder configuration
        try:
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.isdir(desktop_path):
                desktop_path = os.path.join(os.getcwd(), "outputs")
        except Exception as e:
            logger.warning("Failed to get desktop path, using outputs folder: %s", e)
            desktop_path = os.path.join(os.getcwd(), "outputs")

        os.makedirs(desktop_path, exist_ok=True)
        self.output_folder_path = desktop_path
        self.output_folder_var = tk.StringVar(value=self.output_folder_path)
        self.output_folder_button = None
        self.output_folder_label = None
        self.start_batch_button = None
        self.stop_batch_button = None

        # Analysis and processing results
        self.analysis_result: Dict[str, Any] = {}
        self.last_chinese_script_lines: List[str] = []
        self.last_chinese_script_text: str = ""
        self.last_chinese_script_digest: Optional[str] = None
        self.center_subtitle_region: Optional[Dict[str, Any]] = None
        self.translation_result = ""
        self.tts_file_path = ""
        self.tts_files: List[str] = []
        self.final_video_path = ""
        self.final_video_temp_dir = None
        self.generated_videos: List[Dict[str, Any]] = []
        self.korean_subtitle_override = None
        self.korean_subtitle_mode = 'default'
        self.cached_video_width: Optional[int] = None
        self.cached_video_height: Optional[int] = None

        # TTS metadata
        self.speaker_voice_mapping: Dict[str, str] = {}
        self.last_tts_segments: List[Dict[str, Any]] = []
        self._per_line_tts: List[Any] = []
        self.tts_sync_info: Dict[str, Any] = {}

        # Progress tracking
        self.current_task_var = tk.StringVar(value="대기 중")
        self._current_job_header = None

        self.progress_states = {
            'download': {'status': 'waiting', 'progress': 0, 'message': None},
            'analysis': {'status': 'waiting', 'progress': 0, 'message': None},
            'subtitle': {'status': 'waiting', 'progress': 0, 'message': None},
            'translation': {'status': 'waiting', 'progress': 0, 'message': None},
            'tts': {'status': 'waiting', 'progress': 0, 'message': None},
            'video': {'status': 'waiting', 'progress': 0, 'message': None},
            'tts_audio': {'status': 'waiting', 'progress': 0, 'message': None},
            'audio_merge': {'status': 'waiting', 'progress': 0, 'message': None},
            'audio_analysis': {'status': 'waiting', 'progress': 0, 'message': None},
            'subtitle_overlay': {'status': 'waiting', 'progress': 0, 'message': None},
            'post_tasks': {'status': 'waiting', 'progress': 0, 'message': None},
            'finalize': {'status': 'waiting', 'progress': 0, 'message': None},
        }

        # Stage messages for UX
        self.stage_messages = {
            'download': [
                "현재 원본 동영상을 찾고 있습니다.",
                "링크 속 숨은 명장면을 뒤지는 중이에요.",
                "다운로드 터널 속에서 영상을 끌어오는 중입니다."
            ],
            'analysis': [
                "동영상을 분석하고 있습니다.",
                "씬별 포인트를 캐치하고 있어요.",
                "내용을 샅샅이 뜯어보고 있습니다."
            ],
            'subtitle': [
                "중국어 자막을 분석하고 있습니다.",
                "프레임 속 글자를 한 줄씩 추적하는 중이에요.",
                "자막 위치를 확대경으로 살피고 있습니다."
            ],
            'translation': [
                "번역과 각색을 하고 있습니다.",
                "한국어 감성으로 문장을 다듬는 중이에요.",
                "의미를 살리며 자연스럽게 고쳐 쓰고 있습니다."
            ],
            'tts': [
                "목소리를 입히는 중이에요.",
                "톤과 감정을 맞춰 한 줄씩 녹음하고 있어요.",
                "듣기 좋은 보이스를 믹싱 중입니다."
            ],
            'video': [
                "영상을 최종 인코딩 하고 있습니다.",
                "장면을 이어 붙이며 피날레를 완성 중이에요.",
                "렌더링 엔진이 열심히 팬을 돌리고 있습니다."
            ],
            'tts_audio': [
                "TTS 음성을 조물조물 빚는 중입니다.",
                "대사를 가장 자연스러운 목소리로 녹음하고 있어요.",
                "보이스 배우가 마이크 앞에서 열연 중입니다."
            ],
            'audio_merge': [
                "갓 구운 TTS를 영상에 살포시 얹는 중입니다.",
                "오디오와 영상이 한 몸이 되도록 맞붙이고 있어요.",
                "볼륨과 템포를 맞춰 한 컷에 담는 중입니다."
            ],
            'audio_analysis': [
                "오디오를 세밀하게 들으며 자막 타이밍을 측정 중입니다.",
                "파형 위를 탐정처럼 훑으며 싱크를 계산하고 있어요.",
                "귀로 들은 시간을 숫자로 바꾸는 중입니다."
            ],
            'subtitle_overlay': [
                "계산한 타이밍으로 자막을 딱 맞춰 붙이고 있습니다.",
                "문장마다 화면에 착 붙도록 자막을 얹는 중이에요.",
                "자막이 화면 위에서 춤출 준비를 하고 있습니다."
            ],
            'post_tasks': [
                "마지막 다듬기를 하며 군더더기를 정리하고 있어요.",
                "마무리 전 필수 점검 항목을 체크 중입니다.",
                "잔잔바리 작업들을 싹 쓸어 담는 중입니다."
            ],
            'finalize': [
                "피날레 렌더링으로 결과물을 포장 중입니다.",
                "이제 곧 완성본이 탄생합니다. 조금만 기다려 주세요!",
                "완성본을 반짝이 리본으로 묶는 중입니다."
            ]
        }
        self._stage_message_cache: Dict[str, str] = {}

        # Session management (안전한 경로 사용)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
        self.base_tts_dir = get_safe_tts_base_dir()
        self.tts_output_dir = os.path.join(self.base_tts_dir, f"session_{self.session_id}")
        os.makedirs(self.tts_output_dir, exist_ok=True)
        self.voice_sample_dir = os.path.join(self.base_tts_dir, "voice_samples")
        os.makedirs(self.voice_sample_dir, exist_ok=True)

        # OCR reader
        self.ocr_reader = None

        # Video options
        self.mirror_video = tk.BooleanVar(value=False)
        self.add_subtitles = tk.BooleanVar(value=True)
        self.output_quality = tk.StringVar(value="medium")
        self.apply_blur = tk.BooleanVar(value=True)

        # UI components (will be set during UI setup)
        self.script_progress = None
        self.translation_progress = None
        self.tts_progress = None
        self.script_text = None
        self.translation_text = None
        self.tts_result_text = None
        self.tts_status_label = None
        self.create_final_video_button = None
        self.save_path_label = None
        self.analyze_button = None
        self.status_bar = None

        # Icon reference (prevent garbage collection)
        self._root_icon = None

        # Resize timer
        self._resize_timer = None

        # Scaled fonts (responsive)
        self.scaled_fonts: Dict[str, int] = {}
        self.scaled_padding = 18

        # Login watch control
        self._login_watch_stop = False

        # Current processing URL (for derive_product_keyword)
        self._current_processing_url = ""
