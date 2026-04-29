"""
YouTube Manager for Channel Connection and Auto-Upload
유튜브 채널 연결 및 자동 업로드 매니저

Handles:
- YouTube OAuth 2.0 authentication
- Channel connection management
- Auto-upload scheduling with interval settings
- SEO-optimized title, description, hashtag generation
"""

import json
import os
import shutil
import stat
import subprocess
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

from utils.logging_config import get_logger
from utils.secrets_manager import get_secrets_manager
from managers.settings_manager import get_settings_manager

logger = get_logger(__name__)

COUPANG_AFFILIATE_DISCLOSURE = (
    "이 게시물은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)

# YouTube API imports (optional)
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False


@dataclass
class YouTubeChannel:
    """YouTube channel data structure"""
    channel_id: str = ""
    channel_name: str = ""
    thumbnail_url: str = ""
    subscriber_count: str = "0"
    video_count: str = "0"
    connected_at: str = ""


@dataclass
class AutoUploadSettings:
    """Auto-upload settings data structure"""
    enabled: bool = False
    interval_minutes: int = 30  # 업로드 간격 (분 단위)
    auto_title: bool = True  # SEO 제목 자동 생성
    auto_description: bool = True  # SEO 설명 자동 생성
    auto_hashtags: bool = True  # SEO 해시태그 자동 생성
    max_hashtags: int = 10  # 최대 해시태그 개수
    default_privacy: str = "public"  # public, unlisted, private
    category_id: str = "22"  # 22 = People & Blogs
    made_for_kids: bool = False


class YouTubeManager:
    """
    YouTube channel management and auto-upload functionality
    유튜브 채널 관리 및 자동 업로드 기능
    """

    # OAuth 2.0 scopes
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ]
    OAUTH_FLOW_TIMEOUT_SECONDS = 180
    CLIENT_SECRETS_KEY = "youtube_client_secrets_json_v1"

    def __init__(self, gui=None, settings_file: str = "youtube_settings.json"):
        """
        Initialize YouTube manager.

        Args:
            gui: VideoAnalyzerGUI instance
            settings_file: Settings file name
        """
        self.gui = gui
        self.settings_file = settings_file

        # State
        self._credentials: Optional[Any] = None
        self._youtube_service: Optional[Any] = None
        self._channel: Optional[YouTubeChannel] = None
        self._last_error_message: str = ""
        self._upload_settings = AutoUploadSettings()
        self._secrets_manager = get_secrets_manager()

        # Auto-upload thread
        self._upload_thread: Optional[threading.Thread] = None
        self._upload_queue: List[Dict[str, Any]] = []
        self._upload_running = False
        self._last_upload_time: Optional[datetime] = None

        # Callbacks
        self._on_upload_complete: Optional[Callable] = None
        self._on_upload_error: Optional[Callable] = None
        self._on_connection_changed: Optional[Callable] = None

        # Load settings
        self._load_settings()

    # ============ Settings Persistence ============

    def _get_app_base_dir(self) -> str:
        """Get base directory for app runtime files."""
        try:
            import sys
            if getattr(sys, 'frozen', False):
                return os.path.dirname(sys.executable)
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            logger.debug(f"[YouTube] 앱 기본 경로 감지 실패, cwd 사용: {e}")
            return os.getcwd()

    def _get_user_data_dir(self) -> str:
        """Get per-user writable directory for persisted app data."""
        return os.path.join(os.path.expanduser("~"), ".ssmaker")

    def _ensure_writable_dir(self, directory: str) -> None:
        """Ensure directory exists and is writable for current user."""
        if not directory:
            raise ValueError("directory path is empty")
        os.makedirs(directory, exist_ok=True)
        if os.name == "nt":
            try:
                subprocess.run(
                    ["attrib", "-R", "-H", directory],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception:
                pass

    def _get_credentials_dir(self) -> str:
        """Get protected credentials directory under user data folder."""
        return os.path.join(self._get_user_data_dir(), ".ssmaker_credentials", "youtube")

    def _get_settings_path(self) -> str:
        """Get full path to settings file"""
        return os.path.join(self._get_user_data_dir(), self.settings_file)

    def _get_legacy_settings_path(self) -> str:
        """Legacy settings location near app executable/project root."""
        return os.path.join(self._get_app_base_dir(), self.settings_file)

    def _load_settings(self) -> None:
        """Load settings from file"""
        settings_path = self._get_settings_path()
        legacy_settings_path = self._get_legacy_settings_path()

        try:
            if (not os.path.exists(settings_path)) and os.path.exists(legacy_settings_path):
                try:
                    self._ensure_writable_dir(os.path.dirname(settings_path))
                    shutil.copy2(legacy_settings_path, settings_path)
                    logger.info("[YouTube] 설정 파일을 사용자 경로로 마이그레이션했습니다.")
                except Exception as migrate_error:
                    logger.warning(
                        "[YouTube] 설정 마이그레이션 실패: %s",
                        migrate_error,
                    )

            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Load channel info
                if "channel" in data:
                    ch = data["channel"]
                    self._channel = YouTubeChannel(
                        channel_id=ch.get("channel_id", ""),
                        channel_name=ch.get("channel_name", ""),
                        thumbnail_url=ch.get("thumbnail_url", ""),
                        subscriber_count=ch.get("subscriber_count", "0"),
                        video_count=ch.get("video_count", "0"),
                        connected_at=ch.get("connected_at", "")
                    )

                # Load upload settings
                if "upload_settings" in data:
                    us = data["upload_settings"]
                    self._upload_settings = AutoUploadSettings(
                        enabled=us.get("enabled", False),
                        interval_minutes=us.get("interval_minutes", 30),
                        auto_title=us.get("auto_title", True),
                        auto_description=us.get("auto_description", True),
                        auto_hashtags=us.get("auto_hashtags", True),
                        max_hashtags=us.get("max_hashtags", 10),
                        default_privacy=us.get("default_privacy", "public"),
                        category_id=us.get("category_id", "22"),
                        made_for_kids=us.get("made_for_kids", False)
                    )

                logger.debug("[YouTube] 설정 로드 완료")
                self._sync_settings_manager_state()
        except Exception as e:
            logger.error(f"[YouTube] 설정 로드 실패: {e}")

    def _sync_settings_manager_state(self) -> None:
        """Keep the shared SettingsManager in sync with this manager state."""
        try:
            settings = get_settings_manager()
            connected = bool(
                self._channel
                and self._channel.channel_id
                and os.path.exists(self._get_token_path())
            )
            if connected:
                settings.set_youtube_connected(
                    True,
                    self._channel.channel_id,
                    self._channel.channel_name,
                )
            else:
                settings.set_youtube_connected(False, "", "")
            settings.set_youtube_auto_upload(bool(self._upload_settings.enabled))
        except Exception as exc:
            logger.debug("[YouTube] SettingsManager sync skipped: %s", exc)

    def _save_settings(self) -> bool:
        """Save settings to file"""
        settings_path = self._get_settings_path()

        try:
            self._ensure_writable_dir(os.path.dirname(settings_path))
            data = {
                "channel": {
                    "channel_id": self._channel.channel_id if self._channel else "",
                    "channel_name": self._channel.channel_name if self._channel else "",
                    "thumbnail_url": self._channel.thumbnail_url if self._channel else "",
                    "subscriber_count": self._channel.subscriber_count if self._channel else "0",
                    "video_count": self._channel.video_count if self._channel else "0",
                    "connected_at": self._channel.connected_at if self._channel else ""
                },
                "upload_settings": {
                    "enabled": self._upload_settings.enabled,
                    "interval_minutes": self._upload_settings.interval_minutes,
                    "auto_title": self._upload_settings.auto_title,
                    "auto_description": self._upload_settings.auto_description,
                    "auto_hashtags": self._upload_settings.auto_hashtags,
                    "max_hashtags": self._upload_settings.max_hashtags,
                    "default_privacy": self._upload_settings.default_privacy,
                    "category_id": self._upload_settings.category_id,
                    "made_for_kids": self._upload_settings.made_for_kids
                }
            }

            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug("[YouTube] 설정 저장 완료")
            return True
        except Exception as e:
            logger.error(f"[YouTube] 설정 저장 실패: {e}")
            return False

    # ============ OAuth Connection ============

    def is_connected(self) -> bool:
        """Check if YouTube channel is connected"""
        return self._channel is not None and self._channel.channel_id != ""

    def get_channel_info(self) -> Dict[str, Any]:
        """Get connected channel info as dictionary"""
        if self._channel is None:
            return {}
        return {
            "id": self._channel.channel_id,
            "title": self._channel.channel_name,
            "channel_name": self._channel.channel_name,
            "thumbnail_url": self._channel.thumbnail_url,
            "subscriber_count": self._channel.subscriber_count,
            "video_count": self._channel.video_count,
            "connected_at": self._channel.connected_at,
        }

    def get_last_error(self) -> str:
        """Return the latest YouTube connection error message."""
        return self._last_error_message

    def connect_channel(
        self,
        client_secrets_file: str = None,
        oauth_timeout_seconds: Optional[int] = None
    ) -> bool:
        """
        Connect to YouTube channel using OAuth 2.0.

        Args:
            client_secrets_file: Path to OAuth client secrets file
            oauth_timeout_seconds: OAuth callback wait timeout in seconds

        Returns:
            True if connection successful
        """
        self._last_error_message = ""
        if not YOUTUBE_API_AVAILABLE:
            logger.warning("[YouTube] YouTube API library is not installed.")
            self._last_error_message = "YouTube API 라이브러리가 설치되지 않았습니다."
            return False

        try:
            self._migrate_legacy_oauth_files()

            # Check for existing credentials
            token_path = self._get_token_path()
            creds = None

            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
                try:
                    has_scopes = bool(getattr(creds, "has_scopes", None))
                    if has_scopes and not creds.has_scopes(self.SCOPES):
                        logger.info("[YouTube] OAuth 권한(scope) 업데이트로 재인증이 필요합니다.")
                        creds = None
                except Exception:
                    # If scope introspection fails, proceed with normal refresh/login flow.
                    pass

            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    oauth_config = self._load_client_secret_config_securely()
                    if oauth_config is None:
                        if not client_secrets_file:
                            client_secrets_file = self._get_client_secrets_path()

                        if not os.path.exists(client_secrets_file):
                            legacy_secrets_path = self._get_legacy_client_secrets_path()
                            if os.path.exists(legacy_secrets_path):
                                try:
                                    client_secrets_file = self.install_client_secrets(legacy_secrets_path)
                                except Exception as migrate_error:
                                    logger.debug(f"[YouTube] 레거시 OAuth 파일 마이그레이션 실패: {migrate_error}")

                        if not os.path.exists(client_secrets_file):
                            logger.warning("[YouTube] OAuth client secrets file is missing.")
                            self._last_error_message = "OAuth 클라이언트 JSON 파일을 찾을 수 없습니다."
                            return False

                        oauth_config = self._load_client_secret_config_from_file(client_secrets_file)
                        if not oauth_config:
                            self._last_error_message = "OAuth JSON 형식이 올바르지 않습니다."
                            return False
                        self._store_client_secret_config_securely(oauth_config)

                    flow = InstalledAppFlow.from_client_config(
                        oauth_config, self.SCOPES
                    )
                    timeout_seconds = (
                        oauth_timeout_seconds
                        if oauth_timeout_seconds is not None
                        else self.OAUTH_FLOW_TIMEOUT_SECONDS
                    )
                    creds = flow.run_local_server(
                        port=0,
                        timeout_seconds=timeout_seconds
                    )

                # Save credentials
                self._ensure_writable_dir(os.path.dirname(token_path))
                with open(token_path, "w", encoding="utf-8") as token:
                    token.write(creds.to_json())

            self._credentials = creds

            # Build YouTube service
            self._youtube_service = build('youtube', 'v3', credentials=creds)

            # Get channel info
            self._fetch_channel_info()

            # Notify callback
            if self._on_connection_changed:
                self._on_connection_changed(True)

            return True

        except PermissionError as e:
            logger.error("[YouTube] Connection permission error: %s", e)
            self._last_error_message = (
                "OAuth 파일 저장 권한이 없어 연결에 실패했습니다.\n"
                "앱을 다시 실행한 뒤 다시 시도해주세요."
            )
            return False
        except Exception as e:
            logger.error("[YouTube] Connection failed: %s", e)
            self._last_error_message = str(e) or "YouTube 채널 연결 중 알 수 없는 오류가 발생했습니다."
            return False

    def disconnect_channel(self) -> None:
        """Disconnect YouTube channel"""
        self._credentials = None
        self._youtube_service = None
        self._channel = None

        # Remove token file
        token_path = self._get_token_path()
        if os.path.exists(token_path):
            try:
                os.remove(token_path)
            except Exception as e:
                logger.debug(f"[YouTube] 토큰 파일 삭제 실패: {e}")

        self._save_settings()
        self._sync_settings_manager_state()

        # Stop auto-upload
        self.stop_auto_upload()

        # Notify callback
        if self._on_connection_changed:
            self._on_connection_changed(False)

    def _get_token_path(self) -> str:
        """Get OAuth token file path"""
        return os.path.join(self._get_user_data_dir(), "youtube_token.json")

    def _get_legacy_token_path(self) -> str:
        """Legacy OAuth token path stored next to executable/project root."""
        return os.path.join(self._get_app_base_dir(), "youtube_token.json")

    def _get_client_secrets_path(self) -> str:
        """Get OAuth client secrets file path"""
        return os.path.join(self._get_credentials_dir(), "client_secrets.json")

    def _get_legacy_managed_client_secrets_path(self) -> str:
        """Legacy managed OAuth file path under app base directory."""
        return os.path.join(self._get_app_base_dir(), ".ssmaker_credentials", "youtube", "client_secrets.json")

    def _get_legacy_client_secrets_path(self) -> str:
        """Get old client_secrets.json location in app root."""
        return os.path.join(self._get_app_base_dir(), "client_secrets.json")

    @staticmethod
    def _is_valid_client_secret_config(config: Dict[str, Any]) -> bool:
        """Validate minimal OAuth client JSON schema."""
        if not isinstance(config, dict):
            return False
        installed = config.get("installed") or config.get("web")
        if not isinstance(installed, dict):
            return False
        return bool(installed.get("client_id")) and bool(installed.get("client_secret"))

    def _load_client_secret_config_from_file(self, source_path: str) -> Optional[Dict[str, Any]]:
        """Load OAuth client config from JSON file."""
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.debug("[YouTube] Failed to load OAuth JSON %s: %s", source_path, e)
            return None
        if not self._is_valid_client_secret_config(data):
            logger.warning("[YouTube] Invalid OAuth JSON format: %s", source_path)
            return None
        return data

    def _store_client_secret_config_securely(self, config: Dict[str, Any]) -> bool:
        """Store OAuth client config in secure storage."""
        if not self._is_valid_client_secret_config(config):
            return False
        try:
            payload = json.dumps(config, ensure_ascii=False)
            return bool(self._secrets_manager.set_credential(self.CLIENT_SECRETS_KEY, payload))
        except Exception as e:
            logger.debug("[YouTube] Failed to store OAuth config securely: %s", e)
            return False

    def _load_client_secret_config_securely(self) -> Optional[Dict[str, Any]]:
        """Load OAuth client config from secure storage."""
        try:
            payload = self._secrets_manager.get_credential(self.CLIENT_SECRETS_KEY)
            if not payload:
                return None
            data = json.loads(payload)
        except Exception as e:
            logger.debug("[YouTube] Failed to read secure OAuth config: %s", e)
            return None
        if not self._is_valid_client_secret_config(data):
            return None
        return data

    def _make_path_writable(self, path: str) -> None:
        """Best-effort clear read-only attributes so updates can replace file."""
        if not path or not os.path.exists(path):
            return

        try:
            mode = stat.S_IREAD | stat.S_IWRITE
            if os.path.isdir(path):
                mode |= stat.S_IEXEC
            os.chmod(path, mode)
        except Exception:
            pass

        if os.name == "nt":
            try:
                subprocess.run(
                    ["attrib", "-R", "-H", path],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception:
                pass

    def _copy_file_best_effort(self, source_path: str, destination_path: str, label: str) -> bool:
        """Copy file with best-effort writable handling for legacy migration."""
        if not source_path or not destination_path:
            return False
        if not os.path.isfile(source_path):
            return False

        try:
            self._ensure_writable_dir(os.path.dirname(destination_path))
            self._make_path_writable(destination_path)
            shutil.copy2(source_path, destination_path)
            logger.info("[YouTube] %s 마이그레이션 완료: %s", label, destination_path)
            return True
        except Exception as e:
            logger.debug("[YouTube] %s 마이그레이션 실패: %s", label, e)
            return False

    def _migrate_legacy_oauth_files(self) -> None:
        """Migrate OAuth artifacts from legacy app-root paths to user profile path."""
        token_path = self._get_token_path()
        if not os.path.exists(token_path):
            self._copy_file_best_effort(
                self._get_legacy_token_path(),
                token_path,
                "OAuth 토큰",
            )

        if self._load_client_secret_config_securely():
            return

        for legacy_path in (
            self._get_client_secrets_path(),
            self._get_legacy_managed_client_secrets_path(),
            self._get_legacy_client_secrets_path(),
        ):
            if not os.path.exists(legacy_path):
                continue
            config = self._load_client_secret_config_from_file(legacy_path)
            if not config:
                continue
            if self._store_client_secret_config_securely(config):
                try:
                    self._make_path_writable(legacy_path)
                    os.remove(legacy_path)
                except Exception:
                    pass
                break

    def _protect_credentials_file(self, path: str) -> None:
        """Apply basic protection flags to credentials file."""
        try:
            os.chmod(path, stat.S_IREAD)
        except Exception as e:
            logger.debug(f"[YouTube] OAuth 파일 읽기 전용 설정 실패: {e}")

        if os.name == "nt":
            try:
                subprocess.run(
                    ["attrib", "+H", "+R", path],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                subprocess.run(
                    ["attrib", "+H", os.path.dirname(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception as e:
                logger.debug(f"[YouTube] OAuth 파일 hidden/readonly 속성 설정 실패: {e}")

    def install_client_secrets(self, source_path: str) -> str:
        """
        Validate and store OAuth client secrets in secure storage.

        Args:
            source_path: User-selected source json file path.

        Returns:
            Logical managed path used for compatibility.

        Raises:
            FileNotFoundError: source file missing.
            OSError: secure store operation failed.
        """
        if not source_path or not os.path.exists(source_path):
            raise FileNotFoundError("OAuth JSON 파일을 찾을 수 없습니다.")

        if os.path.isdir(source_path):
            inferred = os.path.join(source_path, "client_secrets.json")
            if os.path.isfile(inferred):
                source_path = inferred
            else:
                raise FileNotFoundError("선택한 경로에 client_secrets.json 파일이 없습니다.")

        if not os.path.isfile(source_path):
            raise FileNotFoundError("OAuth JSON 파일 경로가 올바르지 않습니다.")

        source_abs = os.path.abspath(source_path)
        config = self._load_client_secret_config_from_file(source_abs)
        if not config:
            raise OSError("OAuth JSON 형식이 올바르지 않습니다.")

        if not self._store_client_secret_config_securely(config):
            raise OSError("OAuth JSON을 안전 저장소에 저장하지 못했습니다.")

        # Remove plaintext managed file if it exists.
        destination_abs = os.path.abspath(self._get_client_secrets_path())
        try:
            if os.path.exists(destination_abs):
                self._make_path_writable(destination_abs)
                os.remove(destination_abs)
        except Exception:
            pass

        logger.info("[YouTube] OAuth JSON securely stored (keyring/encrypted storage)")
        return destination_abs

    def _fetch_channel_info(self) -> None:
        """Fetch connected channel information"""
        if not self._youtube_service:
            return

        try:
            response = self._youtube_service.channels().list(
                part="snippet,statistics",
                mine=True
            ).execute()

            if response.get("items"):
                item = response["items"][0]
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})

                self._channel = YouTubeChannel(
                    channel_id=item.get("id", ""),
                    channel_name=snippet.get("title", ""),
                    thumbnail_url=snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                    subscriber_count=stats.get("subscriberCount", "0"),
                    video_count=stats.get("videoCount", "0"),
                    connected_at=datetime.now().isoformat()
                )

                self._save_settings()
                self._sync_settings_manager_state()
                logger.info(f"[YouTube] 채널 연결: {self._channel.channel_name}")

        except Exception as e:
            logger.error(f"[YouTube] 채널 정보 조회 실패: {e}")

    # ============ Upload Settings ============

    def get_upload_settings(self) -> AutoUploadSettings:
        """Get auto-upload settings"""
        return self._upload_settings

    def set_upload_enabled(self, enabled: bool) -> None:
        """Enable/disable auto-upload"""
        self._upload_settings.enabled = enabled
        self._save_settings()
        try:
            get_settings_manager().set_youtube_auto_upload(enabled)
        except Exception as exc:
            logger.debug("[YouTube] Failed to sync auto-upload setting: %s", exc)

        if enabled:
            self.start_auto_upload()
        else:
            self.stop_auto_upload()

    def set_upload_interval(self, minutes: int) -> None:
        """Set upload interval in minutes"""
        self._upload_settings.interval_minutes = max(1, min(1440, minutes))  # 1분 ~ 24시간
        self._save_settings()

    def set_seo_settings(
        self,
        auto_title: bool = True,
        auto_description: bool = True,
        auto_hashtags: bool = True,
        max_hashtags: int = 10
    ) -> None:
        """Set SEO auto-generation settings"""
        self._upload_settings.auto_title = auto_title
        self._upload_settings.auto_description = auto_description
        self._upload_settings.auto_hashtags = auto_hashtags
        self._upload_settings.max_hashtags = max_hashtags
        self._save_settings()

    def set_privacy_settings(self, privacy: str, made_for_kids: bool = False) -> None:
        """Set default privacy settings"""
        if privacy in ("public", "unlisted", "private"):
            self._upload_settings.default_privacy = privacy
        self._upload_settings.made_for_kids = made_for_kids
        self._save_settings()

    # ============ SEO Generation ============

    def generate_seo_title(self, product_info: str, max_length: int = 100) -> str:
        """
        Generate SEO-optimized title for YouTube Shorts.

        Args:
            product_info: Product description or translation text
            max_length: Maximum title length

        Returns:
            SEO-optimized title
        """
        if not product_info:
            return "쇼핑 추천 영상"

        # Extract keywords from product info
        import re
        words = re.findall(r'[가-힣a-zA-Z0-9]+', product_info)

        # Filter out common stop words
        stop_words = {'이', '그', '저', '것', '수', '등', '및', '를', '을', '가', '에서', '으로'}
        keywords = [w for w in words if w not in stop_words and len(w) > 1][:5]

        # Build title with hooks
        hooks = [
            "꿀템 발견!",
            "이거 대박!",
            "충격 가격!",
            "완전 추천!",
            "필수템!",
            "갓성비!",
        ]

        import random
        hook = random.choice(hooks)

        keyword_str = " ".join(keywords[:3])
        title = f"{hook} {keyword_str}"

        # Trim to max length
        if len(title) > max_length:
            title = title[:max_length - 3] + "..."

        return title

    def generate_seo_description(self, product_info: str, url: str = "") -> str:
        """
        Generate SEO-optimized description.

        Args:
            product_info: Product description
            url: Source URL

        Returns:
            SEO-optimized description
        """
        purchase_link = str(url or "").strip()
        lines = [
            product_info[:200] if product_info else "쇼핑 추천 영상입니다.",
            "",
            "👆 자세한 상품 정보는 아래 링크에서 확인하세요.",
            "",
            "📱 좋아요와 구독 부탁드립니다!",
            "",
        ]

        if purchase_link:
            lines.append(f"🛒 상품 보기: {purchase_link}")

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "🎬 AI 쇼핑 쇼츠 메이커로 제작",
            "━━━━━━━━━━━━━━━━━━━━",
        ])

        description = "\n".join(lines)
        if self._is_coupang_url(purchase_link):
            description = self.ensure_coupang_affiliate_compliance(description, purchase_link)
        return description

    @staticmethod
    def ensure_coupang_affiliate_compliance(description: str, purchase_link: str = "") -> str:
        """Ensure Coupang affiliate disclosure + purchase link are visible."""
        desc = str(description or "").strip()
        link = str(purchase_link or "").strip()

        if COUPANG_AFFILIATE_DISCLOSURE not in desc:
            desc = f"{COUPANG_AFFILIATE_DISCLOSURE}\n\n{desc}" if desc else COUPANG_AFFILIATE_DISCLOSURE

        if link and link not in desc:
            desc = f"{desc}\n\n🛒 쿠팡 상품 보기: {link}"

        return desc.strip()

    def generate_seo_hashtags(self, product_info: str, max_count: int = 10) -> List[str]:
        """
        Generate SEO-optimized hashtags.

        Args:
            product_info: Product description
            max_count: Maximum number of hashtags

        Returns:
            List of hashtags (without # prefix)
        """
        # Base hashtags for shopping shorts
        base_tags = [
            "쇼핑", "추천", "꿀템", "쇼츠", "shorts",
            "리뷰", "할인", "핫딜", "갓성비"
        ]

        # Extract keywords from product
        import re
        if product_info:
            words = re.findall(r'[가-힣a-zA-Z]+', product_info)
            keywords = [w for w in words if len(w) >= 2][:5]
        else:
            keywords = []

        # Combine and deduplicate
        all_tags = keywords + base_tags
        seen = set()
        unique_tags = []
        for tag in all_tags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                unique_tags.append(tag)

        return unique_tags[:max_count]

    # ============ Auto-Upload ============

    def add_to_upload_queue(
        self,
        video_path: str,
        title: str = "",
        description: str = "",
        tags: List[str] = None,
        product_info: str = "",
        source_url: str = "",
        coupang_deep_link: str = "",
        linktree_url: str = "",
    ) -> None:
        """
        Add video to upload queue.

        Args:
            video_path: Path to video file
            title: Video title (auto-generated if empty and enabled)
            description: Video description (auto-generated if empty and enabled)
            tags: Video tags (auto-generated if empty and enabled)
            product_info: Product information for SEO generation
            source_url: Source URL
            linktree_url: Public Linktree profile URL for the auto-comment
        """
        # Generate SEO content if enabled and not provided
        if not title and self._upload_settings.auto_title:
            title = self.generate_seo_title(product_info)

        if not description and self._upload_settings.auto_description:
            description = self.generate_seo_description(product_info, source_url)

        purchase_link = coupang_deep_link or source_url
        if self._is_coupang_url(purchase_link) or self._is_coupang_url(source_url):
            description = self.ensure_coupang_affiliate_compliance(description, purchase_link)

        if not tags and self._upload_settings.auto_hashtags:
            tags = self.generate_seo_hashtags(product_info, self._upload_settings.max_hashtags)

        self._upload_queue.append({
            "video_path": video_path,
            "title": title or "쇼핑 추천 영상",
            "description": description or "",
            "tags": tags or [],
            "product_info": product_info or "",
            "source_url": source_url or "",
            "coupang_deep_link": coupang_deep_link or "",
            "linktree_url": linktree_url or "",
            "added_at": datetime.now().isoformat()
        })

        logger.info(f"[YouTube] 업로드 대기열 추가: {title}")

    def start_auto_upload(self) -> None:
        """Start auto-upload background thread"""
        if self._upload_running:
            return

        if not self.is_connected():
            logger.warning("[YouTube] 채널이 연결되지 않았습니다.")
            return

        self._upload_running = True
        self._upload_thread = threading.Thread(target=self._upload_loop, daemon=True)
        self._upload_thread.start()
        logger.info("[YouTube] 자동 업로드 시작")

    def stop_auto_upload(self) -> None:
        """Stop auto-upload background thread"""
        self._upload_running = False
        logger.info("[YouTube] 자동 업로드 중지")

    def _upload_loop(self) -> None:
        """Auto-upload background loop"""
        while self._upload_running and self._upload_settings.enabled:
            try:
                # Check interval
                if self._last_upload_time:
                    elapsed = (datetime.now() - self._last_upload_time).total_seconds()
                    wait_seconds = self._upload_settings.interval_minutes * 60 - elapsed
                    if wait_seconds > 0:
                        time.sleep(min(wait_seconds, 10))  # Check every 10 seconds
                        continue

                # Process queue
                if self._upload_queue:
                    item = self._upload_queue.pop(0)
                    success = self._upload_video(item)

                    if success:
                        self._last_upload_time = datetime.now()
                        if self._on_upload_complete:
                            self._on_upload_complete(item)
                    else:
                        # Put back to queue on failure
                        self._upload_queue.insert(0, item)
                        if self._on_upload_error:
                            self._on_upload_error(item, "Upload failed")

                time.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"[YouTube] 자동 업로드 오류: {e}")
                time.sleep(30)

    def _upload_video(self, item: Dict[str, Any]) -> bool:
        """
        Upload a single video to YouTube.

        Args:
            item: Upload queue item

        Returns:
            True if upload successful
        """
        if not self._youtube_service:
            return False

        video_path = item.get("video_path", "")
        if not os.path.exists(video_path):
            logger.warning(f"[YouTube] 비디오 파일 없음: {video_path}")
            return False

        try:
            # Add hashtags to description
            tags = item.get("tags", [])
            hashtag_str = " ".join([f"#{tag}" for tag in tags])
            description = item.get("description", "")
            purchase_link = item.get("coupang_deep_link") or item.get("source_url") or ""
            if self._is_coupang_url(purchase_link):
                description = self.ensure_coupang_affiliate_compliance(description, purchase_link)
            if hashtag_str:
                description = f"{description}\n\n{hashtag_str}"

            body = {
                "snippet": {
                    "title": item.get("title", "쇼핑 추천 영상"),
                    "description": description,
                    "tags": tags,
                    "categoryId": self._upload_settings.category_id
                },
                "status": {
                    "privacyStatus": self._upload_settings.default_privacy,
                    "selfDeclaredMadeForKids": self._upload_settings.made_for_kids
                }
            }

            media = MediaFileUpload(
                video_path,
                chunksize=1024 * 1024,
                resumable=True
            )

            request = self._youtube_service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.debug(f"[YouTube] 업로드 진행: {int(status.progress() * 100)}%")

            video_id = response.get("id", "")
            logger.info(f"[YouTube] 업로드 완료: https://youtu.be/{video_id}")

            if video_id:
                item["video_id"] = video_id
                item["video_url"] = f"https://youtu.be/{video_id}"
                self._try_post_auto_comment(video_id, item)
            return True

        except Exception as e:
            logger.error(f"[YouTube] 업로드 실패: {e}")
            return False

    @staticmethod
    def _is_coupang_url(url: str) -> bool:
        return "coupang.com" in str(url or "").lower()

    @staticmethod
    def _trim_comment_text(text: str, limit: int = 10000) -> str:
        cleaned = str(text or "").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."

    def _render_comment_template(
        self,
        template: str,
        purchase_link: str,
        original_link: str,
        product_description: str = "",
        linktree_link: str = "",
    ) -> str:
        replacements = {
            "{구매링크}": purchase_link,
            "{쿠팡링크}": purchase_link,
            "{딥링크}": purchase_link,
            "{purchase_link}": purchase_link,
            "{원상품링크}": original_link,
            "{쿠팡원상품링크}": original_link,
            "{original_link}": original_link,
            "{상품설명}": product_description,
            "{상품 설명}": product_description,
            "{product_description}": product_description,
            "{링크트리}": linktree_link,
            "{링크트리링크}": linktree_link,
            "{linktree_link}": linktree_link,
        }

        rendered = str(template or "")
        for token, value in replacements.items():
            rendered = rendered.replace(token, value or "")
        return rendered.strip()

    @staticmethod
    def _field_has_comment_placeholder(raw_prompt: str, tokens: List[str]) -> bool:
        return any(token in raw_prompt for token in tokens)

    def _resolve_comment_linktree_url(self, settings: Any, item: Dict[str, Any]) -> str:
        for key in ("linktree_url", "linktree_profile_url"):
            value = str(item.get(key, "") or "").strip()
            if value:
                return value

        try:
            if hasattr(settings, "get_linktree_settings"):
                linktree_settings = settings.get_linktree_settings() or {}
                profile_url = str(linktree_settings.get("profile_url", "") or "").strip()
                if profile_url:
                    return profile_url
        except Exception as exc:
            logger.debug("[YouTube] Linktree profile lookup skipped: %s", exc)

        description = str(item.get("description", "") or "")
        try:
            import re
            match = re.search(r"https?://(?:www\.)?linktr\.ee/[^\s)>\]]+", description)
            if match:
                return match.group(0).rstrip(".,")
        except Exception:
            pass
        return ""

    @staticmethod
    def _build_comment_product_description(item: Dict[str, Any], limit: int = 220) -> str:
        raw = (
            item.get("product_description")
            or item.get("product_info")
            or item.get("product_name")
            or item.get("title")
            or ""
        )
        text = " ".join(str(raw or "").split())
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."

    def _resolve_comment_original_link(self, item: Dict[str, Any]) -> str:
        settings = get_settings_manager()
        manual_link = settings.get_youtube_comment_manual_product_link()
        if manual_link:
            return manual_link

        source_url = str(item.get("source_url", "")).strip()
        if self._is_coupang_url(source_url):
            return source_url
        return ""

    def _build_auto_comment_text(self, item: Dict[str, Any]) -> str:
        settings = get_settings_manager()
        comment_enabled = bool(
            settings.get_youtube_comment_enabled()
            if hasattr(settings, "get_youtube_comment_enabled")
            else False
        )
        raw_prompt = (
            settings.get_youtube_comment_prompt().strip()
            if comment_enabled and hasattr(settings, "get_youtube_comment_prompt")
            else ""
        )
        purchase_link = str(item.get("coupang_deep_link", "")).strip()
        original_link = self._resolve_comment_original_link(item)
        product_description = self._build_comment_product_description(item)
        linktree_link = self._resolve_comment_linktree_url(settings, item)

        has_shopping_context = any(
            (product_description, purchase_link, original_link, linktree_link)
        )
        if not comment_enabled and not has_shopping_context:
            return ""

        prompt_with_tokens = self._render_comment_template(
            raw_prompt,
            purchase_link=purchase_link or original_link,
            original_link=original_link,
            product_description=product_description,
            linktree_link=linktree_link,
        )

        purchase_tokens = ("{구매링크}", "{쿠팡링크}", "{딥링크}", "{purchase_link}")
        original_tokens = ("{원상품링크}", "{쿠팡원상품링크}", "{original_link}")
        product_tokens = ("{상품설명}", "{상품 설명}", "{product_description}")
        linktree_tokens = ("{링크트리}", "{링크트리링크}", "{linktree_link}")

        has_purchase_placeholder = self._field_has_comment_placeholder(
            raw_prompt, list(purchase_tokens)
        )
        has_original_placeholder = self._field_has_comment_placeholder(
            raw_prompt, list(original_tokens)
        )
        has_product_placeholder = self._field_has_comment_placeholder(
            raw_prompt, list(product_tokens)
        )
        has_linktree_placeholder = self._field_has_comment_placeholder(
            raw_prompt, list(linktree_tokens)
        )

        if not prompt_with_tokens:
            prompt_with_tokens = "영상에서 소개한 상품 정보를 공유드립니다."

        extra_lines = []
        if product_description and not has_product_placeholder:
            extra_lines.append(f"상품 설명: {product_description}")
        if purchase_link and not has_purchase_placeholder:
            extra_lines.append(f"구매 링크: {purchase_link}")
        if linktree_link and not has_linktree_placeholder:
            extra_lines.append(f"Linktree: {linktree_link}")
        if (
            original_link
            and original_link != purchase_link
            and not has_original_placeholder
        ):
            extra_lines.append(f"원상품 링크: {original_link}")

        if extra_lines:
            text = f"{prompt_with_tokens}\n\n" + "\n".join(extra_lines)
        else:
            text = prompt_with_tokens

        return self._trim_comment_text(text)

    def _post_top_level_comment(self, video_id: str, text: str) -> bool:
        if not self._youtube_service or not video_id or not text:
            return False

        try:
            request = self._youtube_service.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {
                                "textOriginal": text,
                            }
                        },
                    }
                },
            )
            request.execute()
            return True
        except Exception as e:
            logger.warning(f"[YouTube] 자동 댓글 등록 실패: {e}")
            return False

    def _try_post_auto_comment(self, video_id: str, item: Dict[str, Any]) -> None:
        comment_text = self._build_auto_comment_text(item)
        if not comment_text:
            return

        if self._post_top_level_comment(video_id, comment_text):
            logger.info("[YouTube] 자동 댓글 등록 완료: %s", video_id)

    # ============ Callbacks ============

    def set_on_upload_complete(self, callback: Callable) -> None:
        """Set callback for upload completion"""
        self._on_upload_complete = callback

    def set_on_upload_error(self, callback: Callable) -> None:
        """Set callback for upload error"""
        self._on_upload_error = callback

    def set_on_connection_changed(self, callback: Callable) -> None:
        """Set callback for connection state change"""
        self._on_connection_changed = callback

    # ============ Status ============

    def get_queue_count(self) -> int:
        """Get number of videos in upload queue"""
        return len(self._upload_queue)

    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            "connected": self.is_connected(),
            "channel_name": self._channel.channel_name if self._channel else "",
            "auto_upload_enabled": self._upload_settings.enabled,
            "upload_interval_minutes": self._upload_settings.interval_minutes,
            "queue_count": len(self._upload_queue),
            "is_uploading": self._upload_running
        }


# Global instance
_youtube_manager: Optional[YouTubeManager] = None


def get_youtube_manager(gui=None) -> YouTubeManager:
    """Get global YouTube manager instance"""
    global _youtube_manager
    if _youtube_manager is None:
        _youtube_manager = YouTubeManager(gui=gui)
    return _youtube_manager
