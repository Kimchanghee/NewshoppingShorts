import pytest

from core.download import VideoDownloader


def test_detect_platform_for_supported_hosts():
    assert VideoDownloader.detect_platform("https://v.douyin.com/abc123/") == "douyin"
    assert VideoDownloader.detect_platform("https://www.tiktok.com/@user/video/123") == "tiktok"
    assert VideoDownloader.detect_platform("https://xhslink.com/AbCdEf") == "xiaohongshu"
    assert (
        VideoDownloader.detect_platform("https://www.xiaohongshu.com/explore/123abc")
        == "xiaohongshu"
    )


def test_detect_platform_raises_for_unsupported_host():
    with pytest.raises(ValueError):
        VideoDownloader.detect_platform("https://example.com/video/123")


def test_download_video_routes_xiaohongshu(monkeypatch):
    monkeypatch.setattr(
        VideoDownloader.xiaohongshu,
        "download",
        lambda url, max_retries=3: f"xhs:{url}:{max_retries}",
    )
    out = VideoDownloader.download_video("https://xhslink.com/AbCdEf", max_retries=5)
    assert out == "xhs:https://xhslink.com/AbCdEf:5"


def test_download_video_routes_douyin_tiktok(monkeypatch):
    monkeypatch.setattr(
        VideoDownloader.douyin_tiktok,
        "download",
        lambda url, max_retries=3: f"dy:{url}:{max_retries}",
    )
    out = VideoDownloader.download_video("https://v.douyin.com/abc123/")
    assert out == "dy:https://v.douyin.com/abc123/:3"
