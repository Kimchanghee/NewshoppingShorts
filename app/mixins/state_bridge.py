# -*- coding: utf-8 -*-
"""
State Bridge Mixin - Creates attribute aliases from AppState to VideoAnalyzerGUI.

This mixin extracts the state aliasing logic from main.py for cleaner separation.
Maintains backward compatibility with processor.py's app.X access patterns.
"""
from utils.logging_config import get_logger

logger = get_logger(__name__)


class StateBridgeMixin:
    """Mixin that creates attribute aliases from AppState to VideoAnalyzerGUI.

    This allows processor.py and other modules to access state via app.url_queue,
    app.translation_result, etc. while the actual data lives in AppState.
    """

    def _setup_state_aliases(self):
        """Copy state references to self for processor.py compatibility.

        Call this in __init__ after self.state is initialized.
        """
        state = self.state

        # --- URL queue aliases ---
        self.url_queue = state.url_queue
        self.url_status = state.url_status
        self.url_status_message = state.url_status_message
        self.url_timestamps = state.url_timestamps
        self.url_remarks = state.url_remarks
        self.processing_mode = state.processing_mode
        self.mix_video_urls = state.mix_video_urls
        self.mix_jobs = state.mix_jobs

        # --- Output folder ---
        self.output_folder_path = state.output_folder_path
        self.output_folder_label = None

        # --- Voice aliases ---
        self.voice_profiles = state.voice_profiles
        self.voice_vars = state.voice_vars
        self.voice_sample_paths = state.voice_sample_paths
        self.multi_voice_presets = state.multi_voice_presets
        self.available_tts_voices = state.available_tts_voices
        self.max_voice_selection = state.max_voice_selection

        # --- Processing state aliases ---
        self.analysis_result = state.analysis_result
        self.translation_result = state.translation_result
        self.tts_file_path = state.tts_file_path
        self.tts_files = state.tts_files
        self.final_video_path = state.final_video_path
        self.final_video_temp_dir = state.final_video_temp_dir
        self.generated_videos = state.generated_videos
        self.speaker_voice_mapping = state.speaker_voice_mapping
        self.last_tts_segments = state.last_tts_segments
        self._per_line_tts = state._per_line_tts
        self.tts_sync_info = state.tts_sync_info
        self.progress_states = state.progress_states

        # --- Session & directory aliases ---
        self.session_id = state.session_id
        self.base_tts_dir = state.base_tts_dir
        self.tts_output_dir = state.tts_output_dir
        self.voice_sample_dir = state.voice_sample_dir

        # --- Video source aliases ---
        self.video_source = state.video_source
        self.local_file_path = state.local_file_path
        self.tiktok_douyin_url = state.tiktok_douyin_url
        self.source_video = state.source_video
        self._temp_downloaded_file = state._temp_downloaded_file
        self._temp_downloaded_files = state._temp_downloaded_files

        # --- TTS voice aliases ---
        self.fixed_tts_voice = state.fixed_tts_voice
        self.selected_tts_voice = state.selected_tts_voice
        self.last_voice_used = state.last_voice_used

        # --- Video processing options ---
        self.mirror_video = state.mirror_video
        self.add_subtitles = state.add_subtitles
        self.apply_blur = state.apply_blur
        self.max_final_video_duration = state.max_final_video_duration
        self.cached_video_width = state.cached_video_width
        self.cached_video_height = state.cached_video_height

        # --- Processing progress aliases ---
        self.current_processing_index = state.current_processing_index
        self._current_processing_url = state._current_processing_url

        # --- Subtitle options ---
        self.korean_subtitle_override = state.korean_subtitle_override
        self.korean_subtitle_mode = state.korean_subtitle_mode
        self.url_gap_seconds = state.url_gap_seconds
        self.center_subtitle_region = state.center_subtitle_region

        # --- Chinese script cache ---
        self.last_chinese_script_lines = state.last_chinese_script_lines
        self.last_chinese_script_text = state.last_chinese_script_text
        self.last_chinese_script_digest = state.last_chinese_script_digest

    def _setup_ocr_reader(self, preloaded_ocr, allow_fallback: bool = True):
        """Initialize OCR reader with fallback to direct creation.

        Args:
            preloaded_ocr: Pre-loaded OCR reader from AppController, or None
            allow_fallback: If False, skip local fallback initialization
        """
        self.ocr_reader = preloaded_ocr or self.state.ocr_reader

        # OCR reader가 없으면 직접 초기화 (main.py 직접 실행 시 AppController 우회)
        if self.ocr_reader is None and allow_fallback:
            try:
                from utils.ocr_backend import create_ocr_reader
                self.ocr_reader = create_ocr_reader()
                if self.ocr_reader:
                    logger.info(f"[OCR] 직접 초기화 성공: {self.ocr_reader.engine_name}")
                else:
                    logger.warning("[OCR] 초기화 실패: create_ocr_reader()가 None 반환")
            except Exception as e:
                logger.warning(f"[OCR] 초기화 실패: {e}")
