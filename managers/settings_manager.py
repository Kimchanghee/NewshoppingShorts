"""
Settings Manager for UI Preferences Persistence

Saves and loads user preferences (CTA, voice selection, font) to a JSON file.
"""

import json
import os
import threading
from typing import Any, Dict, List, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)


class SettingsManager:
    """Manages persistent storage of UI preferences (thread-safe)"""

    DEFAULT_SETTINGS = {
        "cta_id": "default",
        "font_id": "seoul_hangang",
        "selected_voices": [],  # List of selected voice IDs
        "gender_filter": "all",
        "output_folder": "",  # 저장 폴더 경로 (빈 문자열이면 바탕화면)
        "theme": "light",  # 테마 설정 (light/dark)
        "tutorial_completed": False,  # 튜토리얼 완료 여부
        # 워터마크 설정
        "watermark_enabled": False,  # 워터마크 활성화 여부
        "watermark_channel_name": "",  # 채널 이름
        "watermark_position": "bottom_right",  # 위치: top_left, top_right, bottom_left, bottom_right
    }

    def __init__(self, settings_file: str = "ui_preferences.json"):
        """
        Initialize the settings manager.

        Args:
            settings_file: Name of the settings file (stored in app directory)
        """
        self.settings_file = settings_file
        self._settings: Dict[str, Any] = {}
        self._lock = threading.Lock()  # Thread safety lock
        self._load_settings()

    def _get_settings_path(self) -> str:
        """Get the full path to the settings file"""
        # Store in the same directory as the script/executable
        try:
            # For frozen executables (PyInstaller)
            import sys
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            logger.debug(f"[SettingsManager] 기본 경로 감지 실패, cwd 사용: {e}")
            base_dir = os.getcwd()

        return os.path.join(base_dir, self.settings_file)

    def _load_settings(self) -> None:
        """Load settings from file (thread-safe)"""
        settings_path = self._get_settings_path()

        try:
            with self._lock:
                if os.path.exists(settings_path):
                    with open(settings_path, 'r', encoding='utf-8') as f:
                        loaded = json.load(f)
                        # Merge with defaults to handle new settings
                        self._settings = {**self.DEFAULT_SETTINGS, **loaded}
                        # Settings loaded successfully
                else:
                    self._settings = self.DEFAULT_SETTINGS.copy()
                    # Using default settings (no file found)
        except Exception as e:
            # Settings loading failed - using defaults
            logger.warning(f"[SettingsManager] Settings loading failed: {e}")
            self._settings = self.DEFAULT_SETTINGS.copy()

    def _save_settings(self) -> bool:
        """Save settings to file (thread-safe)"""
        settings_path = self._get_settings_path()

        try:
            with self._lock:
                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump(self._settings, f, ensure_ascii=False, indent=2)
            logger.debug(f"[SettingsManager] Settings saved: {settings_path}")
            return True
        except Exception as e:
            logger.error(f"[SettingsManager] Settings save failed: {e}")
            return False

    # ============ CTA Settings ============

    def get_cta_id(self) -> str:
        """Get the saved CTA selection ID"""
        return self._settings.get("cta_id", "default")

    def set_cta_id(self, cta_id: str) -> bool:
        """
        Save the CTA selection.

        Args:
            cta_id: The CTA option ID to save

        Returns:
            True if save was successful
        """
        self._settings["cta_id"] = cta_id
        return self._save_settings()

    # ============ Font Settings ============

    def get_font_id(self) -> str:
        """Get the saved font selection ID"""
        return self._settings.get("font_id", "seoul_hangang")

    def set_font_id(self, font_id: str) -> bool:
        """
        Save the font selection.

        Args:
            font_id: The font option ID to save

        Returns:
            True if save was successful
        """
        self._settings["font_id"] = font_id
        return self._save_settings()

    # ============ Voice Settings ============

    def get_selected_voices(self) -> List[str]:
        """Get the list of selected voice IDs"""
        return self._settings.get("selected_voices", [])

    def set_selected_voices(self, voice_ids: List[str]) -> bool:
        """
        Save the selected voices.

        Args:
            voice_ids: List of voice IDs that are selected

        Returns:
            True if save was successful
        """
        self._settings["selected_voices"] = list(voice_ids)
        return self._save_settings()

    def get_gender_filter(self) -> str:
        """Get the saved gender filter setting"""
        return self._settings.get("gender_filter", "all")

    def set_gender_filter(self, gender: str) -> bool:
        """
        Save the gender filter setting.

        Args:
            gender: 'all', 'male', or 'female'

        Returns:
            True if save was successful
        """
        self._settings["gender_filter"] = gender
        return self._save_settings()

    # ============ Output Folder Settings ============

    def get_output_folder(self) -> str:
        """Get the saved output folder path"""
        return self._settings.get("output_folder", "")

    def set_output_folder(self, folder_path: str) -> bool:
        """
        Save the output folder path with validation.

        Args:
            folder_path: The folder path to save videos to

        Returns:
            True if save was successful, False if path is invalid
        """
        # Validate path: empty string is allowed (means use default desktop)
        if folder_path and not os.path.isdir(folder_path):
            logger.warning(f"[SettingsManager] Invalid output folder path: {folder_path}")
            return False
        self._settings["output_folder"] = folder_path
        return self._save_settings()

    # ============ Theme Settings ============

    def get_theme(self) -> str:
        """Get the saved theme setting"""
        return self._settings.get("theme", "light")

    def set_theme(self, theme: str) -> bool:
        """
        Save the theme setting.

        Args:
            theme: 'light' or 'dark'

        Returns:
            True if save was successful
        """
        if theme not in ("light", "dark"):
            theme = "light"
        self._settings["theme"] = theme
        return self._save_settings()

    # ============ Tutorial Settings ============

    def is_first_run(self) -> bool:
        """
        Check if this is the first run (tutorial not completed).

        Returns:
            True if tutorial has not been completed yet
        """
        return not self._settings.get("tutorial_completed", False)

    def mark_tutorial_completed(self) -> bool:
        """
        Mark the tutorial as completed.

        Returns:
            True if save was successful
        """
        self._settings["tutorial_completed"] = True
        return self._save_settings()

    def reset_tutorial(self) -> bool:
        """
        Reset tutorial status to show it again on next run.

        Returns:
            True if save was successful
        """
        self._settings["tutorial_completed"] = False
        return self._save_settings()

    # ============ Watermark Settings ============

    def get_watermark_enabled(self) -> bool:
        """Get whether watermark is enabled"""
        return self._settings.get("watermark_enabled", False)

    def set_watermark_enabled(self, enabled: bool) -> bool:
        """
        Save the watermark enabled setting.

        Args:
            enabled: True to enable watermark

        Returns:
            True if save was successful
        """
        with self._lock:
            self._settings["watermark_enabled"] = bool(enabled)
        return self._save_settings()

    def get_watermark_channel_name(self) -> str:
        """Get the watermark channel name"""
        return self._settings.get("watermark_channel_name", "")

    def set_watermark_channel_name(self, name: str) -> bool:
        """
        Save the watermark channel name.

        Args:
            name: Channel name to display as watermark (max 50 characters)

        Returns:
            True if save was successful
        """
        # 최대 50자로 제한하여 UI 렌더링 문제 방지
        MAX_CHANNEL_NAME_LENGTH = 50
        sanitized = str(name).strip()[:MAX_CHANNEL_NAME_LENGTH]
        with self._lock:
            self._settings["watermark_channel_name"] = sanitized
        return self._save_settings()

    def get_watermark_position(self) -> str:
        """Get the watermark position"""
        return self._settings.get("watermark_position", "bottom_right")

    def set_watermark_position(self, position: str) -> bool:
        """
        Save the watermark position.

        Args:
            position: One of 'top_left', 'top_right', 'bottom_left', 'bottom_right'

        Returns:
            True if save was successful
        """
        valid_positions = ("top_left", "top_right", "bottom_left", "bottom_right")
        if position not in valid_positions:
            position = "bottom_right"
        with self._lock:
            self._settings["watermark_position"] = position
        return self._save_settings()

    def get_watermark_settings(self) -> Dict[str, Any]:
        """Get all watermark settings as a dictionary"""
        return {
            "enabled": self.get_watermark_enabled(),
            "channel_name": self.get_watermark_channel_name(),
            "position": self.get_watermark_position(),
        }

    # ============ Bulk Operations ============

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary"""
        return self._settings.copy()

    def update_settings(self, updates: Dict[str, Any]) -> bool:
        """
        Update multiple settings at once.

        Args:
            updates: Dictionary of settings to update

        Returns:
            True if save was successful
        """
        self._settings.update(updates)
        return self._save_settings()


# Global instance for easy access (thread-safe singleton)
_settings_manager: Optional[SettingsManager] = None
_settings_manager_lock = threading.Lock()


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance (thread-safe)"""
    global _settings_manager
    if _settings_manager is None:
        with _settings_manager_lock:
            # Double-checked locking
            if _settings_manager is None:
                _settings_manager = SettingsManager()
    return _settings_manager
