# -*- coding: utf-8 -*-
"""
TikTok Manager for Channel Connection and Auto-Upload
틱톡 채널 연결 및 자동 업로드 매니저

Handles:
- TikTok OAuth 2.0 authentication
- Channel connection management
- Auto-upload via Content Posting API
- Video upload status polling
"""

import json
import os
import re
import threading
import time
import requests
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from utils.logging_config import get_logger

logger = get_logger(__name__)


# TikTok API Configuration
TIKTOK_API_BASE = "https://open.tiktokapis.com"
TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = f"{TIKTOK_API_BASE}/v2/oauth/token/"
TIKTOK_CREATOR_INFO_URL = f"{TIKTOK_API_BASE}/v2/post/publish/creator_info/query/"

# Coupang affiliate disclosure (shared policy text)
COUPANG_AFFILIATE_DISCLOSURE = (
    "이 게시물은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)

# TikTok caption hard limit
TIKTOK_CAPTION_MAX_LEN = 2200

# Privacy levels (ordered by public-preference) used to pick a compliant value
# from the options creator_info reports as available for this account/app.
TIKTOK_PRIVACY_PREFERENCE = [
    "PUBLIC_TO_EVERYONE",
    "FOLLOWER_OF_CREATOR",
    "MUTUAL_FOLLOW_FRIENDS",
    "SELF_ONLY",
]


@dataclass
class TikTokChannel:
    """TikTok account data structure"""
    open_id: str = ""
    username: str = ""
    display_name: str = ""
    avatar_url: str = ""
    follower_count: int = 0
    video_count: int = 0
    connected_at: str = ""


@dataclass
class TikTokUploadSettings:
    """TikTok upload settings data structure"""
    enabled: bool = False
    interval_minutes: int = 60  # 업로드 간격 (분 단위) - TikTok은 더 긴 간격 권장
    default_privacy: str = "PUBLIC_TO_EVERYONE"  # PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY
    allow_comments: bool = True
    allow_duet: bool = True
    allow_stitch: bool = True
    auto_caption: bool = False  # 자동 자막 생성
    max_video_length: int = 180  # 최대 영상 길이 (초)


@dataclass
class TikTokCredentials:
    """TikTok OAuth credentials"""
    access_token: str = ""
    refresh_token: str = ""
    open_id: str = ""
    expires_at: float = 0.0  # Unix timestamp
    scope: str = ""


class TikTokManager:
    """
    TikTok content posting management
    틱톡 콘텐츠 포스팅 관리
    
    Uses TikTok Content Posting API v2
    https://developers.tiktok.com/doc/content-posting-api-get-started
    """

    # OAuth 2.0 scopes required for video upload
    SCOPES = [
        "user.info.basic",
        "video.publish",
        "video.upload"
    ]
    APP_CREDENTIALS_KEY = "tiktok_app_credentials_v1"
    DEFAULT_REDIRECT_URI = "http://localhost:8080/callback"

    def __init__(self, gui=None, settings_file: str = "tiktok_settings.json"):
        """
        Initialize TikTok manager.

        Args:
            gui: VideoAnalyzerGUI instance
            settings_file: Settings file name
        """
        self.gui = gui
        self.settings_file = settings_file

        # App credentials: prefer secure storage, fall back to environment vars.
        self._client_key: str = ""
        self._client_secret: str = ""
        self._redirect_uri: str = os.environ.get("TIKTOK_REDIRECT_URI", self.DEFAULT_REDIRECT_URI)
        self._load_app_credentials_into_state()

        # Latest creator_info snapshot (privacy options / can-post gating).
        self._creator_info: Dict[str, Any] = {}
        self._last_error_message: str = ""

        # State
        self._credentials: Optional[TikTokCredentials] = None
        self._channel: Optional[TikTokChannel] = None
        self._upload_settings = TikTokUploadSettings()

        # Auto-upload thread
        self._upload_thread: Optional[threading.Thread] = None
        self._upload_queue: List[Dict[str, Any]] = []
        self._upload_running = False
        self._last_upload_time: Optional[datetime] = None

        # Upload status tracking
        self._pending_uploads: Dict[str, Dict[str, Any]] = {}  # publish_id -> status

        # Callbacks
        self._on_upload_complete: Optional[Callable] = None
        self._on_upload_error: Optional[Callable] = None
        self._on_connection_changed: Optional[Callable] = None

        # Load settings
        self._load_settings()

    # ============ Settings Persistence ============

    def _get_settings_path(self) -> str:
        """Get full path to settings file"""
        try:
            import sys
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            logger.debug(f"[TikTok] 기본 경로 감지 실패, cwd 사용: {e}")
            base_dir = os.getcwd()
        return os.path.join(base_dir, self.settings_file)

    @staticmethod
    def _encrypt_secret(value: str) -> str:
        """Encrypt sensitive token value for local persistence."""
        if not value:
            return value
        try:
            from utils.secrets_manager import SecretsManager
            return SecretsManager._simple_encrypt(value)
        except Exception as e:
            logger.warning(f"[TikTok] Token encryption failed, storing plaintext: {e}")
            return value

    @staticmethod
    def _decrypt_secret(value: str) -> str:
        """Decrypt persisted token value. Returns plaintext for legacy values."""
        if not value:
            return value
        if value.startswith("fernet:"):
            try:
                from utils.secrets_manager import SecretsManager
                return SecretsManager._simple_decrypt(value)
            except Exception as e:
                logger.warning(f"[TikTok] Token decryption failed: {e}")
                return ""
        return value

    # ============ App credentials (Client Key / Secret / Redirect) ============

    def install_app_credentials(
        self,
        client_key: str,
        client_secret: str,
        redirect_uri: str = "",
    ) -> bool:
        """Validate and store TikTok app credentials in secure storage."""
        client_key = str(client_key or "").strip()
        client_secret = str(client_secret or "").strip()
        redirect_uri = str(redirect_uri or "").strip() or self.DEFAULT_REDIRECT_URI

        if not re.fullmatch(r"[A-Za-z0-9._-]{6,64}", client_key):
            raise ValueError("TikTok Client Key 형식이 올바르지 않습니다.")
        if not re.fullmatch(r"[A-Za-z0-9._-]{6,128}", client_secret):
            raise ValueError("TikTok Client Secret 형식이 올바르지 않습니다.")
        if not re.match(r"^https?://", redirect_uri):
            raise ValueError("Redirect URI는 http(s)로 시작해야 합니다.")

        try:
            from utils.secrets_manager import get_secrets_manager
            payload = json.dumps({
                "client_key": client_key,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            })
            ok = bool(get_secrets_manager().set_credential(self.APP_CREDENTIALS_KEY, payload))
            if ok:
                self._client_key = client_key
                self._client_secret = client_secret
                self._redirect_uri = redirect_uri
                logger.info("[TikTok] App credentials securely stored")
            return ok
        except Exception as e:
            logger.error("[TikTok] Failed to store app credentials: %s", e)
            return False

    def load_app_credentials(self) -> Dict[str, str]:
        """Load TikTok app credentials from secure storage (empty dict if none)."""
        try:
            from utils.secrets_manager import get_secrets_manager
            payload = get_secrets_manager().get_credential(self.APP_CREDENTIALS_KEY)
            if not payload:
                return {}
            data = json.loads(payload)
            client_key = str(data.get("client_key", "") or "").strip()
            client_secret = str(data.get("client_secret", "") or "").strip()
            redirect_uri = str(data.get("redirect_uri", "") or "").strip() or self.DEFAULT_REDIRECT_URI
            if client_key and client_secret:
                return {
                    "client_key": client_key,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                }
        except Exception as e:
            logger.debug("[TikTok] Failed to read app credentials: %s", e)
        return {}

    def _load_app_credentials_into_state(self) -> None:
        """Populate client key/secret/redirect from secure storage or env vars."""
        stored = self.load_app_credentials()
        if stored:
            self._client_key = stored["client_key"]
            self._client_secret = stored["client_secret"]
            self._redirect_uri = stored["redirect_uri"]
            return
        # Fallback: environment variables (legacy / power-user path).
        self._client_key = os.environ.get("TIKTOK_CLIENT_KEY", "")
        self._client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
        self._redirect_uri = os.environ.get("TIKTOK_REDIRECT_URI", self.DEFAULT_REDIRECT_URI)

    def has_app_credentials(self) -> bool:
        return bool(self._client_key and self._client_secret)

    def get_last_error(self) -> str:
        return self._last_error_message

    def _load_settings(self) -> None:
        """Load settings from file"""
        settings_path = self._get_settings_path()
        migrated_plaintext = False

        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Load channel info
                if "channel" in data:
                    ch = data["channel"]
                    self._channel = TikTokChannel(
                        open_id=ch.get("open_id", ""),
                        username=ch.get("username", ""),
                        display_name=ch.get("display_name", ""),
                        avatar_url=ch.get("avatar_url", ""),
                        follower_count=ch.get("follower_count", 0),
                        video_count=ch.get("video_count", 0),
                        connected_at=ch.get("connected_at", "")
                    )

                # Load credentials
                if "credentials" in data:
                    cred = data["credentials"]
                    raw_access_token = str(cred.get("access_token", "") or "")
                    raw_refresh_token = str(cred.get("refresh_token", "") or "")
                    access_token = self._decrypt_secret(raw_access_token)
                    refresh_token = self._decrypt_secret(raw_refresh_token)

                    if raw_access_token and not raw_access_token.startswith("fernet:"):
                        migrated_plaintext = True
                    if raw_refresh_token and not raw_refresh_token.startswith("fernet:"):
                        migrated_plaintext = True

                    self._credentials = TikTokCredentials(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        open_id=cred.get("open_id", ""),
                        expires_at=cred.get("expires_at", 0.0),
                        scope=cred.get("scope", "")
                    )

                # Load upload settings
                if "upload_settings" in data:
                    us = data["upload_settings"]
                    self._upload_settings = TikTokUploadSettings(
                        enabled=us.get("enabled", False),
                        interval_minutes=us.get("interval_minutes", 60),
                        default_privacy=us.get("default_privacy", "PUBLIC_TO_EVERYONE"),
                        allow_comments=us.get("allow_comments", True),
                        allow_duet=us.get("allow_duet", True),
                        allow_stitch=us.get("allow_stitch", True),
                        auto_caption=us.get("auto_caption", False),
                        max_video_length=us.get("max_video_length", 180)
                    )

                if migrated_plaintext and self._credentials:
                    logger.info("[TikTok] Migrating plaintext OAuth tokens to encrypted storage")
                    self._save_settings()

                logger.debug("[TikTok] 설정 로드 완료")
        except Exception as e:
            logger.error(f"[TikTok] 설정 로드 실패: {e}")

    def _save_settings(self) -> bool:
        """Save settings to file"""
        settings_path = self._get_settings_path()

        try:
            data = {
                "channel": {
                    "open_id": self._channel.open_id if self._channel else "",
                    "username": self._channel.username if self._channel else "",
                    "display_name": self._channel.display_name if self._channel else "",
                    "avatar_url": self._channel.avatar_url if self._channel else "",
                    "follower_count": self._channel.follower_count if self._channel else 0,
                    "video_count": self._channel.video_count if self._channel else 0,
                    "connected_at": self._channel.connected_at if self._channel else ""
                },
                "credentials": {
                    "access_token": (
                        self._encrypt_secret(self._credentials.access_token)
                        if self._credentials else ""
                    ),
                    "refresh_token": (
                        self._encrypt_secret(self._credentials.refresh_token)
                        if self._credentials else ""
                    ),
                    "open_id": self._credentials.open_id if self._credentials else "",
                    "expires_at": self._credentials.expires_at if self._credentials else 0.0,
                    "scope": self._credentials.scope if self._credentials else ""
                },
                "upload_settings": {
                    "enabled": self._upload_settings.enabled,
                    "interval_minutes": self._upload_settings.interval_minutes,
                    "default_privacy": self._upload_settings.default_privacy,
                    "allow_comments": self._upload_settings.allow_comments,
                    "allow_duet": self._upload_settings.allow_duet,
                    "allow_stitch": self._upload_settings.allow_stitch,
                    "auto_caption": self._upload_settings.auto_caption,
                    "max_video_length": self._upload_settings.max_video_length
                }
            }

            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug("[TikTok] 설정 저장 완료")
            return True
        except Exception as e:
            logger.error(f"[TikTok] 설정 저장 실패: {e}")
            return False

    # ============ OAuth Connection ============

    def is_connected(self) -> bool:
        """Check if TikTok account is connected"""
        return (
            self._credentials is not None and 
            self._credentials.access_token != "" and
            self._channel is not None and 
            self._channel.open_id != ""
        )

    def is_token_valid(self) -> bool:
        """Check if access token is still valid"""
        if not self._credentials or not self._credentials.access_token:
            return False
        return time.time() < self._credentials.expires_at - 300  # 5분 여유

    def get_channel_info(self) -> Optional[TikTokChannel]:
        """Get connected channel info"""
        return self._channel

    def get_auth_url(self, state: str = "") -> str:
        """
        Generate OAuth authorization URL.
        
        Args:
            state: CSRF protection state parameter
            
        Returns:
            Authorization URL for user to visit
        """
        if not self._client_key:
            logger.error("[TikTok] TIKTOK_CLIENT_KEY 환경변수가 설정되지 않았습니다.")
            return ""
            
        scope = ",".join(self.SCOPES)
        params = {
            "client_key": self._client_key,
            "scope": scope,
            "response_type": "code",
            "redirect_uri": self._redirect_uri,
            "state": state or "tiktok_oauth"
        }
        
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{TIKTOK_AUTH_URL}?{query}"

    def exchange_code_for_token(self, authorization_code: str) -> bool:
        """
        Exchange authorization code for access token.
        
        Args:
            authorization_code: Code received from OAuth callback
            
        Returns:
            True if token exchange successful
        """
        if not self._client_key or not self._client_secret:
            logger.error("[TikTok] Client credentials가 설정되지 않았습니다.")
            return False

        try:
            response = requests.post(
                TIKTOK_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_key": self._client_key,
                    "client_secret": self._client_secret,
                    "code": authorization_code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self._redirect_uri
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"[TikTok] 토큰 교환 실패: {response.status_code}")
                return False
                
            data = response.json()
            
            if "error" in data:
                logger.error(f"[TikTok] 토큰 오류: {data.get('error_description', data['error'])}")
                return False

            # Store credentials
            self._credentials = TikTokCredentials(
                access_token=data.get("access_token", ""),
                refresh_token=data.get("refresh_token", ""),
                open_id=data.get("open_id", ""),
                expires_at=time.time() + data.get("expires_in", 86400),
                scope=data.get("scope", "")
            )

            # Fetch user info
            self._fetch_user_info()
            self._save_settings()

            # Notify callback
            if self._on_connection_changed:
                self._on_connection_changed(True)

            logger.info("[TikTok] 인증 성공")
            return True

        except Exception as e:
            logger.error(f"[TikTok] 토큰 교환 실패: {e}")
            return False

    def refresh_access_token(self) -> bool:
        """
        Refresh expired access token.
        
        Returns:
            True if refresh successful
        """
        if not self._credentials or not self._credentials.refresh_token:
            logger.warning("[TikTok] 리프레시 토큰이 없습니다.")
            return False

        try:
            response = requests.post(
                TIKTOK_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_key": self._client_key,
                    "client_secret": self._client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self._credentials.refresh_token
                },
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"[TikTok] 토큰 리프레시 실패: {response.status_code}")
                return False

            data = response.json()

            if "error" in data:
                logger.error(f"[TikTok] 토큰 리프레시 오류: {data.get('error_description')}")
                return False

            self._credentials.access_token = data.get("access_token", "")
            self._credentials.refresh_token = data.get("refresh_token", self._credentials.refresh_token)
            self._credentials.expires_at = time.time() + data.get("expires_in", 86400)

            self._save_settings()
            logger.info("[TikTok] 토큰 리프레시 성공")
            return True

        except Exception as e:
            logger.error(f"[TikTok] 토큰 리프레시 실패: {e}")
            return False

    def disconnect_channel(self) -> None:
        """Disconnect TikTok account"""
        self._credentials = None
        self._channel = None

        self._save_settings()

        # Stop auto-upload
        self.stop_auto_upload()

        # Notify callback
        if self._on_connection_changed:
            self._on_connection_changed(False)

        logger.info("[TikTok] 연결 해제됨")

    def _fetch_user_info(self) -> None:
        """Fetch user info from TikTok API"""
        if not self._credentials or not self._credentials.access_token:
            return

        try:
            response = requests.get(
                f"{TIKTOK_API_BASE}/v2/user/info/",
                headers={
                    "Authorization": f"Bearer {self._credentials.access_token}",
                    "Content-Type": "application/json"
                },
                params={
                    "fields": "open_id,union_id,avatar_url,display_name,username,follower_count,video_count"
                },
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"[TikTok] 사용자 정보 조회 실패: {response.status_code}")
                return

            data = response.json()
            
            if data.get("error", {}).get("code") != "ok":
                logger.error(f"[TikTok] API 오류: {data.get('error', {}).get('message')}")
                return

            user_data = data.get("data", {}).get("user", {})

            self._channel = TikTokChannel(
                open_id=user_data.get("open_id", self._credentials.open_id),
                username=user_data.get("username", ""),
                display_name=user_data.get("display_name", ""),
                avatar_url=user_data.get("avatar_url", ""),
                follower_count=user_data.get("follower_count", 0),
                video_count=user_data.get("video_count", 0),
                connected_at=datetime.now().isoformat()
            )

            logger.info(f"[TikTok] 사용자 연결: @{self._channel.username or self._channel.display_name}")

        except Exception as e:
            logger.error(f"[TikTok] 사용자 정보 조회 실패: {e}")

    # ============ Upload Settings ============

    def get_upload_settings(self) -> TikTokUploadSettings:
        """Get upload settings"""
        return self._upload_settings

    def set_upload_enabled(self, enabled: bool) -> None:
        """Enable/disable auto-upload"""
        self._upload_settings.enabled = enabled
        self._save_settings()

        if enabled:
            self.start_auto_upload()
        else:
            self.stop_auto_upload()

    def set_upload_interval(self, minutes: int) -> None:
        """Set upload interval in minutes"""
        self._upload_settings.interval_minutes = max(30, min(1440, minutes))  # 30분 ~ 24시간
        self._save_settings()

    def set_privacy_settings(
        self,
        privacy: str = "PUBLIC_TO_EVERYONE",
        allow_comments: bool = True,
        allow_duet: bool = True,
        allow_stitch: bool = True
    ) -> None:
        """Set default privacy settings"""
        if privacy in ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"):
            self._upload_settings.default_privacy = privacy
        self._upload_settings.allow_comments = allow_comments
        self._upload_settings.allow_duet = allow_duet
        self._upload_settings.allow_stitch = allow_stitch
        self._save_settings()

    # ============ Video Upload ============

    def add_to_upload_queue(
        self,
        video_path: str,
        title: str = "",
        description: str = "",
        source_url: str = "",
        hashtags: Optional[List[str]] = None,
        coupang_deep_link: str = "",
        render_integrity: Optional[Dict[str, Any]] = None,
        render_integrity_required: bool = False,
        upload_number: Optional[int] = None,
    ) -> None:
        """
        Add video to upload queue (caption auto-built).

        Signature mirrors YouTube/Instagram managers for pipeline symmetry.
        """
        if render_integrity_required and not (render_integrity or {}).get("ok"):
            logger.warning("[TikTok] Upload blocked: render integrity was not verified.")
            return

        purchase_link = coupang_deep_link or source_url
        caption = self.build_caption(
            title=title,
            description=description,
            hashtags=hashtags,
            purchase_link=purchase_link,
            upload_number=upload_number,
        )

        self._upload_queue.append({
            "video_path": video_path,
            "caption": caption,
            "source_url": source_url,
            "coupang_deep_link": coupang_deep_link,
            "upload_number": upload_number,
            "render_integrity": render_integrity or {},
            "render_integrity_required": bool(render_integrity_required),
            "added_at": datetime.now().isoformat(),
        })

        logger.info(f"[TikTok] 업로드 대기열 추가: {os.path.basename(video_path)}")

        if self._upload_settings.enabled and self.is_connected() and not self._upload_running:
            self.start_auto_upload()

    @staticmethod
    def _sanitize_caption_text(text: str) -> str:
        raw = str(text or "")
        cleaned = (
            raw.replace("**", "")
            .replace("__", "")
            .replace("`", "")
            .replace("\r", "\n")
        )
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @classmethod
    def build_caption(
        cls,
        title: str = "",
        description: str = "",
        hashtags: Optional[List[str]] = None,
        purchase_link: str = "",
        upload_number: Optional[int] = None,
        max_length: int = TIKTOK_CAPTION_MAX_LEN,
    ) -> str:
        """
        Build a TikTok caption from title/description/hashtags.
        쿠팡 링크가 포함되면 파트너스 고지 문구를 보장한다.

        NOTE: TikTok forbids overlaying brand/watermark/promo text ON the video
        itself; this only builds the post caption (which is allowed to contain
        text/hashtags). Branding-free rendering is enforced upstream.
        """
        title_line = " ".join(str(title or "").split()).strip()
        if upload_number:
            try:
                marker = f"[{int(upload_number):03d}]"
                title_line = re.sub(r"^\[\d+\]\s*", "", title_line).strip()
                title_line = f"{marker} {title_line}".strip()
            except (TypeError, ValueError):
                pass

        body = cls._sanitize_caption_text(description)
        tags = [t for t in (str(tag or "").strip().lstrip("#") for tag in (hashtags or [])) if t]
        hashtag_str = " ".join(f"#{t}" for t in tags[:12])

        parts = [p for p in (title_line, body) if p]
        caption = "\n\n".join(parts)

        if "coupang.com" in str(purchase_link or "").lower() and COUPANG_AFFILIATE_DISCLOSURE not in caption:
            caption = f"{COUPANG_AFFILIATE_DISCLOSURE}\n\n{caption}" if caption else COUPANG_AFFILIATE_DISCLOSURE

        if hashtag_str:
            caption = f"{caption}\n\n{hashtag_str}" if caption else hashtag_str

        if len(caption) > max_length:
            if hashtag_str and len(hashtag_str) + 2 < max_length:
                head_budget = max_length - len(hashtag_str) - 2
                head = caption[: len(caption) - len(hashtag_str) - 2]
                caption = head[: max(1, head_budget - 3)].rstrip() + "...\n\n" + hashtag_str
            else:
                caption = caption[: max_length - 3].rstrip() + "..."
        return caption.strip()

    def query_creator_info(self) -> Dict[str, Any]:
        """
        Query creator info — MANDATORY compliance step before publishing.

        TikTok requires apps to call this and use the returned privacy options
        and posting-eligibility before every Direct Post. Returns the data dict
        (with privacy_level_options, *_disabled flags, max duration) or {}.
        """
        self._creator_info = {}
        if not self.is_connected():
            self._last_error_message = "TikTok 계정이 연결되지 않았습니다."
            return {}
        if not self.is_token_valid() and not self.refresh_access_token():
            self._last_error_message = "TikTok 토큰 갱신 실패"
            return {}
        try:
            response = requests.post(
                TIKTOK_CREATOR_INFO_URL,
                headers={
                    "Authorization": f"Bearer {self._credentials.access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                timeout=30,
            )
            data = response.json() if response.content else {}
            err = data.get("error", {}) or {}
            if response.status_code != 200 or err.get("code") not in ("ok", None, ""):
                self._last_error_message = (
                    f"creator_info 조회 실패: {err.get('message') or response.status_code}"
                )
                logger.error("[TikTok] %s", self._last_error_message)
                return {}
            self._creator_info = data.get("data", {}) or {}
            return self._creator_info
        except Exception as e:
            self._last_error_message = f"creator_info 조회 오류: {e}"
            logger.error("[TikTok] %s", self._last_error_message)
            return {}

    def _resolve_privacy_level(self, creator_info: Dict[str, Any]) -> Optional[str]:
        """Pick a compliant privacy level from creator-allowed options.

        Unaudited apps only get ['SELF_ONLY'] here, so this naturally degrades
        to private posting until the app passes TikTok's audit.
        """
        options = [str(x) for x in (creator_info.get("privacy_level_options") or [])]
        if not options:
            return None
        preferred = self._upload_settings.default_privacy
        if preferred in options:
            return preferred
        for level in TIKTOK_PRIVACY_PREFERENCE:
            if level in options:
                return level
        return options[0]

    def upload_video(self, video_path: str, caption: str = "") -> Optional[str]:
        """
        Upload a video to TikTok using the Content Posting API (Direct Post).

        Flow (official): query creator_info (compliance) -> init with post_info
        + FILE_UPLOAD source_info -> upload the file bytes -> poll status.

        Args:
            video_path: Path to video file (MP4, H.264)
            caption: Video caption (max 2200 chars)

        Returns:
            publish_id if successful, None otherwise
        """
        self._last_error_message = ""
        if not self.is_connected():
            self._last_error_message = "TikTok 계정이 연결되지 않았습니다."
            logger.error("[TikTok] %s", self._last_error_message)
            return None

        if not self.is_token_valid():
            if not self.refresh_access_token():
                self._last_error_message = "TikTok 토큰 리프레시 실패"
                logger.error("[TikTok] %s", self._last_error_message)
                return None

        if not os.path.exists(video_path):
            self._last_error_message = f"비디오 파일 없음: {video_path}"
            logger.error("[TikTok] %s", self._last_error_message)
            return None

        try:
            file_size = os.path.getsize(video_path)
            if file_size > 4 * 1024 * 1024 * 1024:  # 4GB API hard limit
                self._last_error_message = "파일 크기 초과 (최대 4GB)"
                logger.error("[TikTok] %s", self._last_error_message)
                return None

            # Step 0: creator_info (mandatory) + resolve a compliant privacy level.
            creator_info = self.query_creator_info()
            if not creator_info:
                return None
            privacy_level = self._resolve_privacy_level(creator_info)
            if not privacy_level:
                self._last_error_message = (
                    "지금은 게시할 수 없습니다(게시 한도 도달 또는 권한 없음). 잠시 후 다시 시도됩니다."
                )
                logger.warning("[TikTok] %s", self._last_error_message)
                return None

            # Step 1: Initialize Direct Post (post_info + FILE_UPLOAD source_info).
            init_response = self._init_video_upload(file_size, caption, privacy_level, creator_info)
            if not init_response:
                return None

            upload_url = init_response.get("upload_url")
            publish_id = init_response.get("publish_id")

            # Step 2: Upload the video bytes to the returned upload_url.
            if not self._upload_video_file(upload_url, video_path):
                return None

            # Track pending upload (status polled by _upload_loop / check_upload_status).
            self._pending_uploads[publish_id] = {
                "video_path": video_path,
                "caption": caption,
                "privacy_level": privacy_level,
                "started_at": datetime.now().isoformat(),
                "status": "PROCESSING",
            }

            logger.info("[TikTok] 업로드 시작됨: %s (privacy=%s)", publish_id, privacy_level)
            return publish_id

        except Exception as e:
            self._last_error_message = f"업로드 실패: {e}"
            logger.error("[TikTok] %s", self._last_error_message)
            return None

    def _init_video_upload(
        self,
        file_size: int,
        caption: str = "",
        privacy_level: str = "SELF_ONLY",
        creator_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Initialize Direct Post upload and get the upload URL."""
        creator_info = creator_info or {}
        # Single-chunk upload (valid for files up to 64MB, covers Shorts).
        try:
            response = requests.post(
                f"{TIKTOK_API_BASE}/v2/post/publish/video/init/",
                headers={
                    "Authorization": f"Bearer {self._credentials.access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "post_info": {
                        "title": str(caption or "")[:TIKTOK_CAPTION_MAX_LEN],
                        "privacy_level": privacy_level,
                        "disable_duet": (
                            not self._upload_settings.allow_duet
                            or bool(creator_info.get("duet_disabled"))
                        ),
                        "disable_comment": (
                            not self._upload_settings.allow_comments
                            or bool(creator_info.get("comment_disabled"))
                        ),
                        "disable_stitch": (
                            not self._upload_settings.allow_stitch
                            or bool(creator_info.get("stitch_disabled"))
                        ),
                        "video_cover_timestamp_ms": 1000  # 1초 지점을 썸네일로
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": file_size,
                        "chunk_size": file_size,  # Single chunk (<=64MB)
                        "total_chunk_count": 1
                    }
                },
                timeout=60
            )

            if response.status_code != 200:
                logger.error(f"[TikTok] 업로드 초기화 실패: {response.status_code}")
                return None

            data = response.json()

            if data.get("error", {}).get("code") != "ok":
                logger.error(f"[TikTok] 업로드 초기화 오류: {data.get('error', {}).get('message')}")
                return None

            return data.get("data", {})

        except Exception as e:
            logger.error(f"[TikTok] 업로드 초기화 예외: {e}")
            return None

    def _upload_video_file(self, upload_url: str, video_path: str) -> bool:
        """Upload video file to TikTok's storage"""
        try:
            file_size = os.path.getsize(video_path)
            
            with open(video_path, 'rb') as f:
                response = requests.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(file_size),
                        "Content-Range": f"bytes 0-{file_size - 1}/{file_size}"
                    },
                    data=f,
                    timeout=300  # 5분 타임아웃
                )

            if response.status_code not in (200, 201):
                logger.error(f"[TikTok] 파일 업로드 실패: {response.status_code}")
                return False

            logger.debug("[TikTok] 파일 업로드 완료")
            return True

        except Exception as e:
            logger.error(f"[TikTok] 파일 업로드 예외: {e}")
            return False

    def _create_post(self, publish_id: str, caption: str) -> bool:
        """Finalize and create the post"""
        try:
            response = requests.post(
                f"{TIKTOK_API_BASE}/v2/post/publish/",
                headers={
                    "Authorization": f"Bearer {self._credentials.access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "publish_id": publish_id,
                    "post_info": {
                        "title": caption[:100] if caption else "",  # Title max 100 chars
                        "description": caption
                    }
                },
                timeout=60
            )

            if response.status_code != 200:
                logger.error(f"[TikTok] 포스트 생성 실패: {response.status_code}")
                return False

            data = response.json()

            if data.get("error", {}).get("code") != "ok":
                logger.error(f"[TikTok] 포스트 생성 오류: {data.get('error', {}).get('message')}")
                return False

            return True

        except Exception as e:
            logger.error(f"[TikTok] 포스트 생성 예외: {e}")
            return False

    def check_upload_status(self, publish_id: str) -> Dict[str, Any]:
        """
        Check status of a pending upload.
        
        Args:
            publish_id: The publish_id from upload initialization
            
        Returns:
            Status dict with 'status' key (PROCESSING, FAILED, PUBLISHED_PUBLICLY)
        """
        if not self.is_connected():
            return {"status": "NOT_CONNECTED", "error": "Not connected"}

        try:
            response = requests.post(
                f"{TIKTOK_API_BASE}/v2/post/publish/status/fetch/",
                headers={
                    "Authorization": f"Bearer {self._credentials.access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "publish_id": publish_id
                },
                timeout=30
            )

            if response.status_code != 200:
                return {"status": "ERROR", "error": f"HTTP {response.status_code}"}

            data = response.json()

            if data.get("error", {}).get("code") != "ok":
                return {"status": "ERROR", "error": data.get("error", {}).get("message")}

            status = data.get("data", {}).get("status", "UNKNOWN")
            
            # Update pending uploads
            if publish_id in self._pending_uploads:
                self._pending_uploads[publish_id]["status"] = status
                
                if status in ("PUBLISHED_PUBLICLY", "PUBLISHED_PRIVATELY"):
                    # Upload complete
                    if self._on_upload_complete:
                        self._on_upload_complete(self._pending_uploads[publish_id])
                    del self._pending_uploads[publish_id]
                elif status == "FAILED":
                    fail_reason = data.get("data", {}).get("fail_reason", "Unknown")
                    if self._on_upload_error:
                        self._on_upload_error(self._pending_uploads[publish_id], fail_reason)
                    del self._pending_uploads[publish_id]

            return {"status": status, "data": data.get("data", {})}

        except Exception as e:
            logger.error(f"[TikTok] 상태 확인 실패: {e}")
            return {"status": "ERROR", "error": str(e)}

    # ============ Auto-Upload ============

    def start_auto_upload(self) -> None:
        """Start auto-upload background thread"""
        if self._upload_running:
            return

        if not self.is_connected():
            logger.warning("[TikTok] 계정이 연결되지 않았습니다.")
            return

        self._upload_running = True
        self._upload_thread = threading.Thread(target=self._upload_loop, daemon=True)
        self._upload_thread.start()
        logger.info("[TikTok] 자동 업로드 시작")

    def stop_auto_upload(self) -> None:
        """Stop auto-upload background thread"""
        self._upload_running = False
        logger.info("[TikTok] 자동 업로드 중지")

    def _upload_loop(self) -> None:
        """Auto-upload background loop"""
        while self._upload_running and self._upload_settings.enabled:
            try:
                # Check pending uploads status
                for publish_id in list(self._pending_uploads.keys()):
                    self.check_upload_status(publish_id)

                # Check interval
                if self._last_upload_time:
                    elapsed = (datetime.now() - self._last_upload_time).total_seconds()
                    wait_seconds = self._upload_settings.interval_minutes * 60 - elapsed
                    if wait_seconds > 0:
                        time.sleep(min(wait_seconds, 30))  # Check every 30 seconds
                        continue

                # Process queue
                if self._upload_queue:
                    item = self._upload_queue.pop(0)
                    publish_id = self.upload_video(
                        item["video_path"],
                        item.get("caption", "")
                    )

                    if publish_id:
                        self._last_upload_time = datetime.now()
                    else:
                        # Put back to queue on failure
                        self._upload_queue.insert(0, item)
                        if self._on_upload_error:
                            self._on_upload_error(item, "Upload initialization failed")

                time.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"[TikTok] 자동 업로드 오류: {e}")
                time.sleep(60)

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

    def get_pending_count(self) -> int:
        """Get number of uploads currently processing"""
        return len(self._pending_uploads)

    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            "connected": self.is_connected(),
            "username": self._channel.username if self._channel else "",
            "display_name": self._channel.display_name if self._channel else "",
            "auto_upload_enabled": self._upload_settings.enabled,
            "upload_interval_minutes": self._upload_settings.interval_minutes,
            "queue_count": len(self._upload_queue),
            "pending_count": len(self._pending_uploads),
            "is_uploading": self._upload_running,
            "token_valid": self.is_token_valid()
        }


# Global instance
_tiktok_manager: Optional[TikTokManager] = None


def get_tiktok_manager(gui=None) -> TikTokManager:
    """Get global TikTok manager instance"""
    global _tiktok_manager
    if _tiktok_manager is None:
        _tiktok_manager = TikTokManager(gui=gui)
    return _tiktok_manager
