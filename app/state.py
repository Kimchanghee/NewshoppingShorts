"""
Lightweight application state container without legacy GUI dependency.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import os
from utils.tts_config import get_safe_tts_base_dir
from utils.logging_config import get_logger

logger = get_logger(__name__)


class AppState:
    """Container for application state variables."""

    def __init__(self, root: object = None, login_data=None):
        self.root = root
        self.login_data = login_data

        # Window properties
        self.current_width = 1300
        self.current_height = 950
        self.scale_factor = 1.0

        # Color scheme (legacy values kept)
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
        self.current_processing_index = -1

        # API configuration
        self.api_keys_file = "api_keys_config.json"
        self.api_key_manager = None
        self.genai_client = None
        self.api_key_entries: List[str] = []

        # Processing flags
        self.dynamic_processing = False
        self.batch_processing = False

        # Video source variables
        self.video_source = "none"
        self.local_file_path = ""
        self.tiktok_douyin_url = ""
        self._temp_downloaded_file = None
        self.source_video = ""

        # TTS voice configuration
        from voice_profiles import DEFAULT_MULTI_VOICE_PRESETS, VOICE_PROFILES

        default_voice = DEFAULT_MULTI_VOICE_PRESETS[0]
        self.selected_tts_voice = default_voice
        self.tts_gender = "female"
        self.fixed_tts_voice = default_voice
        self.multi_voice_presets = list(DEFAULT_MULTI_VOICE_PRESETS)
        self.available_tts_voices = list(self.multi_voice_presets)
        self.tts_voice_mode = "multi"
        self.selected_single_voice = self.available_tts_voices[0]
        self.voice_cycle_index = 0
        self.voice_section_scale = 0.45
        self.last_voice_used = self.available_tts_voices[0]
        self.voice_choice_combo = None
        self.voice_info_label = None

        # Voice profiles and selection
        self.voice_profiles = [profile.copy() for profile in VOICE_PROFILES]
        self.voice_vars: Dict[str, bool] = {p["id"]: False for p in self.voice_profiles}
        self.voice_sample_paths: Dict[str, str] = {}
        self.max_voice_selection = 10
        self.voice_summary_var = "선택된 음성: 없음"
        self._active_sample_player = None

        # Batch processing variables
        self.url_list: List[str] = []
        self.batch_output_dir = None
        self.url_gap_seconds = 10
        self.current_batch_index = 0

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
        self.current_task_var = "대기 중"
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

        # Session management
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
        self.base_tts_dir = get_safe_tts_base_dir()
        self.tts_output_dir = os.path.join(self.base_tts_dir, f"session_{self.session_id}")
        os.makedirs(self.tts_output_dir, exist_ok=True)
        self.voice_sample_dir = os.path.join(self.base_tts_dir, "voice_samples")
        os.makedirs(self.voice_sample_dir, exist_ok=True)

        self.ocr_reader = None
        self.mirror_video = False
        self.add_subtitles = True
        self.output_quality = "medium"
        self.apply_blur = True
        self._current_job_header = None
        self._stage_message_cache: Dict[str, str] = {}
        self._resize_timer = None
        self._login_watch_stop = False
        self._current_processing_url = ""
