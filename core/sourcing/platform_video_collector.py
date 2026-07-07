# -*- coding: utf-8 -*-
"""
3플랫폼(도우인/샤오홍슈/콰이쇼우) 영상 수집기 — yt-dlp 기반.

풀자동화의 'platform_video' 소싱 방식에서 사용. 상품 리뷰/데모 숏폼을
URL(또는 유저/해시태그 페이지)로 받아 다운로드 + 메타 수집한다.

주의(저작권): 다운로드 원본을 그대로 재업로드하지 말 것. 반드시 재편집
(워터마크 제거·컷·자막·음성/BGM 교체)을 거쳐 변형 저작물로 만들어야 함.
이 모듈은 '수집'만 담당하며, 재편집/업로드는 별도 단계에서 수행한다.

상태: 스캐폴드. 도우인/콰이쇼우는 yt-dlp 추출기 지원. 샤오홍슈(RED)는
yt-dlp 지원이 불안정하여 전용 스크래퍼가 필요(미구현).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

# yt-dlp 추출기가 인식하는 도메인 → 플랫폼 매핑
_PLATFORM_DOMAINS = {
    "douyin": ("douyin.com", "iesdouyin.com"),
    "kuaishou": ("kuaishou.com", "kwai.com", "chenzhongtech.com"),
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com"),
    "bilibili": ("bilibili.com", "b23.tv"),
}

SUPPORTED_BY_YTDLP = {"douyin", "kuaishou", "bilibili"}  # 샤오홍슈는 별도 스크래퍼 필요


@dataclass
class CollectedVideo:
    """수집된 영상 1건."""
    platform: str
    source_url: str
    local_path: str = ""
    title: str = ""
    uploader: str = ""
    duration: float = 0.0
    view_count: int = 0
    width: int = 0
    height: int = 0
    ok: bool = False
    error: str = ""
    meta: Dict = field(default_factory=dict)


def detect_platform(url: str) -> Optional[str]:
    """URL로 플랫폼 식별."""
    u = str(url or "").lower()
    for platform, domains in _PLATFORM_DOMAINS.items():
        if any(d in u for d in domains):
            return platform
    return None


class PlatformVideoCollector:
    """yt-dlp로 도우인/콰이쇼우 숏폼을 다운로드하는 수집기."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or os.path.join(
            os.path.expanduser("~"), ".ssmaker", "platform_video_downloads"
        )
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def _ytdlp_available() -> bool:
        try:
            import yt_dlp  # noqa: F401
            return True
        except Exception:
            return False

    _UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

    _REFERERS = {
        "douyin": "https://www.douyin.com/",
        "kuaishou": "https://www.kuaishou.com/",
        "bilibili": "https://www.bilibili.com/",
    }

    def collect_one(self, url: str, download: bool = True,
                    cookies: Optional[Dict[str, str]] = None) -> CollectedVideo:
        """단일 URL 수집(메타 + 선택적 다운로드).

        cookies: 자동화 브라우저의 세션 쿠키. 빌리빌리는 buvid 쿠키 없이 치면
        HTTP 412(리스크 컨트롤)가 떨어지므로(실측), 쿠키+UA+Referer를 함께 넘긴다.
        """
        platform = detect_platform(url) or "unknown"
        cv = CollectedVideo(platform=platform, source_url=url)

        if platform == "xiaohongshu":
            cv.error = "샤오홍슈는 yt-dlp 미지원 — 전용 스크래퍼 필요(미구현)."
            logger.warning("[Collector] %s", cv.error)
            return cv
        if platform not in SUPPORTED_BY_YTDLP:
            cv.error = f"지원하지 않는 URL/플랫폼: {platform}"
            return cv
        if not self._ytdlp_available():
            cv.error = "yt-dlp가 설치되지 않았습니다. (pip install yt-dlp)"
            logger.warning("[Collector] %s", cv.error)
            return cv

        cookiefile = ""
        try:
            import yt_dlp
            outtmpl = os.path.join(self.output_dir, "%(id)s.%(ext)s")
            headers = {
                "User-Agent": self._UA,
                "Referer": self._REFERERS.get(platform, url),
            }
            opts = {
                "outtmpl": outtmpl,
                "format": "mp4/bestvideo+bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "skip_download": not download,
                "http_headers": headers,
            }
            # 쿠키는 헤더가 아니라 cookiejar(Netscape 파일)로 — 도우인 추출기는
            # 헤더 Cookie를 인식하지 못하고 'Fresh cookies needed'를 낸다(실측).
            cookiefile = self._write_cookiefile(cookies, platform)
            if cookiefile:
                opts["cookiefile"] = cookiefile
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=download)
            cv.title = str(info.get("title", "") or "")
            cv.uploader = str(info.get("uploader", "") or "")
            cv.duration = float(info.get("duration", 0) or 0)
            cv.view_count = int(info.get("view_count", 0) or 0)
            cv.width = int(info.get("width", 0) or 0)
            cv.height = int(info.get("height", 0) or 0)
            cv.meta = {k: info.get(k) for k in ("id", "ext", "like_count", "webpage_url")}
            if download:
                vid_id, ext = info.get("id", ""), info.get("ext", "mp4")
                candidate = os.path.join(self.output_dir, f"{vid_id}.{ext}")
                cv.local_path = candidate if os.path.exists(candidate) else ""
                cv.ok = bool(cv.local_path)
            else:
                cv.ok = True
            logger.info("[Collector] %s 수집 %s: %s", platform, "완료" if cv.ok else "메타만", cv.title[:40])
        except Exception as e:
            cv.error = f"수집 실패: {e}"
            logger.warning("[Collector] %s", cv.error)
        finally:
            if cookiefile:
                try:
                    os.remove(cookiefile)
                except OSError:
                    pass
        return cv

    _COOKIE_DOMAINS = {
        "douyin": ".douyin.com",
        "kuaishou": ".kuaishou.com",
        "bilibili": ".bilibili.com",
    }

    def _write_cookiefile(self, cookies: Optional[Dict[str, str]], platform: str) -> str:
        """브라우저 쿠키 dict → yt-dlp용 Netscape cookiefile(임시). 실패 시 ''."""
        domain = self._COOKIE_DOMAINS.get(platform, "")
        if not domain or not cookies:
            return ""
        try:
            import tempfile
            fd, path = tempfile.mkstemp(suffix=".txt", prefix="ssmaker_ck_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                for k, v in cookies.items():
                    if not k or "\t" in str(k) or "\n" in str(v):
                        continue
                    f.write(f"{domain}\tTRUE\t/\tTRUE\t0\t{k}\t{v}\n")
            return path
        except Exception:
            return ""

    def collect_many(self, urls: List[str], download: bool = True) -> List[CollectedVideo]:
        """여러 URL 수집."""
        results = []
        for u in urls:
            u = str(u or "").strip()
            if not u:
                continue
            results.append(self.collect_one(u, download=download))
        ok = sum(1 for r in results if r.ok)
        logger.info("[Collector] 수집 결과: %d/%d 성공", ok, len(results))
        return results

    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """붙여넣은 텍스트에서 지원 플랫폼 URL만 추출."""
        urls = re.findall(r"https?://[^\s]+", str(text or ""))
        return [u.rstrip(".,)") for u in urls if detect_platform(u)]


_collector: Optional[PlatformVideoCollector] = None


def get_platform_video_collector() -> PlatformVideoCollector:
    global _collector
    if _collector is None:
        _collector = PlatformVideoCollector()
    return _collector
