# -*- coding: utf-8 -*-
"""
Delegation Mixin - Manager delegation stubs for VideoAnalyzerGUI.

Provides backward-compatible method stubs that delegate to various managers.
Extracted from main.py for cleaner separation.
"""
from utils.logging_config import get_logger

logger = get_logger(__name__)


class DelegationMixin:
    """Provides delegation stubs to various managers.

    Requires:
        - self.queue_manager: QueueManager instance
        - self.batch_handler: BatchHandler instance
        - self.output_manager: OutputManager instance
        - self.api_handler: APIHandler instance
        - self.voice_manager: VoiceManager instance
        - self.session_manager: SessionManager instance
        - self._video_helpers: VideoHelpers instance
        - self._generated_video_manager: GeneratedVideoManager instance
        - self.status_bar: StatusBar widget
        - self.topbar: TopBarPanel widget
    """

    # ================================================================
    # Status update
    # ================================================================
    def update_status(self, status_text: str):
        """Update status bar text."""
        bar = getattr(self, "status_bar", None)
        if bar and hasattr(bar, "update_status"):
            bar.update_status(status_text)

    def update_url_listbox(self):
        """Update URL list display."""
        self.queue_manager.update_url_listbox()

    # ================================================================
    # Video helpers (delegated to VideoHelpers)
    # ================================================================
    def get_video_duration_helper(self) -> float:
        """Get duration of source video."""
        return self._video_helpers.get_video_duration()

    def apply_chinese_subtitle_removal(self, video):
        """Apply blur to Chinese subtitles in video."""
        return self._video_helpers.apply_chinese_subtitle_removal(video)

    def detect_subtitles_with_opencv(self):
        """Detect subtitle regions using OCR."""
        return self._video_helpers.detect_subtitles_with_opencv()

    def extract_clean_script_from_translation(self, max_len: int = 14) -> str:
        """Extract clean Korean script from translation result."""
        return self._video_helpers.extract_clean_script_from_translation(max_len)

    def cleanup_temp_files(self):
        """Clean up temporary downloaded files."""
        self._video_helpers.cleanup_temp_files()

    # ================================================================
    # Generated video management (delegated to GeneratedVideoManager)
    # ================================================================
    def register_generated_video(
        self, voice, output_path, duration, file_size, temp_dir
    ):
        """Register a newly generated video."""
        self._generated_video_manager.register(
            voice, output_path, duration, file_size, temp_dir
        )

    def save_generated_videos_locally(self, show_popup=True):
        """Save generated videos to output folder."""
        self._generated_video_manager.save_locally(show_popup)

    # ================================================================
    # Session management
    # ================================================================
    def _auto_save_session(self):
        """Auto-save current session."""
        mgr = getattr(self, "session_manager", None)
        if mgr:
            try:
                mgr.save_session()
            except Exception as e:
                logger.warning(f"[세션] 자동 저장 실패: {e}")

    # ================================================================
    # URL helpers (delegated to QueueManager)
    # ================================================================
    def add_url_from_entry(self):
        """Add URL from entry widget to queue."""
        self.queue_manager.add_url_from_entry()

    def paste_and_extract(self):
        """Paste and extract URLs from clipboard."""
        self.queue_manager.paste_and_extract()

    def remove_selected_url(self):
        """Remove selected URL from queue."""
        self.queue_manager.remove_selected_url()

    def clear_url_queue(self):
        """Clear all URLs from queue."""
        self.queue_manager.clear_url_queue()

    def clear_waiting_only(self):
        """Clear only waiting URLs from queue."""
        self.queue_manager.clear_waiting_only()

    def clear_completed_only(self):
        """Clear only completed URLs from queue."""
        self.queue_manager.clear_completed_only()

    # ================================================================
    # Batch processing (delegated to BatchHandler)
    # ================================================================
    def _navigate_to_settings(self):
        """Navigate to settings tab."""
        self._on_step_selected("settings")

    def start_batch_processing(self):
        """Start batch processing."""
        self.batch_handler.start_batch_processing()

    def stop_batch_processing(self):
        """Stop batch processing."""
        self.batch_handler.stop_batch_processing()

    # ================================================================
    # Output / API / Voice
    # ================================================================
    def select_output_folder(self):
        """Open folder selection dialog."""
        self.output_manager.select_output_folder()

    def show_api_key_manager(self):
        """Show API key manager dialog."""
        self.api_handler.show_api_key_manager()

    def show_api_status(self):
        """Show API status dialog."""
        self.api_handler.show_api_status()

    def play_voice_sample(self, voice_id: str):
        """Play voice sample audio."""
        self.voice_manager.play_voice_sample(voice_id)

    def _toggle_voice(self, voice_id: str):
        """Toggle voice selection."""
        self.voice_manager.on_voice_card_clicked(voice_id)

    def refresh_user_status(self):
        """Refresh user status display in topbar."""
        self.topbar.refresh_user_status()

    def _show_subscription_panel(self):
        """Show subscription panel."""
        self.topbar.show_subscription_panel()

    def _update_subscription_info(self):
        """Update subscription info display."""
        if hasattr(self, "topbar") and hasattr(self.topbar, "refresh_user_status"):
            self.topbar.refresh_user_status()
