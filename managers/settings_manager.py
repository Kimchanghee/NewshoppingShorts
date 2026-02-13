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

    DEFAULT_PLATFORM_PROMPTS = {
        "youtube": {
            "title_prompt": (
                "상품명, 핵심 기능, 타깃 고객을 반영해 유튜브 쇼츠 제목 1개를 작성하세요. "
                "30자 내외로 짧고 클릭을 유도하되 허위·과장은 금지합니다."
            ),
            "description_prompt": (
                "아래 상품 정보를 바탕으로 유튜브 게시글을 작성하세요. "
                "1) 한 줄 요약 2) 핵심 장점 2개 3) 구매 유도 CTA 1개 순서로 3~4문장 구성."
            ),
            "hashtag_prompt": (
                "상품 카테고리, 사용 상황, 타깃 키워드를 반영한 해시태그를 8~10개 작성하세요. "
                "#을 포함하고 중복 없이 작성합니다."
            ),
        },
        "tiktok": {
            "title_prompt": (
                "틱톡 숏폼 톤에 맞춰 20자 내외의 짧고 리듬감 있는 제목 1개를 작성하세요. "
                "첫 단어에서 관심을 끌고 상품 장점을 즉시 드러내세요."
            ),
            "description_prompt": (
                "틱톡 게시글용 설명을 작성하세요. "
                "1) 공감되는 사용 상황 1문장 2) 핵심 장점 2개 3) 행동 유도 CTA 1문장 순서로 구성하세요."
            ),
            "hashtag_prompt": (
                "틱톡 검색/추천에 맞는 해시태그를 6~9개 작성하세요. "
                "제품군 해시태그, 사용 상황 해시태그, 트렌드 해시태그를 균형 있게 포함하세요."
            ),
        },
        "instagram": {
            "title_prompt": (
                "인스타그램 릴스/피드에 어울리는 감성형 제목 1개를 작성하세요. "
                "브랜드 톤을 유지하면서도 상품의 핵심 가치를 한 줄로 보여주세요."
            ),
            "description_prompt": (
                "인스타그램 캡션을 작성하세요. "
                "도입 문장 1개, 상품 핵심 포인트 2개, CTA 1개를 포함하고 읽기 쉬운 줄바꿈을 사용하세요."
            ),
            "hashtag_prompt": (
                "인스타그램용 해시태그 10개 내외를 작성하세요. "
                "대형 키워드와 니치 키워드를 섞고, 동일 의미 중복 해시태그는 제외하세요."
            ),
        },
        "threads": {
            "title_prompt": (
                "스레드에 맞는 대화형 훅 문장 1개를 작성하세요. "
                "질문형 또는 공감형 시작으로 자연스럽게 상품 주제로 연결하세요."
            ),
            "description_prompt": (
                "스레드용 본문을 작성하세요. "
                "짧은 단락 2~3개로 의견/경험을 섞어 설명하고, 마지막에 토론을 유도하는 문장을 넣으세요."
            ),
            "hashtag_prompt": (
                "스레드 문맥에 맞는 핵심 해시태그를 4~6개 작성하세요. "
                "과도한 태그 나열 대신 주제 집중도를 높이는 태그만 선택하세요."
            ),
        },
        "x": {
            "title_prompt": (
                "X(트위터) 스타일로 짧고 강한 훅 문장 1개를 작성하세요. "
                "핵심 메시지를 앞에 배치하고 불필요한 수식어를 줄이세요."
            ),
            "description_prompt": (
                "X 게시글 본문을 작성하세요. "
                "핵심 요약 1문장 + 장점 2개 + CTA 1문장 구조로 간결하게 구성하세요."
            ),
            "hashtag_prompt": (
                "X용 해시태그를 3~5개 작성하세요. "
                "검색 효율이 높은 키워드 위주로 선택하고 중복/장문 태그는 제외하세요."
            ),
        },
    }

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
        "watermark_font_id": "pretendard",  # 워터마크 폰트 ID
        "watermark_font_size": "medium",  # 워터마크 크기: small, medium, large
        # 워터마크가 사용자가 직접 설정한 값인지 (기본값/테스트값 자동 초기화에 사용)
        "watermark_user_configured": False,
        # 소셜 미디어 연결 설정
        "youtube_connected": False,
        "youtube_channel_id": "",
        "youtube_channel_name": "",
        "youtube_auto_upload": False,
        "youtube_upload_interval": 60,  # 분 단위 (60, 120, 180, 240)
        # 업로드 프롬프트 설정 (채널별)
        "youtube_title_prompt": "",
        "youtube_description_prompt": "",
        "youtube_hashtag_prompt": "",
        "youtube_comment_enabled": False,
        "youtube_comment_prompt": "",
        # COMING SOON 플랫폼
        "tiktok_connected": False,
        "tiktok_title_prompt": "",
        "tiktok_description_prompt": "",
        "tiktok_hashtag_prompt": "",
        "instagram_connected": False,
        "instagram_title_prompt": "",
        "instagram_description_prompt": "",
        "instagram_hashtag_prompt": "",
        "threads_connected": False,
        "threads_title_prompt": "",
        "threads_description_prompt": "",
        "threads_hashtag_prompt": "",
        "x_connected": False,
        "x_title_prompt": "",
        "x_description_prompt": "",
        "x_hashtag_prompt": "",
        # Automation Settings
        "coupang_access_key": "",
        "coupang_secret_key": "",
        "cookies_inpock": {},  # Dict to store Inpock Link cookies
        "cookies_1688": {},  # Dict to store 1688 cookies
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

    def _get_settings_dir(self) -> str:
        """
        사용자별 설정 저장 폴더.

        NOTE:
        설정을 EXE 옆(설치 폴더)에 저장하면 업데이트/압축해제 과정에서
        테스트 설정이 같이 배포되는 문제가 생길 수 있어 사용자 홈으로 이동합니다.
        """
        return os.path.join(os.path.expanduser("~"), ".ssmaker")

    def _get_settings_path(self) -> str:
        """Get the full path to the settings file"""
        return os.path.join(self._get_settings_dir(), self.settings_file)

    def _get_legacy_settings_path(self) -> str:
        """Legacy location: next to exe / repo root (older builds)."""
        try:
            import sys
            if getattr(sys, "frozen", False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            logger.debug(f"[SettingsManager] Legacy path fallback to cwd: {e}")
            base_dir = os.getcwd()
        return os.path.join(base_dir, self.settings_file)

    def _load_settings(self) -> None:
        """Load settings from file (thread-safe)"""
        settings_path = self._get_settings_path()
        legacy_path = self._get_legacy_settings_path()
        needs_save = False

        try:
            with self._lock:
                # One-time migration: if new path missing but legacy file exists, copy.
                if not os.path.exists(settings_path) and os.path.exists(legacy_path):
                    try:
                        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
                        with open(legacy_path, "r", encoding="utf-8") as f:
                            legacy_loaded = json.load(f)
                        with open(settings_path, "w", encoding="utf-8") as f:
                            json.dump(legacy_loaded, f, ensure_ascii=False, indent=2)
                        logger.info("[SettingsManager] Migrated settings to user directory")
                    except Exception as e:
                        logger.warning(f"[SettingsManager] Settings migration failed: {e}")

                if os.path.exists(settings_path):
                    with open(settings_path, 'r', encoding='utf-8') as f:
                        loaded = json.load(f)
                        # Merge with defaults to handle new settings
                        self._settings = {**self.DEFAULT_SETTINGS, **loaded}
                        # Settings loaded successfully
                else:
                    self._settings = self.DEFAULT_SETTINGS.copy()
                    # Using default settings (no file found)

                # Reset accidental/test watermark defaults (avoid shipping dev watermark).
                try:
                    user_cfg = bool(self._settings.get("watermark_user_configured", False))
                    enabled = bool(self._settings.get("watermark_enabled", False))
                    channel = str(self._settings.get("watermark_channel_name", "") or "").strip()
                    suspicious = (not channel) or ("?" in channel) or ("\ufffd" in channel) or (channel == "와이엠")
                    if enabled and (not user_cfg) and suspicious:
                        self._settings["watermark_enabled"] = False
                        self._settings["watermark_channel_name"] = ""
                        logger.info("[SettingsManager] Reset suspicious watermark defaults")
                        needs_save = True
                except Exception:
                    pass
        except Exception as e:
            # Settings loading failed - using defaults
            logger.warning(f"[SettingsManager] Settings loading failed: {e}")
            self._settings = self.DEFAULT_SETTINGS.copy()

        # Save outside the lock if we reset suspicious watermark defaults.
        if needs_save:
            try:
                # Only save when file already exists (avoid creating file for fresh installs).
                if os.path.exists(settings_path):
                    self._save_settings()
            except Exception:
                pass

    def _save_settings(self) -> bool:
        """Save settings to file (thread-safe)"""
        settings_path = self._get_settings_path()

        try:
            with self._lock:
                os.makedirs(os.path.dirname(settings_path), exist_ok=True)
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
            self._settings["watermark_user_configured"] = True
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
            self._settings["watermark_user_configured"] = True
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
            self._settings["watermark_user_configured"] = True
        return self._save_settings()

    def get_watermark_font_id(self) -> str:
        """Get the watermark font ID"""
        return self._settings.get("watermark_font_id", "pretendard")

    def set_watermark_font_id(self, font_id: str) -> bool:
        """
        Save the watermark font ID.

        Args:
            font_id: One of 'seoul_hangang', 'pretendard', 'gmarketsans', 'paperlogy', 'unpeople_gothic'

        Returns:
            True if save was successful
        """
        valid_fonts = ("seoul_hangang", "pretendard", "gmarketsans", "paperlogy", "unpeople_gothic")
        if font_id not in valid_fonts:
            font_id = "pretendard"
        with self._lock:
            self._settings["watermark_font_id"] = font_id
            self._settings["watermark_user_configured"] = True
        return self._save_settings()

    def get_watermark_font_size(self) -> str:
        """Get the watermark font size key"""
        return self._settings.get("watermark_font_size", "medium")

    def set_watermark_font_size(self, size: str) -> bool:
        """
        Save the watermark font size.

        Args:
            size: One of 'small', 'medium', 'large'

        Returns:
            True if save was successful
        """
        valid_sizes = ("small", "medium", "large")
        if size not in valid_sizes:
            size = "medium"
        with self._lock:
            self._settings["watermark_font_size"] = size
            self._settings["watermark_user_configured"] = True
        return self._save_settings()

    def get_watermark_settings(self) -> Dict[str, Any]:
        """Get all watermark settings as a dictionary"""
        return {
            "enabled": self.get_watermark_enabled(),
            "channel_name": self.get_watermark_channel_name(),
            "position": self.get_watermark_position(),
            "font_id": self.get_watermark_font_id(),
            "font_size": self.get_watermark_font_size(),
        }

    # ============ Subtitle Settings ============

    def get_subtitle_settings(self) -> Dict[str, Any]:
        """Get all subtitle settings as a dictionary"""
        return {
            "overlay_on_chinese": self._settings.get("subtitle_overlay_on_chinese", True),
            "position": self._settings.get("subtitle_position", "bottom_center"),
            "custom_y_percent": self._settings.get("subtitle_custom_y_percent", 80.0),
        }

    def set_subtitle_overlay_on_chinese(self, enabled: bool) -> bool:
        """Save whether to overlay Korean subtitle on Chinese subtitle position"""
        with self._lock:
            self._settings["subtitle_overlay_on_chinese"] = bool(enabled)
        return self._save_settings()

    def set_subtitle_position(self, position: str) -> bool:
        """Save Korean subtitle position"""
        valid = ("top_center", "middle_center", "bottom_center", "custom")
        if position not in valid:
            position = "bottom_center"
        with self._lock:
            self._settings["subtitle_position"] = position
        return self._save_settings()

    def set_subtitle_custom_y(self, y_percent: float) -> bool:
        """Save custom subtitle Y position (5-95%)"""
        y_percent = max(5.0, min(95.0, float(y_percent)))
        with self._lock:
            self._settings["subtitle_custom_y_percent"] = y_percent
        return self._save_settings()

    # ============ Social Media Connection Settings ============

    def get_youtube_connected(self) -> bool:
        """Get YouTube connection status"""
        return self._settings.get("youtube_connected", False)

    def set_youtube_connected(self, connected: bool, channel_id: str = "", channel_name: str = "") -> bool:
        """Save YouTube connection status"""
        with self._lock:
            self._settings["youtube_connected"] = bool(connected)
            self._settings["youtube_channel_id"] = channel_id
            self._settings["youtube_channel_name"] = channel_name
        return self._save_settings()

    def get_youtube_channel_info(self) -> Dict[str, str]:
        """Get YouTube channel info"""
        return {
            "channel_id": self._settings.get("youtube_channel_id", ""),
            "channel_name": self._settings.get("youtube_channel_name", ""),
        }

    def get_youtube_auto_upload(self) -> bool:
        """Get YouTube auto-upload enabled status"""
        return self._settings.get("youtube_auto_upload", False)

    def set_youtube_auto_upload(self, enabled: bool) -> bool:
        """Save YouTube auto-upload setting"""
        with self._lock:
            self._settings["youtube_auto_upload"] = bool(enabled)
        return self._save_settings()

    def get_youtube_upload_interval(self) -> int:
        """Get YouTube upload interval in minutes"""
        return self._settings.get("youtube_upload_interval", 60)

    def set_youtube_upload_interval(self, interval_minutes: int) -> bool:
        """Save YouTube upload interval (60, 120, 180, 240 minutes)"""
        valid_intervals = (60, 120, 180, 240)
        if interval_minutes not in valid_intervals:
            interval_minutes = 60
        with self._lock:
            self._settings["youtube_upload_interval"] = interval_minutes
        return self._save_settings()

    def get_social_connection_status(self, platform: str) -> bool:
        """Get connection status for a social platform"""
        key = f"{platform}_connected"
        return self._settings.get(key, False)

    def get_upload_settings(self) -> Dict[str, Any]:
        """Get all upload-related settings"""
        return {
            "youtube_connected": self.get_youtube_connected(),
            "youtube_channel_info": self.get_youtube_channel_info(),
            "youtube_auto_upload": self.get_youtube_auto_upload(),
            "youtube_upload_interval": self.get_youtube_upload_interval(),
            "tiktok_connected": self._settings.get("tiktok_connected", False),
            "instagram_connected": self._settings.get("instagram_connected", False),
            "threads_connected": self._settings.get("threads_connected", False),
            "x_connected": self._settings.get("x_connected", False),
            "coupang_connected": bool(self._settings.get("coupang_access_key") and self._settings.get("coupang_secret_key")),
            "inpock_connected": bool(self._settings.get("cookies_inpock")),
        }

    # ============ Upload Prompt Settings ============

    def get_platform_prompts(self, platform: str) -> Dict[str, str]:
        """Get upload prompts for a platform (title, description, hashtag)"""
        defaults = self.DEFAULT_PLATFORM_PROMPTS.get(platform, {})
        title_prompt = self._settings.get(f"{platform}_title_prompt", "")
        description_prompt = self._settings.get(f"{platform}_description_prompt", "")
        hashtag_prompt = self._settings.get(f"{platform}_hashtag_prompt", "")

        return {
            "title_prompt": str(title_prompt).strip() or defaults.get("title_prompt", ""),
            "description_prompt": str(description_prompt).strip() or defaults.get("description_prompt", ""),
            "hashtag_prompt": str(hashtag_prompt).strip() or defaults.get("hashtag_prompt", ""),
        }

    def set_platform_prompts(self, platform: str, title_prompt: str = "",
                             description_prompt: str = "", hashtag_prompt: str = "") -> bool:
        """Save upload prompts for a platform"""
        with self._lock:
            self._settings[f"{platform}_title_prompt"] = title_prompt
            self._settings[f"{platform}_description_prompt"] = description_prompt
            self._settings[f"{platform}_hashtag_prompt"] = hashtag_prompt
        return self._save_settings()

    def get_youtube_comment_enabled(self) -> bool:
        """Get YouTube comment auto-upload setting"""
        return self._settings.get("youtube_comment_enabled", False)

    def set_youtube_comment_enabled(self, enabled: bool) -> bool:
        """Save YouTube comment auto-upload setting"""
        with self._lock:
            self._settings["youtube_comment_enabled"] = bool(enabled)
        return self._save_settings()

    def get_youtube_comment_prompt(self) -> str:
        """Get YouTube auto-comment prompt"""
        return self._settings.get("youtube_comment_prompt", "")

    def set_youtube_comment_prompt(self, prompt: str) -> bool:
        """Save YouTube auto-comment prompt"""
        with self._lock:
            self._settings["youtube_comment_prompt"] = prompt
        return self._save_settings()

    # ============ Automation Settings ============

    def get_coupang_keys(self) -> Dict[str, str]:
        """Get Coupang Partners API keys"""
        return {
            "access_key": self._settings.get("coupang_access_key", ""),
            "secret_key": self._settings.get("coupang_secret_key", ""),
        }

    def set_coupang_keys(self, access_key: str, secret_key: str) -> bool:
        """Save Coupang Partners API keys"""
        with self._lock:
            self._settings["coupang_access_key"] = access_key
            self._settings["coupang_secret_key"] = secret_key
        return self._save_settings()

    def get_inpock_cookies(self) -> Dict[str, str]:
        """Get Inpock Link cookies"""
        return self._settings.get("cookies_inpock", {})

    def set_inpock_cookies(self, cookies: Dict[str, str]) -> bool:
        """Save Inpock Link cookies"""
        with self._lock:
            self._settings["cookies_inpock"] = cookies
        return self._save_settings()

    def get_1688_cookies(self) -> Dict[str, str]:
        """Get 1688 cookies"""
        return self._settings.get("cookies_1688", {})

    def set_1688_cookies(self, cookies: Dict[str, str]) -> bool:
        """Save 1688 cookies for selenium"""
        with self._lock:
            self._settings["cookies_1688"] = cookies
        return self._save_settings()

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
