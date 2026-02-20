from urllib.parse import urlparse

from core.download.platforms import douyin_tiktok, kuaishou, xiaohongshu

_TIKTOK_DOMAINS = ("tiktok.com",)
_DOUYIN_DOMAINS = ("douyin.com", "iesdouyin.com")
_XIAOHONGSHU_DOMAINS = ("xiaohongshu.com", "xhslink.com")
_KUAISHOU_DOMAINS = ("kuaishou.com", "kwai.com")


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    host = (host or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def detect_platform(url: str) -> str:
    host = urlparse((url or "").strip()).netloc.lower()
    raw = (url or "").lower()

    if _host_matches(host, _XIAOHONGSHU_DOMAINS) or any(
        token in raw for token in ("xiaohongshu.com", "xhslink.com")
    ):
        return "xiaohongshu"
    if _host_matches(host, _KUAISHOU_DOMAINS) or any(
        token in raw for token in ("kuaishou.com", "kwai.com")
    ):
        return "kuaishou"
    if _host_matches(host, _DOUYIN_DOMAINS) or "douyin" in host:
        return "douyin"
    if _host_matches(host, _TIKTOK_DOMAINS) or "tiktok" in host:
        return "tiktok"

    raise ValueError("Unsupported URL. Supported: Douyin/TikTok/Xiaohongshu/Kuaishou")


def download_video(url: str, max_retries: int = 3) -> str:
    platform = detect_platform(url)
    if platform == "xiaohongshu":
        return xiaohongshu.download(url, max_retries=max_retries)
    if platform == "kuaishou":
        return kuaishou.download(url, max_retries=max_retries)
    return douyin_tiktok.download(url, max_retries=max_retries)
