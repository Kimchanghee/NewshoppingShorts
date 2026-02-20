# -*- coding: utf-8 -*-
"""
Video Helpers - Video processing utility methods extracted from main.py.

Provides helper functions for video duration, subtitle processing,
script extraction, and temp file cleanup.
"""
import os
import re
from typing import TYPE_CHECKING

from utils.logging_config import get_logger

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI

logger = get_logger(__name__)


class VideoHelpers:
    """Video processing helper methods."""

    def __init__(self, app: "VideoAnalyzerGUI"):
        self.app = app

    def get_video_duration(self) -> float:
        """Get duration of source video.

        Returns:
            Video duration in seconds, or 0.0 on failure.
        """
        try:
            from moviepy.editor import VideoFileClip

            source = getattr(self.app, "_temp_downloaded_file", None)
            if source and os.path.exists(source):
                clip = VideoFileClip(source)
                duration = clip.duration
                clip.close()
                return duration
        except Exception as e:
            logger.warning(f"[Duration] 영상 길이 확인 실패: {e}")
        return 0.0

    def apply_chinese_subtitle_removal(self, video):
        """Apply blur to Chinese subtitles in video.

        Args:
            video: MoviePy video clip

        Returns:
            Processed video clip with blurred subtitles, or original on failure.
        """
        try:
            from processors.subtitle_processor import SubtitleProcessor

            processor = SubtitleProcessor(self.app)
            return processor.apply_chinese_subtitle_removal(video)
        except Exception as e:
            logger.warning(f"[Subtitle Removal] 실패: {e}")
            return video

    def detect_subtitles_with_opencv(self) -> list:
        """Detect subtitle regions using OCR.

        Returns:
            List of detected subtitle regions, or empty list on failure.
        """
        try:
            from processors.subtitle_detector import SubtitleDetector

            detector = SubtitleDetector(self.app)
            return detector.detect_subtitles_with_opencv()
        except Exception as e:
            logger.warning(f"[OCR] 자막 감지 실패: {e}")
            return []

    def extract_clean_script_from_translation(self, max_len: int = 14) -> str:
        """Extract clean Korean script from translation result.

        Removes metadata, timestamps, and formatting to get pure text.

        Args:
            max_len: Maximum length multiplier (max_len * 200 chars)

        Returns:
            Cleaned script text.
        """
        try:
            raw = (self.app.translation_result or "").strip()
            full_script = ""

            if raw:
                cleaned_lines = []
                for original_line in raw.splitlines():
                    line = original_line.strip()
                    if not line:
                        continue
                    # Skip separator lines
                    if re.match(r"^[#*= -]{3,}$", line):
                        continue
                    # Remove bracketed content
                    line = re.sub(r"\[[^\]]*\]", "", line)
                    line = re.sub(r"\([^)]*\)", "", line)
                    # Remove numbered/bulleted list markers
                    line = re.sub(r"^\d+[\.)]\s*", "", line)
                    line = re.sub(r"^(?:-|\*|\u2022)\s*", "", line)
                    # Normalize whitespace
                    line = re.sub(r"\s+", " ", line).strip()
                    if len(line) < 2:
                        continue
                    cleaned_lines.append(line)

                if not cleaned_lines:
                    cleaned_lines = [
                        ln.strip() for ln in raw.splitlines() if ln.strip()
                    ]
                full_script = re.sub(r"\s+", " ", " ".join(cleaned_lines)).strip()

            # Fallback: video analysis result
            if not full_script:
                video_analysis = getattr(self.app, "video_analysis_result", None)
                if video_analysis:
                    if isinstance(video_analysis, str):
                        full_script = video_analysis.strip()
                    elif isinstance(video_analysis, dict):
                        full_script = (
                            video_analysis.get("description", "")
                            or video_analysis.get("script", "")
                        )

            # Fallback: analysis_result dict
            if not full_script and isinstance(
                getattr(self.app, "analysis_result", None), dict
            ):
                alt = self.app.analysis_result.get("script")
                if isinstance(alt, list):
                    fallback = " ".join(
                        str(entry.get("text", "")).strip()
                        for entry in alt
                        if isinstance(entry, dict) and entry.get("text")
                    )
                    full_script = re.sub(r"\s+", " ", fallback).strip()

            # Truncate if too long
            if max_len and len(full_script) > max_len * 200:
                full_script = full_script[: max_len * 200].rsplit(" ", 1)[0].strip()

            return full_script
        except Exception as e:
            logger.error(f"[ScriptExtract] 스크립트 추출 오류: {e}")
            return re.sub(
                r"[^\w\s.,!?\uAC00-\uD7A3]", "", self.app.translation_result or ""
            ).strip()

    def cleanup_temp_files(self):
        """Clean up temporary downloaded files."""
        temp_paths = []

        temp_file = getattr(self.app, "_temp_downloaded_file", None)
        if isinstance(temp_file, str) and temp_file:
            temp_paths.append(temp_file)

        temp_files = getattr(self.app, "_temp_downloaded_files", None)
        if isinstance(temp_files, list):
            for path in temp_files:
                if isinstance(path, str) and path:
                    temp_paths.append(path)

        for path in dict.fromkeys(temp_paths):
            if not os.path.exists(path):
                continue
            try:
                os.remove(path)
                logger.debug(f"[정리] 임시 파일 삭제: {path}")
                parent = os.path.dirname(path)
                if parent:
                    parent_name = os.path.basename(parent)
                    if parent_name.startswith(
                        (
                            "mix_source_",
                            "tiktok_douyin_",
                            "tiktok_video_",
                            "douyin_video_",
                            "xiaohongshu_video_",
                            "kuaishou_video_",
                        )
                    ):
                        try:
                            os.rmdir(parent)
                        except Exception:
                            pass
            except Exception as e:
                logger.debug(f"[정리] 삭제 실패 (무시됨): {e}")

        self.app._temp_downloaded_file = None
        self.app._temp_downloaded_files = []
