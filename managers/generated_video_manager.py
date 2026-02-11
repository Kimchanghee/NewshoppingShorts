# -*- coding: utf-8 -*-
"""
Generated Video Manager - Handles registration and saving of generated videos.

Extracted from main.py for cleaner separation of video output responsibilities.
"""
import os
import re
import shutil
from datetime import datetime
from typing import TYPE_CHECKING, List, Dict, Any

from utils.logging_config import get_logger

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI

logger = get_logger(__name__)


class GeneratedVideoManager:
    """Manages generated video registration and local saving."""

    def __init__(self, app: "VideoAnalyzerGUI"):
        self.app = app

    def register(
        self,
        voice: str,
        output_path: str,
        duration: float,
        file_size: float,
        temp_dir: str,
    ):
        """Register a newly generated video.

        Args:
            voice: Voice ID used for this video
            output_path: Path to the generated video file
            duration: Video duration in seconds
            file_size: File size in MB
            temp_dir: Temporary directory used during generation
        """
        if not hasattr(self.app, "generated_videos"):
            self.app.generated_videos = []

        self.app.generated_videos.append(
            {
                "voice": voice,
                "path": output_path,
                "duration": duration,
                "file_size_mb": file_size,
                "temp_dir": temp_dir,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def save_locally(self, show_popup: bool = True) -> int:
        """Save generated videos to output folder.

        Moves videos from temp directories to the configured output folder,
        organized by URL and timestamp.

        Args:
            show_popup: Whether to show success dialog

        Returns:
            Number of successfully saved videos.
        """
        if not hasattr(self.app, "generated_videos") or not self.app.generated_videos:
            return 0

        output_dir = getattr(self.app, "output_folder_path", None)
        if not output_dir:
            output_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        os.makedirs(output_dir, exist_ok=True)

        # URL별 하위 폴더 생성
        url = getattr(self.app, "_current_processing_url", "") or ""
        start_time = getattr(self.app, "_processing_start_time", datetime.now())
        timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")

        # URL에서 폴더명 생성
        url_slug = re.sub(r"[^0-9a-zA-Z가-힣-_]+", "_", url)[:60] if url else "local"
        subfolder_name = f"{timestamp_str}_{url_slug}"
        url_output_dir = os.path.join(output_dir, subfolder_name)
        os.makedirs(url_output_dir, exist_ok=True)

        saved_count = 0
        for video_info in self.app.generated_videos:
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
        self._cleanup_temp_dirs()

        if saved_count > 0 and show_popup:
            self._show_success_popup(saved_count, url_output_dir)

        # Log video generation
        try:
            from caller.rest import log_user_action
            log_user_action("영상 생성 완료", f"{saved_count}개의 영상이 생성되었습니다.")
        except Exception:
            pass

        return saved_count

    def _cleanup_temp_dirs(self):
        """Clean up temporary directories from generated videos."""
        for video_info in self.app.generated_videos:
            temp_dir = video_info.get("temp_dir")
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    def _show_success_popup(self, count: int, output_dir: str):
        """Show success dialog after saving videos.

        Args:
            count: Number of saved videos
            output_dir: Directory where videos were saved
        """
        try:
            from ui.components.custom_dialog import show_success

            show_success(
                self.app,
                "저장 완료",
                f"{count}개 영상이 저장되었습니다.\n{output_dir}",
            )
        except Exception as e:
            logger.warning(f"[저장] 성공 팝업 표시 실패: {e}")

    def get_saved_videos(self) -> List[Dict[str, Any]]:
        """Get list of all registered videos.

        Returns:
            List of video info dictionaries.
        """
        return getattr(self.app, "generated_videos", [])

    def clear(self):
        """Clear all registered videos."""
        if hasattr(self.app, "generated_videos"):
            self.app.generated_videos.clear()
