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
import re
import shutil
import stat
import subprocess
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

import requests

from utils.logging_config import get_logger
from utils.secrets_manager import get_secrets_manager
from managers.settings_manager import get_settings_manager

logger = get_logger(__name__)

COUPANG_AFFILIATE_DISCLOSURE = (
    "이 게시물은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)
COUPANG_PAID_PROMOTION_TITLE_MARKER = "[광고]"
COUPANG_PARTNERS_NOTICE_98_URL = "https://partners.coupang.com/#announcements/98"

DEFAULT_HASHTAG_POOL = [
    "쇼핑추천",
    "꿀템",
    "추천템",
    "핫딜",
    "쇼츠",
    "shorts",
]

HASHTAG_STOPWORDS = {
    "이", "그", "저", "것", "수", "및", "에서", "으로", "그리고", "하지만",
    "영상", "소개", "상품", "정보", "확인", "아래", "바로", "지금", "정말",
    "완전", "추천", "구매", "링크", "클릭", "해요", "하세요", "합니다", "입니다",
    "the", "and", "for", "with", "from", "this", "that", "video", "item",
    "product", "link", "shop", "shopping",
    "틀어도", "안이", "이제", "바로", "후끈후끈", "후끈후끈하시죠",
}

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
    account_email: str = ""
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
        "openid",
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl",
        "https://www.googleapis.com/auth/userinfo.email",
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
                        account_email=str(ch.get("account_email", "") or "").strip().lower(),
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
                    self._channel.account_email or None,
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
                    "account_email": self._channel.account_email if self._channel else "",
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
            "account_email": self._channel.account_email,
            "thumbnail_url": self._channel.thumbnail_url,
            "subscriber_count": self._channel.subscriber_count,
            "video_count": self._channel.video_count,
            "connected_at": self._channel.connected_at,
            "channel_url": self.get_channel_url(),
        }

    def get_channel_url(self) -> str:
        """Return a stable YouTube channel URL for Coupang Partners review."""
        if not self._channel or not self._channel.channel_id:
            return ""
        return f"https://www.youtube.com/channel/{self._channel.channel_id}"

    def get_last_error(self) -> str:
        """Return the latest YouTube connection error message."""
        return self._last_error_message

    def _fetch_oauth_account_email(self, creds: Optional[Any] = None) -> str:
        """Return the Google account email granted to the OAuth token, if available."""
        creds = creds or self._credentials
        token = str(getattr(creds, "token", "") or "").strip()
        if not token:
            return ""
        try:
            response = requests.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if response.status_code != 200:
                logger.debug(
                    "[YouTube] OAuth account email lookup failed: status=%s body=%s",
                    response.status_code,
                    response.text[:200],
                )
                return ""
            payload = response.json() if response.content else {}
            return str(payload.get("email", "") or "").strip().lower()
        except Exception as exc:
            logger.debug("[YouTube] OAuth account email lookup skipped: %s", exc)
            return ""

    def _account_guard_message(self) -> str:
        """Return a blocking message when configured account verification fails."""
        try:
            settings = get_settings_manager()
            if self._channel and self._channel.account_email:
                settings.set_youtube_account_email(self._channel.account_email)
            verification = settings.get_youtube_account_verification()
            if verification.get("required") and not verification.get("ok"):
                return str(verification.get("message") or "YouTube 계정 이메일 확인이 필요합니다.")
        except Exception as exc:
            logger.debug("[YouTube] Account verification skipped: %s", exc)
        return ""

    def get_account_verification_status(self) -> Dict[str, Any]:
        """Return current YouTube OAuth account verification state."""
        try:
            if self._channel and self._channel.account_email:
                get_settings_manager().set_youtube_account_email(self._channel.account_email)
            return get_settings_manager().get_youtube_account_verification()
        except Exception as exc:
            return {
                "required": False,
                "ok": False,
                "expected": "",
                "actual": "",
                "message": f"YouTube 계정 검증 상태를 확인하지 못했습니다: {exc}",
            }

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
                    try:
                        creds.refresh(Request())
                    except Exception as refresh_error:
                        if "invalid_grant" not in str(refresh_error):
                            raise
                        logger.info("[YouTube] OAuth 토큰이 만료/폐기되어 재인증을 진행합니다.")
                        try:
                            os.remove(token_path)
                        except OSError:
                            pass
                        creds = None

                if not creds or not creds.valid:
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
                    auth_kwargs = {}
                    if os.environ.get("YOUTUBE_OAUTH_SELECT_ACCOUNT", "1").lower() not in {
                        "0",
                        "false",
                        "no",
                    }:
                        auth_kwargs["prompt"] = "consent select_account"

                    try:
                        creds = flow.run_local_server(
                            port=0,
                            timeout_seconds=timeout_seconds,
                            **auth_kwargs,
                        )
                    except Exception as oauth_error:
                        if "NoneType" in str(oauth_error) and "replace" in str(oauth_error):
                            self._last_error_message = (
                                "YouTube OAuth 승인이 완료되지 않았습니다. "
                                "브라우저에서 Google 계정 승인 후 다시 시도하세요."
                            )
                            logger.warning("[YouTube] OAuth approval timed out or was cancelled")
                            return False
                        raise
                    if creds is None:
                        self._last_error_message = (
                            "YouTube OAuth 승인이 완료되지 않았습니다. "
                            "브라우저에서 Google 계정 승인 후 다시 시도하세요."
                        )
                        logger.warning("[YouTube] OAuth returned no credentials")
                        return False

                # Save credentials
                self._ensure_writable_dir(os.path.dirname(token_path))
                with open(token_path, "w", encoding="utf-8") as token:
                    token.write(creds.to_json())

            self._credentials = creds

            # Build YouTube service
            self._youtube_service = build('youtube', 'v3', credentials=creds)
            account_email = self._fetch_oauth_account_email(creds)

            # Get channel info
            self._fetch_channel_info(account_email=account_email)
            account_guard = self._account_guard_message()
            if account_guard:
                self._last_error_message = account_guard
                logger.warning("[YouTube] Connection account verification failed: %s", account_guard)
                return False

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

    def _fetch_channel_info(self, account_email: str = "") -> None:
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
                previous_email = self._channel.account_email if self._channel else ""
                account_email = str(account_email or previous_email or "").strip().lower()

                self._channel = YouTubeChannel(
                    channel_id=item.get("id", ""),
                    channel_name=snippet.get("title", ""),
                    account_email=account_email,
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

    def _ensure_youtube_service(self) -> bool:
        """
        Ensure YouTube API service is ready using saved OAuth token (non-interactive).

        Returns:
            True if service is available.
        """
        if self._youtube_service is not None:
            return True
        if not YOUTUBE_API_AVAILABLE:
            return False

        try:
            self._migrate_legacy_oauth_files()
            token_path = self._get_token_path()
            if not os.path.exists(token_path):
                logger.warning("[YouTube] OAuth 토큰이 없어 업로드를 시작할 수 없습니다.")
                return False

            def _refresh_if_needed(creds: Any) -> bool:
                if creds.valid:
                    return True
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    try:
                        with open(token_path, "w", encoding="utf-8") as token:
                            token.write(creds.to_json())
                    except Exception as save_err:
                        logger.debug("[YouTube] 갱신 토큰 저장 실패: %s", save_err)
                    return True
                logger.warning("[YouTube] OAuth 토큰이 유효하지 않습니다. 채널을 다시 연결해주세요.")
                return False

            creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
            try:
                if not _refresh_if_needed(creds):
                    return False
            except Exception as refresh_exc:
                if "invalid_scope" not in str(refresh_exc).lower():
                    raise
                logger.warning(
                    "[YouTube] OAuth 토큰 scope가 기존 연결과 달라 저장된 scope로 복원합니다."
                )
                creds = Credentials.from_authorized_user_file(token_path)
                if not _refresh_if_needed(creds):
                    return False

            self._credentials = creds
            self._youtube_service = build("youtube", "v3", credentials=creds)
            if not self._channel or not self._channel.channel_id:
                self._fetch_channel_info(account_email=self._fetch_oauth_account_email(creds))
            elif not self._channel.account_email:
                account_email = self._fetch_oauth_account_email(creds)
                if account_email:
                    self._channel.account_email = account_email
                    self._save_settings()
                    self._sync_settings_manager_state()
            return self._youtube_service is not None
        except Exception as e:
            if "invalid_grant" in str(e).lower():
                logger.warning("[YouTube] OAuth 토큰이 만료/폐기되었습니다. 채널을 다시 연결해주세요.")
                try:
                    self.disconnect_channel()
                except Exception:
                    pass
            logger.warning("[YouTube] 저장된 토큰으로 서비스 복원 실패: %s", e)
            return False

    # ============ Upload Settings ============

    def get_upload_settings(self) -> AutoUploadSettings:
        """Get auto-upload settings"""
        return self._upload_settings

    def apply_settings_manager_upload_settings(self, start_upload: bool = True) -> None:
        """Reload auto-upload settings after account settings sync."""
        try:
            settings = get_settings_manager()
            self._upload_settings.enabled = bool(settings.get_youtube_auto_upload())
            self._upload_settings.interval_minutes = int(settings.get_youtube_upload_interval())
            self._save_settings()
            if self._upload_settings.enabled and start_upload:
                self.start_auto_upload()
            elif not self._upload_settings.enabled:
                self.stop_auto_upload()
        except Exception as exc:
            logger.debug("[YouTube] Failed to apply synced upload settings: %s", exc)

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
        purchase_link = self._normalize_public_url(url)
        product_line = self._sanitize_public_text(product_info, limit=180) or "쇼핑 추천 영상입니다."
        lines = [
            product_line,
            "자세한 상품 정보는 아래 링크에서 확인하세요.",
        ]
        if purchase_link:
            lines.append(f"구매 링크: {purchase_link}")
        lines.append("좋아요와 구독 부탁드립니다.")

        description = "\n".join(lines)
        if self._is_coupang_url(purchase_link):
            description = self.ensure_coupang_affiliate_compliance(description, purchase_link)
        return self._sanitize_public_text(description, limit=5000)

    @staticmethod
    def ensure_coupang_affiliate_compliance(description: str, purchase_link: str = "") -> str:
        """Ensure Coupang affiliate disclosure + purchase link are visible."""
        desc = str(description or "").strip()
        link = str(purchase_link or "").strip()

        if COUPANG_AFFILIATE_DISCLOSURE not in desc:
            desc = f"{COUPANG_AFFILIATE_DISCLOSURE}\n\n{desc}" if desc else COUPANG_AFFILIATE_DISCLOSURE

        if link and link.startswith(("http://", "https://")) and link not in desc:
            desc = f"{desc}\n구매 링크: {link}"

        return desc.strip()

    @staticmethod
    def ensure_coupang_title_compliance(
        title: str,
        max_length: int = 100,
        marker_position: str = "prefix",
    ) -> str:
        """Ensure Shorts title carries a visible paid-promotion marker."""
        clean_title = " ".join(str(title or "").split()) or "쇼핑 추천 영상"
        lowered = clean_title.lower()
        paid_markers = (
            COUPANG_PAID_PROMOTION_TITLE_MARKER,
            "유료광고",
            "유료 광고",
            "광고 포함",
            "유료광고 포함",
        )
        if str(marker_position or "").strip().lower() == "suffix":
            for marker in paid_markers:
                clean_title = re.sub(
                    rf"(^|\s){re.escape(marker)}(\s|$)",
                    " ",
                    clean_title,
                    flags=re.IGNORECASE,
                )
            clean_title = " ".join(clean_title.split()).strip() or "쇼핑 추천 영상"
            suffix = f" {COUPANG_PAID_PROMOTION_TITLE_MARKER}"
            available = max(1, max_length - len(suffix))
            if len(clean_title) > available:
                clean_title = clean_title[: max(1, available - 3)].rstrip() + "..."
            return f"{clean_title}{suffix}".strip()

        if any(marker.lower() in lowered for marker in paid_markers):
            return clean_title[:max_length].rstrip()

        prefix = f"{COUPANG_PAID_PROMOTION_TITLE_MARKER} "
        available = max(1, max_length - len(prefix))
        if len(clean_title) > available:
            clean_title = clean_title[: max(1, available - 3)].rstrip() + "..."
        return f"{prefix}{clean_title}".strip()

    @staticmethod
    def ensure_coupang_comment_compliance(
        comment: str,
        purchase_link: str = "",
        original_link: str = "",
    ) -> str:
        """Ensure YouTube comments show disclosure before any collapsed text."""
        text = str(comment or "").strip()
        purchase = str(purchase_link or "").strip()
        original = str(original_link or "").strip()

        if COUPANG_AFFILIATE_DISCLOSURE not in text:
            text = f"{COUPANG_AFFILIATE_DISCLOSURE}\n{text}" if text else COUPANG_AFFILIATE_DISCLOSURE

        preferred_link = purchase or original
        if (
            preferred_link
            and preferred_link.startswith(("http://", "https://"))
            and preferred_link not in text
        ):
            text = f"{text}\n구매 링크: {preferred_link}"

        if (
            original
            and original.startswith(("http://", "https://"))
            and original != preferred_link
            and original not in text
        ):
            text = f"{text}\n원상품 링크: {original}"

        return text.strip()

    @staticmethod
    def _coerce_upload_number(upload_number: Any) -> Optional[int]:
        try:
            if isinstance(upload_number, str):
                match = re.search(r"\d+", upload_number)
                if not match:
                    return None
                value = int(match.group(0))
            else:
                value = int(upload_number)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @classmethod
    def format_upload_number(cls, upload_number: Any) -> str:
        value = cls._coerce_upload_number(upload_number)
        return f"[{value:03d}]" if value else ""

    @classmethod
    def apply_upload_number_to_product_text(
        cls,
        text: str,
        upload_number: Any,
        limit: int = 220,
    ) -> str:
        clean = str(text or "").strip()
        marker = cls.format_upload_number(upload_number)
        if not marker:
            return cls._sanitize_public_text(clean, limit=limit)

        clean = re.sub(r"^\[\d+\]\s*", "", clean).strip()
        numbered = f"{marker} {clean}".strip() if clean else marker
        return cls._sanitize_public_text(numbered, limit=limit)

    @classmethod
    def apply_upload_number_to_title(
        cls,
        title: str,
        upload_number: Any,
        max_length: int = 100,
    ) -> str:
        marker = cls.format_upload_number(upload_number)
        clean = " ".join(str(title or "").split()).strip()
        if not marker:
            return clean[:max_length].rstrip()

        paid_marker = COUPANG_PAID_PROMOTION_TITLE_MARKER
        parts: List[str] = []
        if clean.startswith(paid_marker):
            parts.append(paid_marker)
            clean = clean[len(paid_marker):].strip()

        clean = re.sub(r"^\[\d+\]\s*", "", clean).strip()
        parts.append(marker)
        head = " ".join(parts)
        available = max(0, max_length - len(head) - 1)
        if clean and len(clean) > available:
            clean = clean[: max(1, available - 3)].rstrip() + "..."
        return f"{head} {clean}".strip()[:max_length].rstrip()

    @classmethod
    def apply_upload_number_to_description(
        cls,
        description: str,
        upload_number: Any,
        product_text: str = "",
        limit: int = 5000,
    ) -> str:
        marker = cls.format_upload_number(upload_number)
        desc = str(description or "").strip()
        if not marker:
            return cls._sanitize_public_text(desc, limit=limit)

        desc = re.sub(r"(?m)^상품 번호:\s*\[\d+\]\s*$\n?", "", desc).strip()
        product_line_text = cls.apply_upload_number_to_product_text(
            product_text,
            upload_number,
            limit=220,
        )
        product_line = f"상품: {product_line_text}" if product_line_text else f"상품 번호: {marker}"

        if product_line in desc:
            return cls._sanitize_public_text(desc, limit=limit)

        if desc.startswith(COUPANG_AFFILIATE_DISCLOSURE):
            tail = desc[len(COUPANG_AFFILIATE_DISCLOSURE):].lstrip()
            parts = [COUPANG_AFFILIATE_DISCLOSURE, product_line]
            if tail:
                parts.append(tail)
            return cls._sanitize_public_text("\n\n".join(parts), limit=limit)

        combined = f"{product_line}\n{desc}".strip() if desc else product_line
        return cls._sanitize_public_text(combined, limit=limit)

    def generate_seo_hashtags(self, product_info: str, max_count: int = 10) -> List[str]:
        """
        Generate SEO-optimized hashtags.

        Args:
            product_info: Product description
            max_count: Maximum number of hashtags

        Returns:
            List of hashtags (without # prefix)
        """
        raw = self._sanitize_public_text(product_info, limit=260)
        tokens = re.findall(r"[가-힣]{2,}|[a-zA-Z][a-zA-Z0-9]{1,20}", raw.lower())

        keywords: List[str] = []
        for token in tokens:
            if token in HASHTAG_STOPWORDS:
                continue
            if re.search(r"(하세요|해요|합니다|입니다|보세요|하시죠|나요|네요|까요|였죠|겠죠)$", token):
                continue
            if token.endswith(("하다", "하기", "하는", "되는", "같은")):
                continue
            if token.isdigit():
                continue
            cleaned = self._normalize_hashtag_token(token)
            if not cleaned:
                continue
            keywords.append(cleaned)
            if len(keywords) >= max(2, max_count):
                break

        all_tags = keywords + DEFAULT_HASHTAG_POOL
        seen = set()
        unique_tags = []
        for tag in all_tags:
            normalized = tag.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_tags.append(tag)
            if len(unique_tags) >= max_count:
                break

        return unique_tags

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
        render_integrity: Optional[Dict[str, Any]] = None,
        render_integrity_required: bool = False,
        upload_number: Optional[int] = None,
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
            upload_number: Shared Linktree/channel number, shown as [001]
        """
        clean_source_url = self._normalize_public_url(source_url)
        clean_coupang_link = self._normalize_public_url(coupang_deep_link)
        clean_product_info = self._sanitize_public_text(product_info, limit=220)
        clean_title = self._sanitize_public_text(title, limit=100)
        clean_description = self._sanitize_public_text(description, limit=5000)
        clean_upload_number = self._coerce_upload_number(upload_number)
        unnumbered_product_info = clean_product_info

        # Generate SEO content if enabled and not provided
        if not clean_title and self._upload_settings.auto_title:
            clean_title = self.generate_seo_title(clean_product_info)

        if not clean_description and self._upload_settings.auto_description:
            clean_description = self.generate_seo_description(clean_product_info, clean_source_url)

        purchase_link = clean_coupang_link or clean_source_url
        if self._is_coupang_url(purchase_link) or self._is_coupang_url(clean_source_url):
            clean_title = self.ensure_coupang_title_compliance(clean_title)
            clean_description = self.ensure_coupang_affiliate_compliance(clean_description, purchase_link)

        if clean_upload_number:
            clean_product_info = self.apply_upload_number_to_product_text(
                clean_product_info,
                clean_upload_number,
            )
            clean_title = self.apply_upload_number_to_title(
                clean_title or unnumbered_product_info,
                clean_upload_number,
            )
            clean_description = self.apply_upload_number_to_description(
                clean_description,
                clean_upload_number,
                product_text=unnumbered_product_info,
            )

        normalized_tags = [
            t for t in (self._normalize_hashtag_token(tag) for tag in (tags or []))
            if t
        ]
        if not normalized_tags and self._upload_settings.auto_hashtags:
            normalized_tags = self.generate_seo_hashtags(clean_product_info, self._upload_settings.max_hashtags)

        if render_integrity_required and not (render_integrity or {}).get("ok"):
            logger.warning("[YouTube] Upload blocked: render integrity was not verified.")
            return

        account_guard = self._account_guard_message()
        if account_guard:
            logger.warning("[YouTube] Upload blocked: %s", account_guard)
            self._last_error_message = account_guard
            return

        self._upload_queue.append({
            "video_path": video_path,
            "title": clean_title or "쇼핑 추천 영상",
            "description": clean_description or "",
            "tags": normalized_tags,
            "product_info": clean_product_info or "",
            "source_url": clean_source_url or "",
            "coupang_deep_link": clean_coupang_link or "",
            "linktree_url": linktree_url or "",
            "upload_number": clean_upload_number,
            "render_integrity": render_integrity or {},
            "render_integrity_required": bool(render_integrity_required),
            "added_at": datetime.now().isoformat()
        })

        logger.info(f"[YouTube] 업로드 대기열 추가: {clean_title}")

        # 업로드 활성화 상태인데 스레드가 꺼져 있으면 자동 재시작
        if self._upload_settings.enabled and self.is_connected() and not self._upload_running:
            self.start_auto_upload()

    def start_auto_upload(self) -> None:
        """Start auto-upload background thread"""
        if self._upload_running:
            return

        if not self.is_connected():
            logger.warning("[YouTube] 채널이 연결되지 않았습니다.")
            return

        if not self._ensure_youtube_service():
            logger.warning("[YouTube] 업로드 서비스를 준비하지 못했습니다. 채널 재연결 후 다시 시도해주세요.")
            return

        account_guard = self._account_guard_message()
        if account_guard:
            logger.warning("[YouTube] Auto-upload blocked: %s", account_guard)
            self._last_error_message = account_guard
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
        if not self._youtube_service and not self._ensure_youtube_service():
            return False

        video_path = item.get("video_path", "")
        if not os.path.exists(video_path):
            logger.warning(f"[YouTube] 비디오 파일 없음: {video_path}")
            return False

        if item.get("render_integrity_required") and not (
            item.get("render_integrity") or {}
        ).get("ok"):
            logger.warning("[YouTube] Upload blocked: render integrity guard failed.")
            return False

        try:
            # Add hashtags to description
            tags = [
                t for t in (self._normalize_hashtag_token(tag) for tag in item.get("tags", []))
                if t
            ]
            hashtag_str = " ".join([f"#{tag}" for tag in tags])
            safe_title = self._sanitize_public_text(item.get("title", ""), limit=100) or "쇼핑 추천 영상"
            description = self._sanitize_public_text(item.get("description", ""), limit=5000)
            purchase_link = self._normalize_public_url(
                item.get("coupang_deep_link") or item.get("source_url") or ""
            )
            if self._is_coupang_url(purchase_link):
                safe_title = self.ensure_coupang_title_compliance(
                    safe_title,
                    marker_position=str(item.get("paid_marker_position") or "prefix"),
                )
                description = self.ensure_coupang_affiliate_compliance(description, purchase_link)
            item["title"] = safe_title
            if hashtag_str:
                description = f"{description}\n\n{hashtag_str}"

            body = {
                "snippet": {
                    "title": safe_title,
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
    def _normalize_public_url(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        match = re.search(r"https?://[^\s)>\]]+", text)
        if not match:
            return ""
        return match.group(0).rstrip(".,)")

    @staticmethod
    def _sanitize_public_text(text: str, limit: int = 1000) -> str:
        raw = str(text or "")
        if not raw:
            return ""

        cleaned = (
            raw.replace("**", "")
            .replace("__", "")
            .replace("`", "")
            .replace("\r", "\n")
        )
        cleaned = re.sub(r"\[(.*?)\]\((https?://[^)]+)\)", r"\1 \2", cleaned)

        lines: List[str] = []
        for line in cleaned.splitlines():
            compact = " ".join(line.split()).strip()
            if not compact:
                if lines and lines[-1] != "":
                    lines.append("")
                continue
            if "local://" in compact.lower() or "file://" in compact.lower():
                continue
            lines.append(compact)

        normalized = "\n".join(lines).strip()
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3].rstrip() + "..."

    @staticmethod
    def _normalize_hashtag_token(token: str) -> str:
        t = str(token or "").strip().lstrip("#")
        if not t:
            return ""
        t = re.sub(r"[^0-9a-zA-Z가-힣]", "", t)
        if len(t) < 2:
            return ""
        if len(t) > 24:
            return ""
        if re.fullmatch(r"[가-힣]+", t) and len(t) > 8:
            return ""
        return t

    @staticmethod
    def _is_instructional_comment_prompt(text: str) -> bool:
        prompt = str(text or "")
        if not prompt:
            return False
        lowered = prompt.lower()
        marker_hits = sum(
            1
            for marker in (
                "[형식]",
                "[작성 원칙]",
                "작성해주세요",
                "작성해 주세요",
                "고정 댓글용",
                "금지",
                "원칙",
            )
            if marker in prompt
        )
        numbered_lines = len(re.findall(r"(?m)^\s*\d+\)", prompt))
        return marker_hits >= 2 or (marker_hits >= 1 and numbered_lines >= 2) or "형식" in lowered and numbered_lines >= 2

    @staticmethod
    def _sanitize_comment_body(text: str, max_lines: int = 8) -> str:
        normalized = YouTubeManager._sanitize_public_text(text, limit=2000)
        if not normalized:
            return ""
        kept: List[str] = []
        for line in normalized.splitlines():
            compact = line.strip()
            if not compact:
                continue
            # Remove instruction-like list artifacts from leaked prompt templates.
            if re.match(r"^\[.*\]$", compact):
                continue
            if re.match(r"^\d+\)\s*", compact) and any(
                hint in compact for hint in ("요약", "상품", "구매", "신뢰", "참여", "원칙")
            ):
                continue
            if compact.startswith("- ") and any(
                hint in compact for hint in ("금지", "원칙", "이모지", "반복", "수수료")
            ):
                continue
            kept.append(compact)
            if len(kept) >= max_lines:
                break
        return "\n".join(kept).strip()

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
        upload_number: str = "",
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
            "{상품번호}": upload_number,
            "{업로드번호}": upload_number,
            "{upload_number}": upload_number,
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
            value = self._normalize_public_url(item.get(key, "") or "")
            if value:
                return value

        try:
            if hasattr(settings, "get_linktree_settings"):
                linktree_settings = settings.get_linktree_settings() or {}
                profile_url = self._normalize_public_url(
                    linktree_settings.get("profile_url", "") or ""
                )
                if profile_url:
                    return profile_url
        except Exception as exc:
            logger.debug("[YouTube] Linktree profile lookup skipped: %s", exc)

        description = str(item.get("description", "") or "")
        try:
            match = re.search(r"https?://(?:www\.)?linktr\.ee/[^\s)>\]]+", description)
            if match:
                return match.group(0).rstrip(".,")
        except Exception:
            pass

        try:
            from managers.linktree_manager import DEFAULT_LINKTREE_PROFILE_URL
            return DEFAULT_LINKTREE_PROFILE_URL
        except Exception:
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
        text = YouTubeManager._sanitize_public_text(raw, limit=limit)
        if not text:
            return ""
        upload_number = (
            item.get("upload_number")
            or item.get("linktree_publish_index")
            or item.get("publish_index")
        )
        return YouTubeManager.apply_upload_number_to_product_text(
            text,
            upload_number,
            limit=limit,
        )

    def _resolve_comment_original_link(self, item: Dict[str, Any]) -> str:
        settings = get_settings_manager()
        manual_link = self._normalize_public_url(settings.get_youtube_comment_manual_product_link())
        if manual_link:
            return manual_link

        source_url = self._normalize_public_url(item.get("source_url", ""))
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
            self._sanitize_public_text(settings.get_youtube_comment_prompt().strip(), limit=2500)
            if comment_enabled and hasattr(settings, "get_youtube_comment_prompt")
            else ""
        )
        if raw_prompt and self._is_instructional_comment_prompt(raw_prompt):
            logger.warning("[YouTube] Instruction-style comment prompt detected; using safe auto-comment format")
            try:
                if hasattr(settings, "set_youtube_comment_prompt"):
                    settings.set_youtube_comment_prompt(
                        "영상에서 소개한 상품 안내입니다.\n"
                        "상품: {상품설명}\n"
                        "구매 링크: {구매링크}\n"
                        "원상품 링크: {원상품링크}\n"
                        "링크 모음: {linktree_link}\n"
                        "궁금한 점은 댓글로 남겨주세요."
                    )
            except Exception as exc:
                logger.debug("[YouTube] Failed to migrate comment prompt: %s", exc)
            raw_prompt = ""

        purchase_link = self._normalize_public_url(item.get("coupang_deep_link", ""))
        original_link = self._resolve_comment_original_link(item)
        product_description = self._build_comment_product_description(item)
        upload_number = self.format_upload_number(
            item.get("upload_number")
            or item.get("linktree_publish_index")
            or item.get("publish_index")
        )
        has_product_context = any((product_description, purchase_link, original_link))
        linktree_link = (
            self._resolve_comment_linktree_url(settings, item)
            if has_product_context
            else ""
        )

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
            upload_number=upload_number,
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

        prompt_with_tokens = self._sanitize_comment_body(prompt_with_tokens)
        if not prompt_with_tokens:
            prompt_with_tokens = "영상에서 소개한 상품 정보를 공유드립니다."

        extra_lines = []
        if product_description and not has_product_placeholder:
            extra_lines.append(f"상품: {product_description}")
        if purchase_link and not has_purchase_placeholder:
            extra_lines.append(f"구매 링크: {purchase_link}")
        if linktree_link and not has_linktree_placeholder:
            extra_lines.append(f"링크 모음: {linktree_link}")
        if (
            original_link
            and original_link != purchase_link
            and not has_original_placeholder
        ):
            extra_lines.append(f"원상품 링크: {original_link}")

        if extra_lines:
            text = "\n".join([prompt_with_tokens] + extra_lines)
        else:
            text = prompt_with_tokens

        text = self._sanitize_comment_body(text)
        if self._is_coupang_url(purchase_link) or self._is_coupang_url(original_link):
            text = self.ensure_coupang_comment_compliance(
                text,
                purchase_link=purchase_link,
                original_link=original_link,
            )

        return self._trim_comment_text(self._sanitize_comment_body(text), limit=10000)

    def build_coupang_partners_submission_guide(self, linktree_url: str = "") -> str:
        """Build a markdown checklist for Coupang Partners channel review."""
        channel_info = self.get_channel_info()
        channel_name = channel_info.get("channel_name") or channel_info.get("title") or "미연결"
        channel_url = channel_info.get("channel_url") or self.get_channel_url() or "유튜브 채널 미연결"
        linktree = str(linktree_url or "").strip() or "Linktree Profile 미설정"
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return "\n".join([
            "# 쿠팡 파트너스 채널 인증 재신청 자료",
            "",
            f"- 생성일: {generated_at}",
            f"- 참고 공지: {COUPANG_PARTNERS_NOTICE_98_URL}",
            "",
            "## 등록할 채널",
            f"- YouTube 채널명: {channel_name}",
            f"- YouTube 채널 URL: {channel_url}",
            f"- Linktree Profile: {linktree}",
            "",
            "## 쿠팡 파트너스 신청 화면 입력",
            "- 웹사이트 목록에는 YouTube 프로필을 확인할 수 있는 채널 URL을 입력합니다.",
            "- Linktree를 함께 쓰는 경우 Linktree 공개 Profile URL도 활동 페이지로 추가합니다.",
            "- 스크린샷에는 유튜브 활동 페이지, 파트너스 링크, 대가성 문구가 모두 보이게 합니다.",
            "",
            "## 스크린샷 체크리스트",
            "- YouTube 채널 홈에서 채널 URL과 채널명이 보이는 화면",
            "- 쿠팡 파트너스 링크가 들어간 영상 설명란 또는 댓글이 접히지 않고 보이는 화면",
            "- 쇼츠 제목의 `[광고]` 표기 또는 영상 내부의 `유료광고 포함` 표기가 보이는 화면",
            "- Linktree를 쓰는 경우 공개 페이지에서 쿠팡 링크 카드와 대가성 문구가 보이는 화면",
            "",
            "## 프로그램 자동 보강 내용",
            f"- 쿠팡 링크가 포함된 YouTube 제목 앞에 `{COUPANG_PAID_PROMOTION_TITLE_MARKER}`를 붙입니다.",
            f"- YouTube 설명과 자동 댓글 첫 줄에 `{COUPANG_AFFILIATE_DISCLOSURE}` 문구를 넣습니다.",
            "- 쿠팡 구매 링크가 설명 또는 댓글에 누락되면 자동으로 추가합니다.",
            "- 자동 댓글은 대가성 문구가 `더보기` 뒤로 밀리지 않도록 첫 줄에 배치합니다.",
            "",
            "## 최종 점검",
            "- 파트너스 링크가 들어간 영상 설명란, 댓글, 커뮤니티 글에 대가성 문구가 빠지지 않았는지 확인",
            "- 대가성 문구가 `더보기`를 누르지 않아도 보이는지 확인",
            "- Shorts 제목 또는 영상 내부에 `[광고]`/`유료광고 포함` 등 경제적 이해관계 표시가 있는지 확인",
            "- 파트너스 활동을 확인할 수 있는 링크와 스크린샷이 쿠팡 파트너스에 모두 등록됐는지 확인",
            "",
        ])

    def write_coupang_partners_submission_guide(
        self,
        linktree_url: str = "",
        output_path: str = "",
    ) -> str:
        """Write the Coupang Partners review checklist to a user data file."""
        path = output_path or os.path.join(
            self._get_user_data_dir(),
            "coupang_partners_channel_verification.md",
        )
        self._ensure_writable_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.build_coupang_partners_submission_guide(linktree_url=linktree_url))
        return path

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
