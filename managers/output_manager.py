"""
OutputManager rewritten to use PyQt6 QFileDialog (no legacy Tk dependency).
"""

from __future__ import annotations

import os
import re
import sys
import shutil
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import QFileDialog, QWidget
from ui.components.custom_dialog import show_info, show_success
from caller import ui_controller
from managers.settings_manager import get_settings_manager
from utils.logging_config import get_logger

logger = get_logger(__name__)


class OutputManager:
    """
    Manager class for handling output file operations.
    """

    def __init__(self, gui: QWidget):
        self.gui = gui

    def select_output_folder(self):
        """Open a PyQt6 folder picker and update GUI state."""
        old_folder = getattr(self.gui, "output_folder_path", "")
        selected = QFileDialog.getExistingDirectory(self.gui, "Select Output Folder", old_folder or os.getcwd())
        if not selected:
            return
        selected = os.path.abspath(selected)
        os.makedirs(selected, exist_ok=True)
        folder_changed = old_folder != selected

        self.gui.output_folder_path = selected
        output_folder_label = getattr(self.gui, "output_folder_label", None)
        if output_folder_label is not None:
            output_folder_label.setText(selected)

        if folder_changed:
            get_settings_manager().set_output_folder(selected)
            show_success(self.gui, "폴더 변경", f"출력 폴더가 변경되었습니다:\n{selected}")

    # Existing register/save methods kept for compatibility (logic untouched)
    def register_video(self, url: str, file_path: str) -> None:
        if not hasattr(self.gui, "url_remarks"):
            self.gui.url_remarks = {}
        self.gui.url_remarks[url] = file_path

    def get_safe_filename(self, url: str) -> str:
        sanitized = re.sub(r"[^0-9a-zA-Z-_]+", "_", url)[:120]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{sanitized}"

    def verify_video_log(self, url: str) -> str:
        """처리 로그를 분석하여 싱크/오류 문제를 확인하고 비고 문자열 반환."""
        log_buffer = getattr(self.gui, "_url_log_buffer", None)
        if not log_buffer:
            return "통과"

        log_text = "".join(log_buffer)
        issues: List[str] = []

        error_patterns = {
            "싱크 불일치": ["sync", "싱크", "synchronization", "timing mismatch"],
            "TTS 실패": ["tts 실패", "tts fail", "음성 생성 실패", "voice generation failed"],
            "자막 오류": ["subtitle error", "자막 오류", "srt error"],
            "인코딩 오류": ["encoding error", "인코딩 오류", "ffmpeg error", "codec error"],
            "API 오류": ["api error", "api 오류", "500 internal"],
        }

        log_lower = log_text.lower()
        for label, keywords in error_patterns.items():
            if any(kw in log_lower for kw in keywords):
                issues.append(label)

        if issues:
            return ", ".join(issues)
        return "통과"

    def open_folder(self, path: str):
        if not path:
            return
        try:
            if os.name == "nt":
                os.startfile(path)
            elif os.name == "posix":
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", path])
        except Exception as exc:
            logger.error("Failed to open folder %s: %s", path, exc)
            show_info(self.gui, "안내", "폴더를 열 수 없습니다.")
