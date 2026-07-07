# -*- coding: utf-8 -*-
"""
Instagram Manager for Account Connection and Auto-Upload (Official Graph API)
인스타그램 계정 연결 및 릴스 자동 업로드 매니저 (공식 Graph API)

Handles:
- Facebook Login for Business OAuth 2.0 (local loopback flow)
- Long-lived token exchange + refresh
- Page -> Instagram professional account discovery
- Reels publishing via resumable upload (rupload.facebook.com)
- Publish rate-limit check (100 posts / 24h)
- Auto-upload queue with interval scheduling

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing/
"""

import json
import os
import re
import secrets as _secrets
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode, urlparse, parse_qs
from dataclasses import dataclass

import requests

from utils.logging_config import get_logger

logger = get_logger(__name__)

# Instagram Graph API Configuration (Instagram API with Facebook Login)
INSTAGRAM_GRAPH_API_VERSION = "v23.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{INSTAGRAM_GRAPH_API_VERSION}"
RUPLOAD_API_BASE = f"https://rupload.facebook.com/ig-api-upload/{INSTAGRAM_GRAPH_API_VERSION}"
FB_OAUTH_DIALOG_URL = f"https://www.facebook.com/{INSTAGRAM_GRAPH_API_VERSION}/dialog/oauth"

