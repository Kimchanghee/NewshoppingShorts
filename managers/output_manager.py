"""
OutputManager rewritten to use PyQt6 QFileDialog (no legacy Tk dependency).
"""

from __future__ import annotations

import os
import re
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
        if hasattr(self.gui, "output_folder_label"):
            self.gui.output_folder_label.setText(selected)

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
