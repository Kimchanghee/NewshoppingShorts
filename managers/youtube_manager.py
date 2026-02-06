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
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

from utils.logging_config import get_logger

logger = get_logger(__name__)

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
        "https://www.googleapis.com/auth/youtube.readonly"
    ]

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
        self._upload_settings = AutoUploadSettings()

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

    def _get_settings_path(self) -> str:
        """Get full path to settings file"""
        try:
            import sys
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            logger.debug(f"[YouTube] 기본 경로 감지 실패, cwd 사용: {e}")
            base_dir = os.getcwd()
        return os.path.join(base_dir, self.settings_file)

    def _load_settings(self) -> None:
        """Load settings from file"""
        settings_path = self._get_settings_path()

        try:
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
        except Exception as e:
            logger.error(f"[YouTube] 설정 로드 실패: {e}")

    def _save_settings(self) -> bool:
        """Save settings to file"""
        settings_path = self._get_settings_path()

        try:
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

    def connect_channel(self, client_secrets_file: str = None) -> bool:
        """
        Connect to YouTube channel using OAuth 2.0.

        Args:
            client_secrets_file: Path to OAuth client secrets file

        Returns:
            True if connection successful
        """
        if not YOUTUBE_API_AVAILABLE:
            logger.warning("[YouTube] YouTube API 라이브러리가 설치되지 않았습니다.")
            return False

        try:
            # Check for existing credentials
            token_path = self._get_token_path()
            creds = None

            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)

            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not client_secrets_file:
                        client_secrets_file = self._get_client_secrets_path()

                    if not os.path.exists(client_secrets_file):
                        logger.warning("[YouTube] OAuth 클라이언트 설정 파일이 없습니다.")
                        return False

                    flow = InstalledAppFlow.from_client_secrets_file(
                        client_secrets_file, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # Save credentials
                with open(token_path, 'w') as token:
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

        except Exception as e:
            logger.error(f"[YouTube] 연결 실패: {e}")
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

        # Stop auto-upload
        self.stop_auto_upload()

        # Notify callback
        if self._on_connection_changed:
            self._on_connection_changed(False)

    def _get_token_path(self) -> str:
        """Get OAuth token file path"""
        try:
            import sys
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            logger.debug(f"[YouTube] 토큰 경로 감지 실패, cwd 사용: {e}")
            base_dir = os.getcwd()
        return os.path.join(base_dir, "youtube_token.json")

    def _get_client_secrets_path(self) -> str:
        """Get OAuth client secrets file path"""
        try:
            import sys
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            logger.debug(f"[YouTube] 클라이언트 시크릿 경로 감지 실패, cwd 사용: {e}")
            base_dir = os.getcwd()
        return os.path.join(base_dir, "client_secrets.json")

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
        lines = [
            product_info[:200] if product_info else "쇼핑 추천 영상입니다.",
            "",
            "👆 더 많은 정보는 링크에서 확인하세요!",
            "",
            "📱 좋아요와 구독 부탁드립니다!",
            "",
        ]

        if url:
            lines.append(f"🔗 원본: {url}")

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "🎬 AI 쇼핑 쇼츠 메이커로 제작",
            "━━━━━━━━━━━━━━━━━━━━",
        ])

        return "\n".join(lines)

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
        source_url: str = ""
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
        """
        # Generate SEO content if enabled and not provided
        if not title and self._upload_settings.auto_title:
            title = self.generate_seo_title(product_info)

        if not description and self._upload_settings.auto_description:
            description = self.generate_seo_description(product_info, source_url)

        if not tags and self._upload_settings.auto_hashtags:
            tags = self.generate_seo_hashtags(product_info, self._upload_settings.max_hashtags)

        self._upload_queue.append({
            "video_path": video_path,
            "title": title or "쇼핑 추천 영상",
            "description": description or "",
            "tags": tags or [],
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
            return True

        except Exception as e:
            logger.error(f"[YouTube] 업로드 실패: {e}")
            return False

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