COUPANG_AFFILIATE_DISCLOSURE = (
    "이 게시물은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)

# Reels caption hard limit
INSTAGRAM_CAPTION_MAX_LEN = 2200
# Meta publish rate limit (rolling 24h)
INSTAGRAM_PUBLISH_LIMIT_24H = 100

# Loopback OAuth ports (fixed first so users can whitelist a stable redirect URI)
OAUTH_LOOPBACK_PORTS = (8951, 8952, 8953, 8954)


@dataclass
class InstagramAccount:
    """Connected Instagram professional account data structure"""
    ig_user_id: str = ""
    username: str = ""
    page_id: str = ""
    page_name: str = ""
    profile_picture_url: str = ""
    connected_at: str = ""


@dataclass
class InstagramUploadSettings:
    """Instagram auto-upload settings data structure"""
    enabled: bool = False
    interval_minutes: int = 60  # 릴스 업로드 간격 (분)
    share_to_feed: bool = True  # 릴스를 피드에도 노출
    max_retries: int = 3  # 항목당 재시도 횟수


@dataclass
class InstagramCredentials:
    """Instagram OAuth credentials (Facebook Login for Business)"""
    user_access_token: str = ""  # long-lived user token (~60 days)
    page_access_token: str = ""  # page token derived from user token
    expires_at: float = 0.0  # user token expiry (unix timestamp)
    scope: str = ""


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Minimal loopback handler capturing the OAuth redirect."""

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        parsed = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        # Store result on server object for the waiting thread.
        if parsed.path in ("", "/", "/callback"):
            self.server.oauth_result = params  # type: ignore[attr-defined]
        body = (
            "<html><head><meta charset='utf-8'><title>SSMaker</title></head>"
            "<body style='font-family:sans-serif;text-align:center;margin-top:80px;'>"
            "<h2>인스타그램 연결 승인 완료</h2>"
            "<p>이 창을 닫고 SSMaker 앱으로 돌아가세요.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def log_message(self, format, *args):  # noqa: A002 (match stdlib signature)
        return  # silence default request logging


class InstagramManager:
    """
    Instagram Reels publishing via official Graph API
    (Instagram API with Facebook Login + resumable upload).
    """

    # Facebook Login for Business permissions for content publishing
    SCOPES = [
        "instagram_basic",
        "instagram_content_publish",
        "pages_show_list",
        "pages_read_engagement",
        "business_management",
    ]
    OAUTH_FLOW_TIMEOUT_SECONDS = 180
    APP_CREDENTIALS_KEY = "instagram_app_credentials_v1"
    TOKEN_REFRESH_MARGIN_SECONDS = 10 * 24 * 3600  # refresh when <10 days left

    def __init__(self, gui=None, settings_file: str = "instagram_settings.json"):
        self.gui = gui
        self.settings_file = settings_file

        # State
        self._account: Optional[InstagramAccount] = None
        self._credentials: Optional[InstagramCredentials] = None
        self._upload_settings = InstagramUploadSettings()
        self._last_error_message: str = ""

        # Auto-upload thread
        self._upload_thread: Optional[threading.Thread] = None
        self._upload_queue: List[Dict[str, Any]] = []
        self._upload_running = False
        self._last_upload_time: Optional[datetime] = None

        # Callbacks
        self._on_upload_complete: Optional[Callable] = None
        self._on_upload_error: Optional[Callable] = None
        self._on_connection_changed: Optional[Callable] = None

        self._load_settings()

    # ============ Paths / Persistence ============

    def _get_user_data_dir(self) -> str:
        """Per-user writable directory for persisted app data."""
        return os.path.join(os.path.expanduser("~"), ".ssmaker")

    def _get_settings_path(self) -> str:
        return os.path.join(self._get_user_data_dir(), self.settings_file)

    @staticmethod
    def _encrypt_secret(value: str) -> str:
        """Encrypt sensitive token value for local persistence."""
        if not value:
            return value
        try:
            from utils.secrets_manager import SecretsManager
            return SecretsManager._simple_encrypt(value)
        except Exception as e:
            logger.warning(f"[Instagram] Token encryption failed, storing plaintext: {e}")
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
                logger.warning(f"[Instagram] Token decryption failed: {e}")
                return ""
        return value

    def _load_settings(self) -> None:
        """Load account/credentials/upload settings from file."""
        settings_path = self._get_settings_path()
        try:
            if not os.path.exists(settings_path):
                return
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "account" in data:
                acc = data["account"]
                self._account = InstagramAccount(
                    ig_user_id=str(acc.get("ig_user_id", "") or ""),
                    username=str(acc.get("username", "") or ""),
                    page_id=str(acc.get("page_id", "") or ""),
                    page_name=str(acc.get("page_name", "") or ""),
                    profile_picture_url=str(acc.get("profile_picture_url", "") or ""),
                    connected_at=str(acc.get("connected_at", "") or ""),
                )

            if "credentials" in data:
                cred = data["credentials"]
                self._credentials = InstagramCredentials(
                    user_access_token=self._decrypt_secret(str(cred.get("user_access_token", "") or "")),
                    page_access_token=self._decrypt_secret(str(cred.get("page_access_token", "") or "")),
                    expires_at=float(cred.get("expires_at", 0.0) or 0.0),
                    scope=str(cred.get("scope", "") or ""),
                )

            if "upload_settings" in data:
                us = data["upload_settings"]
                self._upload_settings = InstagramUploadSettings(
                    enabled=bool(us.get("enabled", False)),
                    interval_minutes=int(us.get("interval_minutes", 60)),
                    share_to_feed=bool(us.get("share_to_feed", True)),
                    max_retries=int(us.get("max_retries", 3)),
                )

            logger.debug("[Instagram] 설정 로드 완료")
            self._sync_settings_manager_state()
        except Exception as e:
            logger.error(f"[Instagram] 설정 로드 실패: {e}")

    def _save_settings(self) -> bool:
        """Save account/credentials/upload settings to file."""
        settings_path = self._get_settings_path()
        try:
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            data = {
                "account": {
                    "ig_user_id": self._account.ig_user_id if self._account else "",
                    "username": self._account.username if self._account else "",
                    "page_id": self._account.page_id if self._account else "",
                    "page_name": self._account.page_name if self._account else "",
                    "profile_picture_url": self._account.profile_picture_url if self._account else "",
                    "connected_at": self._account.connected_at if self._account else "",
                },
                "credentials": {
                    "user_access_token": (
                        self._encrypt_secret(self._credentials.user_access_token)
                        if self._credentials else ""
                    ),
                    "page_access_token": (
                        self._encrypt_secret(self._credentials.page_access_token)
                        if self._credentials else ""
                    ),
                    "expires_at": self._credentials.expires_at if self._credentials else 0.0,
                    "scope": self._credentials.scope if self._credentials else "",
                },
                "upload_settings": {
                    "enabled": self._upload_settings.enabled,
                    "interval_minutes": self._upload_settings.interval_minutes,
                    "share_to_feed": self._upload_settings.share_to_feed,
                    "max_retries": self._upload_settings.max_retries,
                },
            }
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("[Instagram] 설정 저장 완료")
            return True
        except Exception as e:
            logger.error(f"[Instagram] 설정 저장 실패: {e}")
            return False

    def _sync_settings_manager_state(self) -> None:
        """Keep shared SettingsManager in sync with connection state."""
        try:
            from managers.settings_manager import get_settings_manager
            settings = get_settings_manager()
            if self.is_connected():
                settings.set_social_connection_status(
                    "instagram", True, account_name=self._account.username
                )
            else:
                settings.set_social_connection_status("instagram", False)
        except Exception as exc:
            logger.debug("[Instagram] SettingsManager sync skipped: %s", exc)

    # ============ App credentials (Meta App ID / Secret) ============

    def install_app_credentials(self, app_id: str, app_secret: str) -> bool:
        """Validate and store Meta app credentials in secure storage."""
        app_id = str(app_id or "").strip()
        app_secret = str(app_secret or "").strip()
        if not re.fullmatch(r"\d{5,32}", app_id):
            raise ValueError("Meta 앱 ID 형식이 올바르지 않습니다. (숫자만)")
        if not re.fullmatch(r"[0-9a-f]{16,64}", app_secret.lower()):
            raise ValueError("Meta 앱 시크릿 코드 형식이 올바르지 않습니다.")
        try:
            from utils.secrets_manager import get_secrets_manager
            payload = json.dumps({"app_id": app_id, "app_secret": app_secret})
            ok = bool(get_secrets_manager().set_credential(self.APP_CREDENTIALS_KEY, payload))
            if ok:
                logger.info("[Instagram] Meta app credentials securely stored")
            return ok
        except Exception as e:
            logger.error("[Instagram] Failed to store app credentials: %s", e)
            return False

    def load_app_credentials(self) -> Dict[str, str]:
        """Load Meta app credentials from secure storage."""
        try:
            from utils.secrets_manager import get_secrets_manager
            payload = get_secrets_manager().get_credential(self.APP_CREDENTIALS_KEY)
            if not payload:
                return {}
            data = json.loads(payload)
            app_id = str(data.get("app_id", "") or "").strip()
            app_secret = str(data.get("app_secret", "") or "").strip()
            if app_id and app_secret:
                return {"app_id": app_id, "app_secret": app_secret}
        except Exception as e:
            logger.debug("[Instagram] Failed to read app credentials: %s", e)
        return {}

    def has_app_credentials(self) -> bool:
        return bool(self.load_app_credentials())

    # ============ Connection state ============

    def is_connected(self) -> bool:
        """Check if an Instagram professional account is connected."""
        return (
            self._account is not None
            and self._account.ig_user_id != ""
            and self._credentials is not None
            and self._credentials.user_access_token != ""
        )

    def is_token_valid(self) -> bool:
        """Check if the long-lived user token is still valid."""
        if not self._credentials or not self._credentials.user_access_token:
            return False
        if self._credentials.expires_at <= 0:
            return True  # unknown expiry: assume valid, API errors will surface
        return time.time() < self._credentials.expires_at - 300

    def get_account_info(self) -> Dict[str, Any]:
        """Get connected account info as dictionary."""
        if self._account is None:
            return {}
        return {
            "id": self._account.ig_user_id,
            "username": self._account.username,
            "name": self._account.username,
            "page_id": self._account.page_id,
            "page_name": self._account.page_name,
            "profile_picture_url": self._account.profile_picture_url,
            "connected_at": self._account.connected_at,
            "profile_url": f"https://www.instagram.com/{self._account.username}/" if self._account.username else "",
        }

    def get_last_error(self) -> str:
        return self._last_error_message

    # ============ OAuth (Facebook Login for Business, loopback) ============

    def _run_loopback_server(self, timeout_seconds: int) -> Optional[Dict[str, str]]:
        """Bind loopback server, open browser, wait for OAuth redirect."""
        server = None
        port = 0
        for candidate in OAUTH_LOOPBACK_PORTS:
            try:
                server = HTTPServer(("127.0.0.1", candidate), _OAuthCallbackHandler)
                port = candidate
                break
            except OSError:
                continue
        if server is None:
            self._last_error_message = (
                "로컬 인증 포트를 열 수 없습니다. 다른 프로그램이 포트를 사용 중인지 확인해주세요."
            )
            return None

        server.oauth_result = None  # type: ignore[attr-defined]
        server.timeout = 1
        redirect_uri = f"http://localhost:{port}/"
        state = _secrets.token_urlsafe(24)

        creds = self.load_app_credentials()
        auth_url = FB_OAUTH_DIALOG_URL + "?" + urlencode({
            "client_id": creds["app_id"],
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": ",".join(self.SCOPES),
        })

        try:
            webbrowser.open(auth_url)
        except Exception as e:
            logger.warning("[Instagram] 브라우저 열기 실패, URL 수동 안내 필요: %s", e)

        deadline = time.time() + max(30, timeout_seconds)
        result: Optional[Dict[str, str]] = None
        try:
            while time.time() < deadline:
                server.handle_request()
                captured = getattr(server, "oauth_result", None)
                if captured:
                    result = dict(captured)
                    break
        finally:
            try:
                server.server_close()
            except Exception:
                pass

        if result is None:
            self._last_error_message = (
                "인스타그램 연결 승인이 완료되지 않았습니다. "
                "브라우저에서 Facebook 로그인/승인 후 다시 시도하세요."
            )
            return None
        if result.get("error"):
            desc = result.get("error_description") or result.get("error_reason") or result.get("error")
            self._last_error_message = f"Facebook 승인 거부/오류: {desc}"
            return None
        if result.get("state") != state:
            self._last_error_message = "OAuth state 검증에 실패했습니다. 다시 시도해주세요."
            return None
        if not result.get("code"):
            self._last_error_message = "승인 코드(code)를 받지 못했습니다. 다시 시도해주세요."
            return None
        result["redirect_uri"] = redirect_uri
        return result

    def _exchange_code_for_token(self, code: str, redirect_uri: str) -> Optional[str]:
        """Exchange authorization code for a short-lived user token."""
        creds = self.load_app_credentials()
        try:
            response = requests.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "client_id": creds["app_id"],
                    "client_secret": creds["app_secret"],
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
                timeout=30,
            )
            data = response.json() if response.content else {}
            if response.status_code != 200 or "access_token" not in data:
                self._last_error_message = self._format_graph_error("토큰 교환 실패", response)
                return None
            return str(data["access_token"])
        except Exception as e:
            self._last_error_message = f"토큰 교환 중 오류: {e}"
            return None

    def _exchange_for_long_lived_token(self, short_token: str) -> Optional[Dict[str, Any]]:
        """Exchange short-lived token for a long-lived (~60 days) token."""
        creds = self.load_app_credentials()
        try:
            response = requests.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": creds["app_id"],
                    "client_secret": creds["app_secret"],
                    "fb_exchange_token": short_token,
                },
                timeout=30,
            )
            data = response.json() if response.content else {}
            if response.status_code != 200 or "access_token" not in data:
                self._last_error_message = self._format_graph_error("장기 토큰 교환 실패", response)
                return None
            return {
                "access_token": str(data["access_token"]),
                "expires_in": int(data.get("expires_in", 60 * 24 * 3600) or 60 * 24 * 3600),
            }
        except Exception as e:
            self._last_error_message = f"장기 토큰 교환 중 오류: {e}"
            return None

    def _discover_instagram_account(self, user_token: str) -> Optional[Dict[str, Any]]:
        """Find first Facebook page with a linked Instagram professional account."""
        try:
            response = requests.get(
                f"{GRAPH_API_BASE}/me/accounts",
                params={
                    "fields": (
                        "id,name,access_token,"
                        "instagram_business_account{id,username,profile_picture_url}"
                    ),
                    "limit": 50,
                    "access_token": user_token,
                },
                timeout=30,
            )
            data = response.json() if response.content else {}
            if response.status_code != 200:
                self._last_error_message = self._format_graph_error("페이지 목록 조회 실패", response)
                return None

            pages = data.get("data", []) or []
            if not pages:
                self._last_error_message = (
                    "연결 가능한 Facebook 페이지가 없습니다. "
                    "인스타그램 프로페셔널 계정과 연결된 페이지가 필요합니다."
                )
                return None

            for page in pages:
                ig = page.get("instagram_business_account") or {}
                if ig.get("id"):
                    return {
                        "page_id": str(page.get("id", "")),
                        "page_name": str(page.get("name", "")),
                        "page_access_token": str(page.get("access_token", "")),
                        "ig_user_id": str(ig.get("id", "")),
                        "username": str(ig.get("username", "")),
                        "profile_picture_url": str(ig.get("profile_picture_url", "") or ""),
                    }

            self._last_error_message = (
                "Facebook 페이지에 연결된 인스타그램 프로페셔널 계정을 찾지 못했습니다.\n"
                "인스타그램 앱에서 [프로페셔널 계정 전환] 후 Facebook 페이지와 연결해주세요."
            )
            return None
        except Exception as e:
            self._last_error_message = f"인스타그램 계정 조회 중 오류: {e}"
            return None

    def connect_account(
        self,
        app_id: str = "",
        app_secret: str = "",
        oauth_timeout_seconds: Optional[int] = None,
    ) -> bool:
        """
        Connect Instagram professional account using Facebook Login OAuth.

        Args:
            app_id: Meta app ID (uses stored credentials if empty)
            app_secret: Meta app secret (uses stored credentials if empty)
            oauth_timeout_seconds: browser approval wait timeout

        Returns:
            True if connection successful
        """
        self._last_error_message = ""

        if app_id and app_secret:
            try:
                if not self.install_app_credentials(app_id, app_secret):
                    self._last_error_message = "Meta 앱 정보를 안전 저장소에 저장하지 못했습니다."
                    return False
            except ValueError as ve:
                self._last_error_message = str(ve)
                return False

        if not self.has_app_credentials():
            self._last_error_message = (
                "Meta 앱 ID/시크릿 코드가 없습니다. developers.facebook.com에서 앱을 만들고 입력해주세요."
            )
            return False

        timeout_seconds = (
            oauth_timeout_seconds
            if oauth_timeout_seconds is not None
            else self.OAUTH_FLOW_TIMEOUT_SECONDS
        )

        oauth_result = self._run_loopback_server(timeout_seconds)
        if not oauth_result:
            return False

        short_token = self._exchange_code_for_token(
            oauth_result["code"], oauth_result["redirect_uri"]
        )
        if not short_token:
            return False

        long_lived = self._exchange_for_long_lived_token(short_token)
        if not long_lived:
            return False

        discovered = self._discover_instagram_account(long_lived["access_token"])
        if not discovered:
            return False

        self._credentials = InstagramCredentials(
            user_access_token=long_lived["access_token"],
            page_access_token=discovered["page_access_token"],
            expires_at=time.time() + long_lived["expires_in"],
            scope=",".join(self.SCOPES),
        )
        self._account = InstagramAccount(
            ig_user_id=discovered["ig_user_id"],
            username=discovered["username"],
            page_id=discovered["page_id"],
            page_name=discovered["page_name"],
            profile_picture_url=discovered["profile_picture_url"],
            connected_at=datetime.now().isoformat(),
        )
        self._save_settings()
        self._sync_settings_manager_state()
        logger.info(
            "[Instagram] 계정 연결: @%s (page: %s)",
            self._account.username,
            self._account.page_name,
        )

        if self._on_connection_changed:
            try:
                self._on_connection_changed(True)
            except Exception:
                pass
        return True

    def disconnect_account(self) -> None:
        """Disconnect Instagram account and clear stored tokens."""
        self._account = None
        self._credentials = None
        self._save_settings()
        self._sync_settings_manager_state()
        self.stop_auto_upload()
        if self._on_connection_changed:
            try:
                self._on_connection_changed(False)
            except Exception:
                pass
        logger.info("[Instagram] 계정 연결 해제")

    def refresh_access_token(self) -> bool:
        """Refresh long-lived user token and re-derive page token."""
        if not self._credentials or not self._credentials.user_access_token:
            return False
        long_lived = self._exchange_for_long_lived_token(self._credentials.user_access_token)
        if not long_lived:
            return False
        discovered = self._discover_instagram_account(long_lived["access_token"])
        if not discovered:
            return False
        self._credentials.user_access_token = long_lived["access_token"]
        self._credentials.page_access_token = discovered["page_access_token"]
        self._credentials.expires_at = time.time() + long_lived["expires_in"]
        self._save_settings()
        logger.info("[Instagram] 액세스 토큰 갱신 완료")
        return True

    def _ensure_token_fresh(self) -> bool:
        """Refresh token proactively when close to expiry."""
        if not self._credentials or not self._credentials.user_access_token:
            return False
        if self._credentials.expires_at <= 0:
            return True
        remaining = self._credentials.expires_at - time.time()
        if remaining < self.TOKEN_REFRESH_MARGIN_SECONDS:
            if not self.refresh_access_token() and remaining <= 300:
                self._last_error_message = (
                    "인스타그램 토큰이 만료되었습니다. 계정을 다시 연결해주세요."
                )
                return False
        return True

    # ============ Upload Settings ============

    def get_upload_settings(self) -> InstagramUploadSettings:
        return self._upload_settings

    def set_upload_enabled(self, enabled: bool) -> None:
        self._upload_settings.enabled = bool(enabled)
        self._save_settings()
        if enabled:
            self.start_auto_upload()
        else:
            self.stop_auto_upload()

    def set_upload_interval(self, minutes: int) -> None:
        self._upload_settings.interval_minutes = max(1, min(1440, int(minutes)))
        self._save_settings()

    def set_share_to_feed(self, share_to_feed: bool) -> None:
        self._upload_settings.share_to_feed = bool(share_to_feed)
        self._save_settings()

    # ============ Caption ============

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
        max_length: int = INSTAGRAM_CAPTION_MAX_LEN,
    ) -> str:
        """
        Build a Reels caption from title/description/hashtags.
        쿠팡 링크가 포함되면 파트너스 고지 문구를 보장한다.
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
        hashtag_str = " ".join(f"#{t}" for t in tags[:15])

        parts = [p for p in (title_line, body) if p]
        caption = "\n\n".join(parts)

        is_coupang = "coupang.com" in str(purchase_link or "").lower()
        if is_coupang and COUPANG_AFFILIATE_DISCLOSURE not in caption:
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

    # ============ Publishing (Reels via resumable upload) ============

    @staticmethod
    def _format_graph_error(prefix: str, response: Any) -> str:
        """Build a readable error string from a Graph API response."""
        detail = ""
        try:
            payload = response.json() if response.content else {}
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            detail = str(
                err.get("error_user_msg")
                or err.get("message")
                or payload
            )[:300]
        except Exception:
            detail = str(getattr(response, "text", ""))[:300]
        return f"{prefix} (HTTP {getattr(response, 'status_code', '?')}): {detail}"

    def check_publish_limit(self) -> Dict[str, Any]:
        """Check current 24h publish quota usage."""
        result = {"ok": False, "quota_usage": -1, "quota_total": INSTAGRAM_PUBLISH_LIMIT_24H}
        if not self.is_connected():
            return result
        try:
            response = requests.get(
                f"{GRAPH_API_BASE}/{self._account.ig_user_id}/content_publishing_limit",
                params={
                    "fields": "quota_usage,config",
                    "access_token": self._credentials.page_access_token,
                },
                timeout=30,
            )
            data = response.json() if response.content else {}
            entries = data.get("data", []) or []
            if response.status_code == 200 and entries:
                entry = entries[0]
                result["ok"] = True
                result["quota_usage"] = int(entry.get("quota_usage", 0) or 0)
                config = entry.get("config", {}) or {}
                result["quota_total"] = int(config.get("quota_total", INSTAGRAM_PUBLISH_LIMIT_24H))
        except Exception as e:
            logger.debug("[Instagram] 발행 한도 조회 실패: %s", e)
        return result

    def _create_reels_container(self, caption: str) -> Optional[str]:
        """Step 1: create a REELS media container for resumable upload."""
        try:
            response = requests.post(
                f"{GRAPH_API_BASE}/{self._account.ig_user_id}/media",
                data={
                    "media_type": "REELS",
                    "upload_type": "resumable",
                    "caption": caption,
                    "share_to_feed": "true" if self._upload_settings.share_to_feed else "false",
                    "access_token": self._credentials.page_access_token,
                },
                timeout=60,
            )
            data = response.json() if response.content else {}
            if response.status_code != 200 or not data.get("id"):
                self._last_error_message = self._format_graph_error("컨테이너 생성 실패", response)
                logger.error("[Instagram] %s", self._last_error_message)
                return None
            return str(data["id"])
        except Exception as e:
            self._last_error_message = f"컨테이너 생성 중 오류: {e}"
            logger.error("[Instagram] %s", self._last_error_message)
            return None

    def _upload_video_binary(self, container_id: str, video_path: str) -> bool:
        """Step 2: upload the local video binary to rupload.facebook.com."""
        try:
            file_size = os.path.getsize(video_path)
            with open(video_path, "rb") as f:
                response = requests.post(
                    f"{RUPLOAD_API_BASE}/{container_id}",
                    headers={
                        "Authorization": f"OAuth {self._credentials.page_access_token}",
                        "offset": "0",
                        "file_size": str(file_size),
                        "Content-Type": "application/octet-stream",
                    },
                    data=f,
                    timeout=600,
                )
            data = {}
            try:
                data = response.json() if response.content else {}
            except Exception:
                pass
            if response.status_code == 200 and data.get("success"):
                logger.debug("[Instagram] 영상 바이너리 업로드 완료 (%d bytes)", file_size)
                return True
            debug_info = data.get("debug_info", {}) if isinstance(data, dict) else {}
            self._last_error_message = (
                f"영상 업로드 실패 (HTTP {response.status_code}): "
                f"{debug_info.get('message') or debug_info.get('type') or str(data)[:200]}"
            )
            logger.error("[Instagram] %s", self._last_error_message)
            return False
        except Exception as e:
            self._last_error_message = f"영상 업로드 중 오류: {e}"
            logger.error("[Instagram] %s", self._last_error_message)
            return False

    def _wait_container_ready(
        self,
        container_id: str,
        poll_interval_seconds: int = 15,
        max_wait_seconds: int = 360,
    ) -> bool:
        """Step 3: poll container status until FINISHED."""
        deadline = time.time() + max_wait_seconds
        last_status = ""
        while time.time() < deadline:
            try:
                response = requests.get(
                    f"{GRAPH_API_BASE}/{container_id}",
                    params={
                        "fields": "status_code,status",
                        "access_token": self._credentials.page_access_token,
                    },
                    timeout=30,
                )
                data = response.json() if response.content else {}
                status_code = str(data.get("status_code", "") or "").upper()
                last_status = str(data.get("status", "") or "")
                if status_code == "FINISHED":
                    return True
                if status_code in ("ERROR", "EXPIRED"):
                    self._last_error_message = (
                        f"영상 처리 실패 (status={status_code}): {last_status[:200]}"
                    )
                    logger.error("[Instagram] %s", self._last_error_message)
                    return False
                logger.debug("[Instagram] 컨테이너 처리 중: %s", status_code or "UNKNOWN")
            except Exception as e:
                logger.debug("[Instagram] 상태 조회 오류(재시도): %s", e)
            time.sleep(poll_interval_seconds)

        self._last_error_message = f"영상 처리 대기 시간 초과: {last_status[:200]}"
        logger.error("[Instagram] %s", self._last_error_message)
        return False

    def _publish_container(self, container_id: str) -> Optional[str]:
        """Step 4: publish the finished container. Returns media id."""
        try:
            response = requests.post(
                f"{GRAPH_API_BASE}/{self._account.ig_user_id}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": self._credentials.page_access_token,
                },
                timeout=60,
            )
            data = response.json() if response.content else {}
            if response.status_code != 200 or not data.get("id"):
                self._last_error_message = self._format_graph_error("게시 실패", response)
                logger.error("[Instagram] %s", self._last_error_message)
                return None
            return str(data["id"])
        except Exception as e:
            self._last_error_message = f"게시 중 오류: {e}"
            logger.error("[Instagram] %s", self._last_error_message)
            return None

    def _fetch_permalink(self, media_id: str) -> str:
        """Fetch the published post permalink (best effort)."""
        try:
            response = requests.get(
                f"{GRAPH_API_BASE}/{media_id}",
                params={
                    "fields": "permalink",
                    "access_token": self._credentials.page_access_token,
                },
                timeout=30,
            )
            data = response.json() if response.content else {}
            return str(data.get("permalink", "") or "")
        except Exception:
            return ""

    def upload_reel(self, video_path: str, caption: str = "") -> Optional[str]:
        """
        Publish a local video file as an Instagram Reel (official API).

        Flow: create container(resumable) -> upload binary -> poll status -> publish.

        Args:
            video_path: Local MP4 path (9:16, 3s~15min, <=1GB recommended)
            caption: Reels caption (max 2200 chars)

        Returns:
            Published media ID, or None on failure.
        """
        self._last_error_message = ""

        if not self.is_connected():
            self._last_error_message = "인스타그램 계정이 연결되지 않았습니다."
            logger.error("[Instagram] %s", self._last_error_message)
            return None

        if not self._ensure_token_fresh():
            logger.error("[Instagram] %s", self._last_error_message or "토큰 갱신 실패")
            return None

        if not os.path.exists(video_path):
            self._last_error_message = f"비디오 파일 없음: {video_path}"
            logger.error("[Instagram] %s", self._last_error_message)
            return None

        file_size = os.path.getsize(video_path)
        if file_size > 1024 * 1024 * 1024:
            self._last_error_message = "파일 크기 초과 (최대 1GB)"
            logger.error("[Instagram] %s", self._last_error_message)
            return None

        limit = self.check_publish_limit()
        if limit["ok"] and limit["quota_usage"] >= limit["quota_total"]:
            self._last_error_message = (
                f"인스타그램 24시간 발행 한도({limit['quota_total']}건)에 도달했습니다. "
                "잠시 후 다시 시도됩니다."
            )
            logger.warning("[Instagram] %s", self._last_error_message)
            return None

        caption = str(caption or "")[:INSTAGRAM_CAPTION_MAX_LEN]

        container_id = self._create_reels_container(caption)
        if not container_id:
            return None

        if not self._upload_video_binary(container_id, video_path):
            return None

        if not self._wait_container_ready(container_id):
            return None

        media_id = self._publish_container(container_id)
        if not media_id:
            return None

        permalink = self._fetch_permalink(media_id)
        logger.info(
            "[Instagram] 릴스 게시 완료: %s %s",
            media_id,
            permalink or "(permalink 조회 실패)",
        )
        return media_id

    # ============ Auto-Upload Queue ============

    def add_to_upload_queue(
        self,
        video_path: str,
        title: str = "",
        description: str = "",
        hashtags: Optional[List[str]] = None,
        source_url: str = "",
        coupang_deep_link: str = "",
        render_integrity: Optional[Dict[str, Any]] = None,
        render_integrity_required: bool = False,
        upload_number: Optional[int] = None,
    ) -> None:
        """
        Add video to Reels upload queue (caption auto-built).

        Args mirror YouTubeManager.add_to_upload_queue for pipeline symmetry.
        """
        if render_integrity_required and not (render_integrity or {}).get("ok"):
            logger.warning("[Instagram] Upload blocked: render integrity was not verified.")
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
            "retry_count": 0,
            "render_integrity": render_integrity or {},
            "render_integrity_required": bool(render_integrity_required),
            "added_at": datetime.now().isoformat(),
        })
        logger.info("[Instagram] 업로드 대기열 추가: %s", os.path.basename(video_path))

        if self._upload_settings.enabled and self.is_connected() and not self._upload_running:
            self.start_auto_upload()

    def start_auto_upload(self) -> None:
        """Start auto-upload background thread."""
        if self._upload_running:
            return
        if not self.is_connected():
            logger.warning("[Instagram] 계정이 연결되지 않았습니다.")
            return
        self._upload_running = True
        self._upload_thread = threading.Thread(target=self._upload_loop, daemon=True)
        self._upload_thread.start()
        logger.info("[Instagram] 자동 업로드 시작")

    def stop_auto_upload(self) -> None:
        """Stop auto-upload background thread."""
        self._upload_running = False
        logger.info("[Instagram] 자동 업로드 중지")

    def _upload_loop(self) -> None:
        """Auto-upload background loop (interval-based, mirrors YouTubeManager)."""
        while self._upload_running and self._upload_settings.enabled:
            try:
                if self._last_upload_time:
                    elapsed = (datetime.now() - self._last_upload_time).total_seconds()
                    wait_seconds = self._upload_settings.interval_minutes * 60 - elapsed
                    if wait_seconds > 0:
                        time.sleep(min(wait_seconds, 10))
                        continue

                if self._upload_queue:
                    item = self._upload_queue.pop(0)
                    media_id = self.upload_reel(item["video_path"], item.get("caption", ""))

                    if media_id:
                        item["media_id"] = media_id
                        self._last_upload_time = datetime.now()
                        if self._on_upload_complete:
                            try:
                                self._on_upload_complete(item)
                            except Exception:
                                pass
                    else:
                        item["retry_count"] = int(item.get("retry_count", 0)) + 1
                        error_message = self._last_error_message or "Upload failed"
                        if item["retry_count"] < self._upload_settings.max_retries:
                            self._upload_queue.insert(0, item)
                            logger.warning(
                                "[Instagram] 업로드 실패, 재시도 대기 (%d/%d): %s",
                                item["retry_count"],
                                self._upload_settings.max_retries,
                                error_message,
                            )
                        else:
                            logger.error(
                                "[Instagram] 업로드 %d회 실패, 대기열에서 제거: %s",
                                item["retry_count"],
                                error_message,
                            )
                        if self._on_upload_error:
                            try:
                                self._on_upload_error(item, error_message)
                            except Exception:
                                pass

                time.sleep(10)
            except Exception as e:
                logger.error(f"[Instagram] 자동 업로드 오류: {e}")
                time.sleep(30)

    # ============ Callbacks / Status ============

    def set_on_upload_complete(self, callback: Callable) -> None:
        self._on_upload_complete = callback

    def set_on_upload_error(self, callback: Callable) -> None:
        self._on_upload_error = callback

    def set_on_connection_changed(self, callback: Callable) -> None:
        self._on_connection_changed = callback

    def get_queue_count(self) -> int:
        return len(self._upload_queue)

    def get_status(self) -> Dict[str, Any]:
        """Get manager status snapshot for UI."""
        return {
            "connected": self.is_connected(),
            "username": self._account.username if self._account else "",
            "page_name": self._account.page_name if self._account else "",
            "has_app_credentials": self.has_app_credentials(),
            "token_valid": self.is_token_valid(),
            "auto_upload_enabled": self._upload_settings.enabled,
            "interval_minutes": self._upload_settings.interval_minutes,
            "queue_count": self.get_queue_count(),
            "upload_running": self._upload_running,
            "last_error": self._last_error_message,
        }


# ============ Singleton ============

_instagram_manager: Optional[InstagramManager] = None


def get_instagram_manager(gui=None) -> InstagramManager:
    """Get or create the global InstagramManager instance."""
    global _instagram_manager
    if _instagram_manager is None:
        _instagram_manager = InstagramManager(gui=gui)
    elif gui is not None and _instagram_manager.gui is None:
        _instagram_manager.gui = gui
    return _instagram_manager
