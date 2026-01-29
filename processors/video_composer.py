"""
Video Composition Module

This module handles final video creation with TTS and subtitles.
"""

import os
import threading
from typing import Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

try:
    # moviepy 1.x compatible imports
    from moviepy.editor import VideoFileClip

    MOVIEPY_AVAILABLE = True
except Exception as e:
    logger.debug(f"moviepy import failed: {e}")
    VideoFileClip = None
    MOVIEPY_AVAILABLE = False


class VideoComposer:
    """
    Composes final videos with TTS audio and Korean subtitles.

    This processor orchestrates the final video creation by generating TTS
    for multiple voice presets and creating final videos with synchronized subtitles.
    """

    def __init__(self, gui):
        """
        Initialize the VideoComposer.

        Args:
            gui: Main GUI instance containing video settings and TTS configuration
        """
        self.gui = gui

    def create_final_video(self):
        """
        Create final video(s) with TTS and Korean subtitles.

        Starts a background thread to generate TTS for all voice presets and
        create final videos. Each voice generates a separate output video.
        """
        if not self.gui.translation_result:
            return

        if self.gui.video_source.get() == "local":
            source_video = self.gui.local_file_path
        else:
            source_video = self.gui._temp_downloaded_file

        if not source_video or not os.path.exists(source_video):
            return

        self.gui.generated_videos = []
        self.gui._per_line_tts = []
        self.gui.tts_files = []

        thread = threading.Thread(
            target=self._create_videos_for_presets, args=(source_video,), daemon=True
        )
        thread.start()

    def _create_videos_for_presets(self, source_video: str):
        """
        Generate videos for all voice presets.

        Iterates through configured voice presets, generates TTS for each,
        and creates final videos with synchronized subtitles.

        Args:
            source_video: Path to source video file
        """
        # 사용자가 실제로 선택한 음성만 사용 (voice_vars에서 체크된 것)
        selected_voices = [
            vid for vid, state in self.gui.voice_vars.items() if state.get()
        ]
        voice_manager = getattr(self.gui, "voice_manager", None)
        if selected_voices:
            voices = []
            for vid in selected_voices:
                if voice_manager:
                    profile = voice_manager.get_voice_profile(vid)
                    if profile and profile.get("voice_name"):
                        voices.append(profile["voice_name"])
                        continue
                voices.append(vid)
            display_names = [
                voice_manager.get_voice_label(v) if voice_manager else v for v in voices
            ]
            logger.info(
                f"[음성 선택] 사용자가 선택한 음성 사용: {', '.join(display_names)}"
            )
        else:
            voices = getattr(
                self.gui, "multi_voice_presets", self.gui.available_tts_voices
            )
            display_names = [
                voice_manager.get_voice_label(v) if voice_manager else v for v in voices
            ]
            logger.info(
                f"[음성 선택] 기본 음성 사용: {', '.join(display_names) if isinstance(display_names, list) else display_names}"
            )

        total = len(voices)
        if total == 0:
            # Show warning for empty voice selection
            from ui.components.custom_dialog import show_warning

            self.gui.root.after(
                0,
                lambda: show_warning(
                    self.gui.root,
                    "음성 선택 필요",
                    "TTS 음성이 선택되지 않았습니다.\n\n"
                    "최소 1개 이상의 음성을 선택해주세요.",
                ),
            )
            self.gui.update_progress_state(
                "tts", "error", 0, "음성이 선택되지 않아 처리를 중단했습니다."
            )
            return

        self.gui.generated_videos = []
        self.gui.update_progress_state("tts", "processing", 0)

        for idx, voice in enumerate(voices, 1):
            voice_label = (
                voice_manager.get_voice_label(voice) if voice_manager else voice
            )
            self.gui.add_log(f"[VOICE] {idx}/{total} - {voice_label}")
            try:
                # Import TTS processor
                from processors.tts_processor import TTSProcessor

                tts_processor = TTSProcessor(self.gui)

                metadata, duration, output_path = tts_processor.generate_tts_for_voice(
                    voice
                )
                if not metadata or not output_path:
                    raise RuntimeError("TTS generation failed.")

                self.gui._per_line_tts = metadata
                self.gui.tts_files = [output_path]
                self.gui.fixed_tts_voice = voice
                self.gui.last_voice_used = voice
                self.gui.update_voice_info_label(latest_voice=voice)
                progress = int(idx / total * 100)
                self.gui.update_progress_state("tts", "processing", progress)

                self.gui.source_video = source_video

                # Import CreateFinalVideo module
                from core.video import CreateFinalVideo

                CreateFinalVideo.create_final_video_thread(self.gui)

            except Exception as exc:
                logger.error(f"[Video] Error during video creation for voice: {exc}")
                self.gui.update_progress_state("video", "error", message=str(exc))

        self.gui.update_progress_state("tts", "completed", 100)
        try:
            self.gui.save_generated_videos_locally()
        except Exception as exc:
            logger.error(f"[LocalSave] Failed to store generated videos: {exc}")

    def get_video_duration_helper(self) -> float:
        """
        Measure original video duration.

        Returns:
            Video duration in seconds (defaults to 60.0 if unavailable)
        """
        try:
            if not MOVIEPY_AVAILABLE or VideoFileClip is None:
                logger.warning("[영상 길이] moviepy가 없어 기본값 60초를 사용합니다.")
                return 60.0

            if self.gui.video_source.get() == "local":
                source_video = self.gui.local_file_path
            else:
                source_video = self.gui._temp_downloaded_file

            if source_video and os.path.exists(source_video):
                temp_video = VideoFileClip(source_video)
                duration = temp_video.duration
                temp_video.close()
                logger.info(f"[영상 길이] 측정 완료: {duration:.1f}초")
                return duration
            else:
                logger.warning("[영상 길이] 영상 파일을 찾을 수 없음, 기본값 60초 사용")
                return 60.0

        except Exception as e:
            logger.error(f"[영상 길이] 측정 오류: {str(e)}, 기본값 60초 사용")
            return 60.0
