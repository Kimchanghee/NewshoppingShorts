# -*- coding: utf-8 -*-
"""3플랫폼 소싱 파이프라인(신규 개선분) 유닛 테스트."""
import asyncio
import json
import os
import sys
import types
from types import SimpleNamespace

import pytest

from core.sourcing import platform_pipeline as pp
from core.sourcing import platform_shorts_searcher as searcher
from core.sourcing import platform_video_collector as collector_mod
from core.video import reeditor
from managers import uploaded_registry as reg_mod


# ── build_queries: 중국어 우선 + 중복 제거 ──

def test_build_queries_orders_chinese_first():
    q = pp.build_queries("미니 선풍기", {"chinese": "迷你风扇", "english": "mini fan"})
    assert q[0] == "迷你风扇"
    assert len(q) == len(set(q))


def test_build_queries_skips_empty_and_duplicates():
    q = pp.build_queries("mini fan", {"chinese": "", "english": "mini fan"})
    assert q == ["mini fan"]


def test_build_queries_adds_chinese_product_family_after_exact_brand_query():
    q = pp.build_queries(
        "Ditwo 미니 무선 우유 거품기",
        {
            "chinese": "电动打奶器 电动打蛋器 起泡器 Ditwo",
            "english": "electric milk frother whisk egg Ditwo",
        },
    )

    assert q[0] == "电动打奶器 电动打蛋器 起泡器 Ditwo"
    assert "电动打奶器" in q
    assert "电动打蛋器" in q
    assert "起泡器" in q


@pytest.mark.parametrize(
    ("chinese", "alias"),
    [
        ("旋转 喷泉 注射器式 水枪", "抽拉式 喷泉 水枪"),
        ("旋转 喷泉 水枪", "旋转喷泉水枪 玩具"),
        ("水枪 海豚", "海豚水枪玩具"),
        ("水枪 鲨鱼 鱼形", "鲨鱼水枪玩具"),
        ("LED飞行回旋球 自动飞行回旋球", "感应悬浮回旋球 玩具"),
        ("旋转 喷泉 水枪 恐龙", "恐龙抽拉式水枪"),
    ],
)
def test_build_queries_adds_live_verified_summer_toy_seller_alias(chinese, alias):
    q = pp.build_queries("여름 장난감", {"chinese": chinese, "english": "summer toy"})

    assert q[0] == chinese
    assert alias in q
    assert q.index(alias) < q.index("水枪") if "水枪" in q else True


def test_browser_media_probe_supports_suffixless_douyin_resource_urls():
    assert "mime_type=video_" in searcher._PLATFORM_MP4_JS
    assert "/video/tos/" in searcher._PLATFORM_MP4_JS


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/manifest.json",
        "https://example.com/site.webmanifest",
        "https://example.com/player.html",
        "https://example.com/master.m3u8",
        "https://example.com/api.json?mime_type=application_json",
    ],
)
def test_platform_media_filter_rejects_manifests_and_documents(url):
    assert searcher._is_probable_platform_media_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://v3-dy-o.zjcdn.com/video/tos/cn/tos-cn-ve-15/abc?mime_type=video_mp4",
        "https://example.kwaicdn.com/play?id=abc&mime_type=video_mp4",
        "https://example.xhscdn.com/demo.mp4?sign=abc",
    ],
)
def test_platform_media_filter_keeps_real_and_suffixless_video_urls(url):
    assert searcher._is_probable_platform_media_url(url) is True


def test_platform_video_threshold_targets_related_category_not_identical_listing():
    assert pp._platform_relevance_threshold(0.9) == 0.75
    assert pp._platform_relevance_threshold(0.5) == 0.70
    assert pp._platform_relevance_threshold(1.0) == 0.75
    assert pp._platform_relevance_threshold(0.9, required_score=0.950001) == pytest.approx(
        0.950001
    )
    assert pp._platform_relevance_threshold(0.9, required_score=1.0) == 1.0


@pytest.mark.parametrize("required", ["bad", float("nan"), float("inf"), 0.69, 1.01])
def test_explicit_platform_video_threshold_fails_closed(required):
    with pytest.raises(ValueError, match="required relevance score"):
        pp._platform_relevance_threshold(0.9, required_score=required)


def test_partner_short_link_resolves_only_to_official_product_url(monkeypatch):
    class Response:
        status_code = 302
        headers = {
            "Location": "https://www.coupang.com/vp/products/9411394523?itemId=1"
        }

        def close(self):
            pass

    import requests

    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: Response())

    resolved = pp._resolve_partner_product_url(
        "https://link.coupang.com/a/newAffiliateCode"
    )

    assert resolved.startswith("https://www.coupang.com/vp/products/9411394523")


def test_partner_short_link_scrapes_resolved_product_url_not_short_link(
    monkeypatch, tmp_path
):
    from core.sourcing import coupang_scraper, pipeline as sourcing_pipeline
    from core.sourcing import report_cache

    short_link = "https://link.coupang.com/a/f8i6WhHkK4"
    product_url = (
        "https://www.coupang.com/vp/products/8065952183"
        "?itemId=22684060132&lptag=AF6328806"
    )
    scraped = []

    monkeypatch.setattr(report_cache, "find_cached_product_info", lambda _url: None)
    monkeypatch.setattr(
        sourcing_pipeline, "find_cached_publish_safe_video", lambda **_kwargs: None
    )
    monkeypatch.setattr(pp, "_resolve_partner_product_url", lambda _url: product_url)

    async def fake_scrape(_browser, url):
        scraped.append(url)
        return None

    monkeypatch.setattr(coupang_scraper, "scrape_product", fake_scrape)

    report = asyncio.run(
        pp.run_platform_sourcing(
            short_link,
            output_dir=str(tmp_path),
            browser=object(),
        )
    )

    assert scraped == [product_url]
    assert report["failure"]["code"] == "coupang_product_unavailable"
    assert "잘못된" not in report["error"]


@pytest.mark.parametrize(
    "location",
    [
        "https://evil.example/vp/products/9411394523",
        "http://www.coupang.com/vp/products/9411394523",
        "https://www.coupang.com/np/search?q=test",
    ],
)
def test_partner_short_link_rejects_untrusted_or_non_product_redirect(
    monkeypatch, location
):
    class Response:
        headers = {"Location": location}

        def close(self):
            pass

    import requests

    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: Response())

    assert (
        pp._resolve_partner_product_url(
            "https://link.coupang.com/a/newAffiliateCode"
        )
        == ""
    )


def test_chinese_platform_queries_drop_korean_and_prefer_chinese():
    assert searcher._queries_for_chinese_platform(
        ["无线手持吸尘器 2代 ROMIN", "무선 미니 청소기", "wireless vacuum"]
    ) == ["无线手持吸尘器 2代 ROMIN"]


def test_chinese_platform_query_strips_mixed_korean_brand_annotation():
    assert searcher._queries_for_chinese_platform(
        ["Rebine 리바인 无线 电动 多功能 浴室清洁刷"]
    ) == ["Rebine 无线 电动 多功能 浴室清洁刷"]


def test_gemini_keyword_conversion_removes_hangul_from_search_phrases(monkeypatch):
    from core.sourcing import keyword_converter

    async def fake_generate(_client, _prompt):
        return (
            "chinese: Rebine 리바인 无线 电动 浴室清洁刷 9合1\n"
            "english: Rebine 리바인 cordless electric bathroom cleaning brush 9-in-1"
        )

    monkeypatch.setattr(keyword_converter, "generate_content_text", fake_generate)
    result = asyncio.run(
        keyword_converter.convert_keywords_gemini(
            "리바인 무선 전동 욕실 청소기 9in1", object()
        )
    )

    assert not any("가" <= char <= "힣" for char in result["chinese"])
    assert not any("가" <= char <= "힣" for char in result["english"])
    assert "Rebine" in result["chinese"]
    assert "9合1" in result["chinese"]


# ── 키워드 변환: Gemini 실패 시 rule-based 폴백 ──

def test_convert_keywords_falls_back_to_rules_without_client():
    kw = asyncio.new_event_loop().run_until_complete(
        pp._convert_keywords("수세미 거치대", None)
    )
    assert kw.get("chinese")  # rule-based compound 매칭
    assert kw.get("english")


# ── reeditor: ffmpeg 명령 생성 ──

def test_reedit_cmd_default_has_audio_and_no_speed(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    cmd = reeditor.build_reedit_cmd(str(src), str(tmp_path / "out.mp4"))
    joined = " ".join(cmd)
    assert "setpts" not in joined and "atempo" not in joined
    assert "-an" not in cmd and "-c:a" in cmd


def test_reedit_cmd_speed_applies_setpts_and_atempo(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    cmd = reeditor.build_reedit_cmd(str(src), str(tmp_path / "out.mp4"), speed=1.03)
    joined = " ".join(cmd)
    assert "setpts=PTS/1.0300" in joined
    assert "atempo=1.0300" in joined


def test_reedit_cmd_short_source_loop_is_bounded(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    cmd = reeditor.build_reedit_cmd(
        str(src), str(tmp_path / "out.mp4"), target_duration=10.0
    )
    assert cmd[2:4] == ["-stream_loop", "-1"]
    assert cmd[cmd.index("-t") + 1] == "10.000"


def test_reedit_cmd_mirror_and_mute(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    cmd = reeditor.build_reedit_cmd(
        str(src), str(tmp_path / "out.mp4"), mirror=True, mute=True
    )
    joined = " ".join(cmd)
    assert "hflip" in joined
    assert "-an" in cmd and "atempo" not in joined


def test_reedit_cmd_bgm_replaces_audio(tmp_path):
    src = tmp_path / "in.mp4"
    bgm = tmp_path / "bgm.mp3"
    src.write_bytes(b"x")
    bgm.write_bytes(b"x")
    cmd = reeditor.build_reedit_cmd(
        str(src), str(tmp_path / "out.mp4"), bgm_path=str(bgm)
    )
    assert "-stream_loop" in cmd and "-shortest" in cmd
    assert "-map" in cmd  # 원본 오디오 대신 BGM 매핑


def test_reedit_hook_is_truncated_to_vertical_video_safe_width(tmp_path):
    src = tmp_path / "in.mp4"
    font = tmp_path / "font.ttf"
    src.write_bytes(b"x")
    font.write_bytes(b"font")
    hook = "[대용량] 알앤엘 1+1 회오리 분수 주사기 물총 2개 1세트 핑크 퍼플"

    truncated = reeditor._truncate_hook_text(hook)
    cmd = reeditor.build_reedit_cmd(
        str(src),
        str(tmp_path / "out.mp4"),
        hook_text=hook,
        font_path=str(font),
    )
    joined = " ".join(cmd)

    assert truncated.endswith("…")
    assert len(truncated) < len(hook)
    assert "fontsize=48" in joined
    assert "fix_bounds=1" in joined
    assert "boxcolor=black@0.45" in joined


# ── uploaded_registry: 소스 재사용 차단 ──

def test_registry_source_roundtrip(tmp_path):
    reg = reg_mod.UploadedRegistry(path=str(tmp_path / "reg.json"))
    url = "https://www.douyin.com/video/7351234567890123456?from=search"
    assert not reg.is_source_used(url)
    reg.record_source(url, meta={"platform": "douyin"})
    # 쿼리스트링이 달라도 같은 소스로 판정
    assert reg.is_source_used("https://www.douyin.com/video/7351234567890123456?x=1")
    assert reg_mod.normalize_source_id(url) in reg.used_source_ids()
    # 재로드에도 유지(영구 저장)
    reg2 = reg_mod.UploadedRegistry(path=str(tmp_path / "reg.json"))
    assert reg2.is_source_used(url)


def test_normalize_source_id_strips_query_and_host_case():
    a = reg_mod.normalize_source_id("https://www.KUAISHOU.com/short-video/AbC12345?x=1#t")
    b = reg_mod.normalize_source_id("https://www.kuaishou.com/short-video/AbC12345")
    assert a == b
    assert a != reg_mod.normalize_source_id(
        "https://www.kuaishou.com/short-video/abc12345"
    )


# ── searcher: 페이지 링크 패턴 + 후보 검증 ──

_SAMPLE_HTML = """
<a href="https://www.douyin.com/video/7351234567890123456">v1</a>
<a href="/video/7359999999999999999?from=search">v2</a>
<a href="https://www.kuaishou.com/short-video/3xf8a9b2c1d5e7">k1</a>
<a href="https://www.xiaohongshu.com/explore/66a1b2c3d4e5f6a7b8c9d0e1">x1</a>
<a href="https://www.bilibili.com/video/BV1xx411c7mD">b1</a>
<a href="//www.bilibili.com/video/BV1yy411c7mE?from=search">b2</a>
"""


def test_page_link_pattern_douyin_dedup():
    pat = searcher._PAGE_LINK_PATTERNS["douyin"]
    ids = {m.group(2) for m in pat.finditer(_SAMPLE_HTML)}
    assert ids == {"7351234567890123456", "7359999999999999999"}


def test_page_link_pattern_kuaishou_and_xhs():
    assert searcher._PAGE_LINK_PATTERNS["kuaishou"].search(_SAMPLE_HTML).group(2) == "3xf8a9b2c1d5e7"
    assert searcher._PAGE_LINK_PATTERNS["xiaohongshu"].search(_SAMPLE_HTML)


def test_legacy_bilibili_extractor_is_not_in_automation_order():
    ids = {m.group(2) for m in searcher._PAGE_LINK_PATTERNS["bilibili"].finditer(_SAMPLE_HTML)}
    assert ids == {"BV1xx411c7mD", "BV1yy411c7mE"}
    assert "bilibili" in searcher._YTDLP_PLATFORMS
    assert "xiaohongshu" in searcher._YTDLP_PLATFORMS
    assert searcher.DEFAULT_PLATFORM_ORDER == ["douyin", "xiaohongshu", "kuaishou"]
    assert "bilibili" not in searcher.SUPPORTED_COMMERCE_PLATFORMS


def test_settings_platform_sources_preserve_custom_explicit_order():
    from managers.settings_manager import SettingsManager
    sm = SettingsManager.__new__(SettingsManager)
    sm._settings = {"platform_video_sources": ["kuaishou", "douyin"]}
    import threading
    sm._lock = threading.RLock()
    assert sm.get_platform_video_sources() == ["kuaishou", "douyin"]


def test_settings_platform_sources_migrates_legacy_two_platform_default():
    from managers.settings_manager import SettingsManager
    sm = SettingsManager.__new__(SettingsManager)
    sm._settings = {"platform_video_sources": ["douyin", "kuaishou"]}
    import threading
    sm._lock = threading.RLock()
    assert sm.get_platform_video_sources() == [
        "douyin", "xiaohongshu", "kuaishou"
    ]


def test_settings_platform_sources_default_includes_all_supported_platforms():
    from managers.settings_manager import SettingsManager
    sm = SettingsManager.__new__(SettingsManager)
    sm._settings = {}
    import threading
    sm._lock = threading.RLock()
    assert sm.get_platform_video_sources() == [
        "douyin", "xiaohongshu", "kuaishou"
    ]


def test_settings_platform_sources_drop_bilibili_and_keep_xiaohongshu():
    from managers.settings_manager import SettingsManager
    sm = SettingsManager.__new__(SettingsManager)
    sm._settings = {"platform_video_sources": ["xiaohongshu", "bilibili"]}
    import threading
    sm._lock = threading.RLock()
    assert sm.get_platform_video_sources() == ["xiaohongshu"]


def test_settings_migrates_legacy_coupang_mode_to_three_platforms():
    from managers.settings_manager import SettingsManager
    sm = SettingsManager.__new__(SettingsManager)
    sm._settings = {"automation_sourcing_method": "coupang"}
    assert sm.get_automation_sourcing_method() == "platform_video"


def test_search_platform_shorts_selects_best_safe_hit_and_cleans_discarded(
    monkeypatch, tmp_path
):
    low = tmp_path / "low.mp4"
    high = tmp_path / "high.mp4"
    low.write_bytes(b"low")
    high.write_bytes(b"high")

    async def fake_search(_browser, platform, *_args, **_kwargs):
        if platform == "douyin":
            return {
                "platform": platform,
                "video_file": str(low),
                "video_url": "https://www.douyin.com/video/7351234567890123456",
                "relevance_score": 0.91,
            }
        if platform == "xiaohongshu":
            return {
                "platform": platform,
                "video_file": str(high),
                "video_url": "https://www.xiaohongshu.com/explore/66a1b2c3d4e5f6a7b8c9d0e1",
                "relevance_score": 0.98,
            }
        return None

    monkeypatch.setattr(searcher, "search_one_platform", fake_search)
    hit = asyncio.run(
        searcher.search_platform_shorts(
            object(), ["portable fan"], str(tmp_path),
            platforms=["douyin", "xiaohongshu"],
            relevance_references=["portable fan"],
        )
    )

    assert hit["platform"] == "xiaohongshu"
    assert high.exists()
    assert not low.exists()


def test_search_platform_shorts_filters_non_commerce_platforms(monkeypatch, tmp_path):
    called = []

    async def fake_search(_browser, platform, *_args, **_kwargs):
        called.append(platform)
        return None

    monkeypatch.setattr(searcher, "search_one_platform", fake_search)
    hit = asyncio.run(
        searcher.search_platform_shorts(
            object(), ["迷你风扇"], str(tmp_path),
            platforms=["bilibili", "xiaohongshu", "douyin", "kuaishou"],
            relevance_references=["迷你风扇"],
        )
    )

    assert hit is None
    assert called == ["xiaohongshu", "douyin", "kuaishou"]


def test_search_platform_shorts_stops_on_typed_browser_session_failure(tmp_path):
    diagnostics = {}

    class ClosedBrowser:
        def __init__(self):
            self.calls = 0

        async def get(self, *_args, **_kwargs):
            self.calls += 1
            raise ConnectionError("closed transport")

    browser = ClosedBrowser()
    hit = asyncio.run(
        searcher.search_platform_shorts(
            browser,
            ["电动奶泡器"],
            str(tmp_path),
            platforms=["douyin", "xiaohongshu"],
            diagnostics=diagnostics,
        )
    )

    assert hit is None
    assert browser.calls == 1
    assert diagnostics["counts"]["browser_session_failed"] == 1
    assert pp.describe_platform_search_failure(diagnostics)["code"] == (
        "browser_session_failed"
    )


def test_page_link_evaluation_propagates_typed_browser_session_failure():
    diagnostics = {}

    class ClosedTab:
        async def evaluate(self, *_args, **_kwargs):
            raise ConnectionError("closed transport")

    with pytest.raises(ConnectionError):
        asyncio.run(
            searcher._extract_video_page_links(
                ClosedTab(),
                "douyin",
                diagnostics=diagnostics,
            )
        )

    assert diagnostics["counts"]["browser_session_failed"] == 1
    assert pp.describe_platform_search_failure(diagnostics)["code"] == (
        "browser_session_failed"
    )


def test_search_one_platform_shares_attempted_ids_across_query_variants(
    monkeypatch, tmp_path
):
    seen_sets = []

    class Tab:
        async def close(self):
            return None

    class Browser:
        async def get(self, *_args, **_kwargs):
            return Tab()

    async def fake_query(*args, **_kwargs):
        attempted = args[-1]
        seen_sets.append(attempted)
        if len(seen_sets) == 1:
            attempted.add("douyin:7351234567890123456")
        return None

    monkeypatch.setitem(searcher._WARMUP_URL, "douyin", "")
    monkeypatch.setattr(searcher, "_search_query_on_tab", fake_query)

    hit = asyncio.run(searcher.search_one_platform(
        Browser(),
        "douyin",
        ["迷你风扇", "手持风扇"],
        str(tmp_path),
    ))

    assert hit is None
    assert len(seen_sets) == 2
    assert seen_sets[0] is seen_sets[1]
    assert "douyin:7351234567890123456" in seen_sets[1]


@pytest.mark.parametrize(
    "page_text",
    [
        "请登录后继续查看视频",
        "登录 / 注册",
        "Sign in to continue",
        "Unfortunately, bots use DuckDuckGo too.",
    ],
)
def test_access_challenge_detection_covers_platform_login_and_search_bot_pages(page_text):
    class Tab:
        async def evaluate(self, *_args, **_kwargs):
            return page_text

    from core.sourcing.product_searcher import _page_has_access_challenge

    assert asyncio.run(_page_has_access_challenge(Tab())) is True


def test_external_search_skips_blocked_and_empty_providers(monkeypatch, tmp_path):
    http_opened = []
    monkeypatch.setattr(
        searcher, "_EXTERNAL_SEARCH_PROVIDERS", ("duckduckgo", "bing", "brave")
    )

    class Browser:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("검색엔진 CAPTCHA 탭을 열면 안 됩니다")

    def fake_http_search(provider, platform, _url):
        http_opened.append((provider, platform))
        if provider == "brave":
            return ["https://www.douyin.com/video/7351234567890123456"]
        return []

    diagnostics = {}
    monkeypatch.setattr(
        searcher, "_http_external_search_links", fake_http_search, raising=False
    )

    links = asyncio.run(searcher._external_search_links(
        Browser(), "douyin", "电动奶泡器", str(tmp_path), diagnostics=diagnostics
    ))

    assert links == ["https://www.douyin.com/video/7351234567890123456"]
    assert http_opened == [
        ("duckduckgo", "douyin"),
        ("bing", "douyin"),
        ("brave", "douyin"),
    ]
    assert diagnostics["platforms"]["search:duckduckgo"]["no_results"] == 1
    assert diagnostics["platforms"]["search:bing"]["no_results"] == 1

    second_links = asyncio.run(searcher._external_search_links(
        Browser(), "douyin", "手持奶泡器", str(tmp_path), diagnostics=diagnostics
    ))
    assert second_links == links
    assert http_opened[-3:] == [
        ("duckduckgo", "douyin"),
        ("bing", "douyin"),
        ("brave", "douyin"),
    ]


def test_search_index_uses_http_without_opening_browser_tabs(
    monkeypatch, tmp_path
):
    class Browser:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("검색엔진 페이지를 브라우저로 열면 안 됩니다")

    calls = []

    def fake_http(provider, platform, url):
        calls.append((provider, platform, url))
        return ["https://www.douyin.com/video/7658326682089144783"]

    monkeypatch.setattr(searcher, "_EXTERNAL_SEARCH_PROVIDERS", ("bing",))
    monkeypatch.setattr(searcher, "_http_external_search_links", fake_http)

    links = asyncio.run(
        searcher._external_search_links(
            Browser(), "douyin", "旋转 喷泉 水枪", str(tmp_path), diagnostics={}
        )
    )

    assert links == ["https://www.douyin.com/video/7658326682089144783"]
    assert calls[0][0:2] == ("bing", "douyin")
    assert calls[0][2].startswith("https://www.bing.com/search?")
    assert "site%3Adouyin.com/video" in calls[0][2]


def test_paired_chrome_extension_precedes_automated_browser(monkeypatch, tmp_path):
    from core.sourcing import chrome_extension_bridge as bridge_module

    class Bridge:
        def start(self):
            return True

        def is_connected(self):
            return True

        def search_index(self, platform, query, timeout):
            assert (platform, query) == ("douyin", "旋转 喷泉 水枪")
            assert timeout > 0
            return ["https://www.douyin.com/video/7658326682089144783"]

    class Browser:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("paired Chrome should satisfy the search first")

    monkeypatch.setattr(
        bridge_module, "get_chrome_extension_bridge", lambda: Bridge()
    )
    monkeypatch.setenv("SSMAKER_ALLOW_CHROME_INDEX_SEARCH", "1")

    links = asyncio.run(
        searcher._external_search_links(
            Browser(), "douyin", "旋转 喷泉 水枪", str(tmp_path), diagnostics={}
        )
    )
    assert links == ["https://www.douyin.com/video/7658326682089144783"]


def test_paired_chrome_extension_is_disabled_by_default(monkeypatch, tmp_path):
    from core.sourcing import chrome_extension_bridge as bridge_module

    class Bridge:
        def start(self):
            raise AssertionError("기본 자동화가 사용자 Chrome 검색 탭을 열면 안 됩니다")

    monkeypatch.delenv("SSMAKER_ALLOW_CHROME_INDEX_SEARCH", raising=False)
    monkeypatch.setattr(
        bridge_module, "get_chrome_extension_bridge", lambda: Bridge()
    )
    monkeypatch.setattr(searcher, "_EXTERNAL_SEARCH_PROVIDERS", ())

    links = asyncio.run(
        searcher._external_search_links(
            object(), "douyin", "전동 우유거품기", str(tmp_path), diagnostics={}
        )
    )

    assert links == []


def test_http_external_search_extracts_direct_platform_links(monkeypatch):
    calls = []

    class Response:
        text = """
        <a href="https://www.douyin.com/video/7351234567890123456">first</a>
        <a href="https://www.douyin.com/video/7351234567890123456">duplicate</a>
        """

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(get=fake_get))

    links = searcher._http_external_search_links(
        "bing", "douyin", "https://www.bing.com/search?q=test"
    )

    assert links == ["https://www.douyin.com/video/7351234567890123456"]
    assert calls[0][1]["timeout"] > 0
    assert "User-Agent" in calls[0][1]["headers"]


def test_external_search_records_http_rate_limit(monkeypatch, tmp_path):
    class RateLimited(Exception):
        response = SimpleNamespace(status_code=429)

    def fake_http_search(*_args, **_kwargs):
        raise RateLimited("too many requests")

    diagnostics = {}
    monkeypatch.setattr(searcher, "_EXTERNAL_SEARCH_PROVIDERS", ("brave",))
    monkeypatch.setattr(searcher, "_http_external_search_links", fake_http_search)

    links = asyncio.run(searcher._external_search_links(
        object(), "douyin", "电动奶泡器", str(tmp_path), diagnostics=diagnostics
    ))

    assert links == []
    assert diagnostics["counts"]["rate_limited"] == 1
    assert diagnostics["events"][-1]["detail"] == "HTTP 429"


def test_platform_failure_report_preserves_block_reason_and_skipped_delivery(
    monkeypatch, tmp_path
):
    from core.sourcing import coupang_scraper

    async def fake_scrape(_browser, _url):
        return {"name": "전동 우유거품기"}

    async def fake_keywords(_product_name, _client):
        return {"chinese": "电动奶泡器", "english": "electric milk frother"}

    async def fake_search(*_args, **kwargs):
        diagnostics = kwargs["diagnostics"]
        searcher._diagnostic_event(
            diagnostics,
            "access_challenge",
            platform="search:duckduckgo",
            detail="bot verification",
        )
        searcher._diagnostic_event(
            diagnostics,
            "download_failed",
            platform="douyin",
            detail="login required",
        )
        return None

    class Registry:
        def used_source_ids(self):
            return set()

    monkeypatch.setattr(coupang_scraper, "scrape_product", fake_scrape)
    monkeypatch.setattr(pp, "_convert_keywords", fake_keywords)
    monkeypatch.setattr(pp, "_resolve_purchase_link", lambda url: {
        "purchase_url": url, "deep_link": url, "source": "manual",
    })
    monkeypatch.setattr(searcher, "search_platform_shorts", fake_search)
    monkeypatch.setattr(reg_mod, "get_uploaded_registry", lambda: Registry())

    report = asyncio.run(pp.run_platform_sourcing(
        "https://link.coupang.com/a/f8i3PuVSqi",
        output_dir=str(tmp_path),
        browser=object(),
    ))

    assert report["ok"] is False
    assert report["failure"]["code"] == "platform_access_blocked"
    assert report["blocked_stages"] == ["video_edit", "youtube_upload", "linktree_publish"]
    assert report["error"] == (
        "상품 영상을 찾지 못했어요.\n"
        "잠시 후 다시 시도하거나 다른 상품 링크를 사용해 주세요."
    )
    for internal_detail in (
        "DuckDuckGo", "Douyin", "YouTube", "Linktree", "검색 내역", "후속 단계"
    ):
        assert internal_detail not in report["error"]
    report_path = report["report_path"]
    assert os.path.exists(report_path)
    persisted = json.loads(open(report_path, encoding="utf-8").read())
    assert persisted["failure"]["diagnostics"]["events"][0]["code"] == "access_challenge"


def test_xiaohongshu_collector_uses_ytdlp(monkeypatch, tmp_path):
    class FakeYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, _url, download=True):
            if download:
                (tmp_path / "xhs-video.mp4").write_bytes(b"video")
            return {
                "id": "xhs-video",
                "ext": "mp4",
                "title": "portable fan product demo",
                "duration": 12,
                "width": 1080,
                "height": 1920,
            }

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYoutubeDL))
    collector = collector_mod.PlatformVideoCollector(str(tmp_path))
    result = collector.collect_one(
        "https://www.xiaohongshu.com/explore/66a1b2c3d4e5f6a7b8c9d0e1"
    )

    assert "xiaohongshu" in collector_mod.SUPPORTED_BY_YTDLP
    assert result.ok is True
    assert result.title == "portable fan product demo"
    assert result.local_path.endswith("xhs-video.mp4")


def test_ytdlp_rejects_unrelated_metadata_before_download(monkeypatch, tmp_path):
    calls = []

    class FakeCollector:
        def __init__(self, output_dir):
            assert output_dir == str(tmp_path)

        def collect_one(self, _url, download=True, cookies=None):
            calls.append(download)
            return SimpleNamespace(
                ok=True,
                error="",
                duration=12,
                title="cat dancing compilation",
                local_path="",
                width=1080,
                height=1920,
            )

    monkeypatch.setattr(collector_mod, "PlatformVideoCollector", FakeCollector)
    result = searcher._ytdlp_download(
        "https://www.xiaohongshu.com/explore/66a1b2c3d4e5f6a7b8c9d0e1",
        str(tmp_path),
        relevance_references=["迷你手持风扇"],
        category_terms=["风扇"],
    )

    assert result["relevance_rejected"] is True
    assert calls == [False]


def test_ytdlp_long_metadata_is_terminal_for_same_page(monkeypatch, tmp_path):
    calls = []

    class FakeCollector:
        def __init__(self, output_dir):
            assert output_dir == str(tmp_path)

        def collect_one(self, _url, download=True, cookies=None):
            calls.append(download)
            return SimpleNamespace(
                ok=True,
                error="",
                duration=449,
                title="挂脖风扇评测",
                local_path="",
                width=1080,
                height=1920,
            )

    monkeypatch.setattr(collector_mod, "PlatformVideoCollector", FakeCollector)
    result = searcher._ytdlp_download(
        "https://www.douyin.com/video/7538697061118545171",
        str(tmp_path),
        relevance_references=["挂脖风扇"],
        category_terms=["挂脖风扇"],
    )

    assert result["technical_rejected"] is True
    assert calls == [False]


def test_validate_source_video_rejects_bad_duration(monkeypatch, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 300_000)
    monkeypatch.setattr(searcher, "probe_media_file",
                        lambda p: {"duration": 400.0, "width": 1080, "height": 1920})
    ok, why = searcher.validate_source_video(str(f))
    assert not ok and "duration" in why


def test_validate_source_video_rejects_low_res(monkeypatch, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 300_000)
    monkeypatch.setattr(searcher, "probe_media_file",
                        lambda p: {"duration": 20.0, "width": 320, "height": 568})
    ok, why = searcher.validate_source_video(str(f))
    assert not ok and "resolution" in why


def test_validate_source_video_accepts_good(monkeypatch, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 300_000)
    monkeypatch.setattr(searcher, "probe_media_file",
                        lambda p: {"duration": 21.0, "width": 720, "height": 1280})
    ok, why = searcher.validate_source_video(str(f))
    assert ok, why


def test_validate_source_video_probe_unavailable_uses_size(monkeypatch, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 300_000)
    monkeypatch.setattr(searcher, "probe_media_file", lambda p: {})
    ok, why = searcher.validate_source_video(str(f))
    assert ok and why == "probe_unavailable"


def test_candidate_relevance_requires_candidate_owned_evidence():
    assert searcher.candidate_relevance_score("", ["미니 선풍기", "mini fan"]) is None
    assert searcher.candidate_relevance_score("검색어와 무관한 고양이 영상", ["미니 선풍기"]) < 0.9
    assert searcher.candidate_relevance_score(
        "fan cat dancing compilation", ["fan"]
    ) == 0.0


def test_candidate_relevance_rejects_accessory_only_video():
    score = searcher.candidate_relevance_score(
        "mini fan replacement battery charger", ["mini fan"]
    )
    assert score is not None and score < 0.9
    relevant, threshold_score = searcher._relevance_result(
        "mini fan replacement battery charger", ["mini fan"], 0.9, ["mini fan"]
    )
    assert relevant is False
    assert threshold_score < 0.9


def test_platform_auto_publish_threshold_never_drops_below_ninety_percent():
    relevant, score = searcher._relevance_result(
        "미니 선풍기 사용 후기",
        ["미니 선풍기"],
        0.1,
        ["선풍기"],
    )
    assert relevant is True and score >= 0.9
    relevant, _ = searcher._relevance_result(
        "미니 선풍기 사용 후기",
        ["미니 선풍기"],
        0.1,
        ["고양이"],
    )
    assert relevant is False


def test_candidate_relevance_accepts_exact_multilingual_product_title():
    assert searcher.candidate_relevance_score("미니 선풍기 사용 후기", ["미니 선풍기"]) >= 0.9
    assert searcher.candidate_relevance_score("迷你风扇 产品演示", ["迷你风扇"]) >= 0.9


def test_related_product_video_can_use_platform_family_threshold():
    title = "迷你口袋风扇 USB 高速100档手持小风扇 便携式"
    references = [
        "알리사 100단 아이스 터보 MAX 휴대용 선풍기",
        "便携式手持风扇 MAX USB 100档",
        "portable handheld fan MAX USB 100-speed",
    ]
    relevant, score = searcher._relevance_result(
        title,
        references,
        0.75,
        ["风扇", "fan", "선풍기"],
    )

    assert score is not None and score >= 0.75
    assert relevant is True


def test_chinese_product_family_anchor_handles_unspaced_caption():
    title = "这个多功能打蛋器，不管打蛋液还是搅面糊都好用 #自动打蛋器"
    references = [
        "Ditwo 미니 무선 전동 휘핑기 우유 거품기",
        "电动奶泡器 电动打蛋器 打蛋器 Ditwo",
        "electric milk frother whisk egg Ditwo",
    ]
    relevant, score = searcher._relevance_result(
        title,
        references,
        0.75,
        ["whisk", "beater", "거품기", "打蛋"],
    )

    assert score == 0.75
    assert relevant is True


def test_candidate_relevance_accepts_real_chinese_electric_brush_caption():
    references = [
        "리바인 무선 만능 전동 다용도 화장실 욕실 청소기 9in1 분리형 방수",
        "Rebine 无线 电动 多功能 卫生间 浴室 清洁刷 9合1 可拆卸 防水",
        "Rebine cordless electric multi-functional bathroom cleaning brush 9-in-1",
    ]
    caption = (
        "这款多功能手持无线电动清洁刷，厨房浴室砖，水池都可以清洁，"
        "一机多用省时省力又省心，可换刷头，超长续航，太方便了"
    )

    assert searcher.candidate_relevance_score(caption, references) >= 0.9


# ── cleanup: 보존 기간 지난 산출물 정리 ──

def test_cleanup_old_outputs(tmp_path):
    old = tmp_path / "old.mp4"
    new = tmp_path / "new.mp4"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    past = 1_000_000_000  # 2001년
    os.utime(old, (past, past))
    removed = pp.cleanup_old_outputs(str(tmp_path), retention_days=7)
    assert removed == 1
    assert new.exists() and not old.exists()


# ── 큐 스크립트: 3플랫폼 분기 헬퍼 ──

def test_queue_platform_helpers(tmp_path, monkeypatch):
    from scripts import run_summer_coupang_queue_once as queue_runner

    assert queue_runner.is_platform_system_blocker(
        {"failure": {"code": "browser_start_failed"}}
    )
    assert queue_runner.is_platform_system_blocker(
        {"failure": {"code": "browser_session_failed"}}
    )
    assert not queue_runner.is_platform_system_blocker(
        {
            "failure": {"code": "no_search_results"},
            "error": "browser라는 단어가 있어도 구조화 코드가 우선입니다.",
        }
    )
    assert not queue_runner.is_platform_system_blocker(
        "zendriver launch failed"
    )

    # final_video 없음 → render_ok False + 품질 게이트 사유 포함
    report = {"final_video": "", "render_integrity": {"ok": False}}
    rendered = queue_runner.platform_rendered_result(report, tmp_path, "테스트 상품")
    assert rendered["render_ok"] is False
    assert rendered["upload_quality"]["ok"] is False
    assert (tmp_path / "rendered" / "render_result.json").exists()


def test_queue_get_sourcing_method_defaults_to_platform_video(monkeypatch):
    from scripts import run_summer_coupang_queue_once as queue_runner

    class _Boom:
        def get_automation_sourcing_method(self):
            raise RuntimeError("no settings")

    import managers.settings_manager as sm
    monkeypatch.setattr(sm, "get_settings_manager", lambda: _Boom())
    assert queue_runner.get_sourcing_method() == "platform_video"


def test_platform_source_is_deferred_until_successful_upload(
    monkeypatch, tmp_path
):
    from core.sourcing import coupang_scraper
    from managers.work_reservation_store import WorkReservationStore

    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    store = WorkReservationStore(tmp_path / "reservations.json")
    key = store.get_or_create("platform:recovery", "42")

    async def fake_scrape(_browser, _url):
        return {"name": "recovery product"}

    async def fake_keywords(_product_name, _client):
        return {"chinese": "recovery", "english": "recovery"}

    async def fake_search(*_args, **_kwargs):
        return {
            "platform": "douyin",
            "video_file": str(source),
            "video_url": "https://www.douyin.com/video/7351234567890123456",
            "size_mb": 1,
            "via": "test",
        }

    def fake_reedit(_source_path, output_path, **_kwargs):
        assert _kwargs["min_duration"] == 10.0
        with open(output_path, "wb") as handle:
            handle.write(b"finished-video")
        return True

    class DeferredRegistry:
        record_source_called = False

        def used_source_ids(self):
            return set()

        def record_source(self, *_args, **_kwargs):
            self.record_source_called = True
            raise OSError("registry unavailable")

    def finalize(_path):
        assert store.set_state(
            "platform:recovery", key, "completed_pending_delivery", "42"
        )

    monkeypatch.setattr(coupang_scraper, "scrape_product", fake_scrape)
    monkeypatch.setattr(pp, "_convert_keywords", fake_keywords)
    monkeypatch.setattr(pp, "_resolve_purchase_link", lambda url: {
        "purchase_url": url,
        "deep_link": "",
        "source": "original",
    })
    monkeypatch.setattr(searcher, "search_platform_shorts", fake_search)
    monkeypatch.setattr(reeditor, "reedit", fake_reedit)
    registry = DeferredRegistry()
    monkeypatch.setattr(reg_mod, "get_uploaded_registry", lambda: registry)

    report = asyncio.run(
        pp.run_platform_sourcing(
            "https://www.coupang.com/vp/products/1",
            output_dir=str(tmp_path),
            browser=object(),
            before_commit=finalize,
        )
    )

    assert report["ok"] is True
    assert "manual_recovery_required" not in report
    assert report["quality_profile"] == "platform_reedit"
    assert report["selected_source_url"] == (
        "https://www.douyin.com/video/7351234567890123456"
    )
    assert report["selected_source_id"] == "douyin:7351234567890123456"
    assert registry.record_source_called is False
    assert report["final_video"]
    assert os.path.exists(report["final_video"])
    assert store.state("platform:recovery", "42") == "completed_pending_delivery"


def test_safe_cached_video_bypasses_coupang_and_platform_browsers(
    monkeypatch, tmp_path
):
    from core.sourcing import coupang_scraper, pipeline as sourcing_pipeline
    from core.sourcing import report_cache

    cached_source = tmp_path / "cached-source.mp4"
    cached_source.write_bytes(b"cached source")

    monkeypatch.setattr(
        report_cache,
        "find_cached_product_info",
        lambda _url: None,
    )
    monkeypatch.setattr(
        sourcing_pipeline,
        "find_cached_publish_safe_video",
        lambda **_kwargs: {
            "source": "aliexpress",
            "platform": "aliexpress",
            "product": {"title": "무선 전동 청소솔", "score": 0.98},
            "video_url": "https://example.com/source/123",
            "video_file": str(cached_source),
            "size_mb": 1.2,
            "fallback_reason": "cached_marketplace_video",
            "auto_publish_safe": True,
            "requires_review": False,
            "cached_from_report": str(tmp_path / "old-report.json"),
        },
    )

    async def fail_scrape(*_args, **_kwargs):
        pytest.fail("cached product metadata must bypass the Coupang page")

    async def fail_browser():
        pytest.fail("a publish-safe cached video must bypass Chrome")

    async def fail_search(*_args, **_kwargs):
        pytest.fail("a publish-safe cached video must bypass live search")

    async def fake_keywords(_name, _client):
        return {"chinese": "无线电动清洁刷", "english": "cordless cleaning brush"}

    def fake_reedit(_source_path, output_path, **_kwargs):
        with open(output_path, "wb") as handle:
            handle.write(b"edited cached video")
        return True

    class Registry:
        def used_source_ids(self):
            return set()

    monkeypatch.setattr(coupang_scraper, "scrape_product", fail_scrape)
    monkeypatch.setattr(searcher, "start_browser", fail_browser)
    monkeypatch.setattr(searcher, "search_platform_shorts", fail_search)
    monkeypatch.setattr(pp, "_convert_keywords", fake_keywords)
    monkeypatch.setattr(pp, "_resolve_purchase_link", lambda url: {
        "purchase_url": url, "deep_link": url, "source": "manual",
    })
    monkeypatch.setattr(reeditor, "reedit", fake_reedit)
    monkeypatch.setattr(reg_mod, "get_uploaded_registry", lambda: Registry())

    report = asyncio.run(pp.run_platform_sourcing(
        "https://link.coupang.com/a/test",
        output_dir=str(tmp_path / "output"),
    ))

    assert report["ok"] is True
    assert report["source_kind"] == "cached_marketplace_video"
    assert report["auto_publish_safe"] is True
    assert report["requires_review"] is False
    assert report["product_info"]["source"] == "publish_safe_video_cache"
    assert os.path.exists(report["final_video"])
    assert cached_source.exists(), "shared cached input must not be deleted"


@pytest.mark.parametrize("allow_image_fallback", [False, True])
def test_browser_failure_does_not_promote_or_charge_image_fallback(
    monkeypatch, tmp_path, allow_image_fallback
):
    from core.sourcing import pipeline as sourcing_pipeline
    from core.sourcing import report_cache

    fallback_video = tmp_path / "review-only.mp4"
    fallback_video.write_bytes(b"review-only video")
    committed = []

    monkeypatch.setattr(
        report_cache,
        "find_cached_product_info",
        lambda _url: {
            "name": "전동 우유거품기",
            "image": "https://example.com/frother.jpg",
            "url": "https://link.coupang.com/a/f8i3PuVSqi",
            "source": "cached_report",
        },
    )
    monkeypatch.setattr(
        sourcing_pipeline,
        "find_cached_publish_safe_video",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(pp, "_resolve_partner_product_url", lambda _url: "")

    async def fake_image_fallback(**_kwargs):
        return {
            "source": "coupang_image",
            "platform": "coupang_image",
            "product": {"title": "전동 우유거품기", "score": 1.0},
            "video_url": "https://example.com/frother.jpg",
            "video_file": str(fallback_video),
            "size_mb": 1.0,
            "fallback_reason": "no_marketplace_video",
            "auto_publish_safe": False,
            "requires_review": True,
        }

    async def fail_browser():
        raise RuntimeError("Chrome unavailable")

    async def fake_keywords(_name, _client):
        return {"chinese": "电动奶泡器", "english": "electric milk frother"}

    class Registry:
        def used_source_ids(self):
            return set()

    monkeypatch.setattr(
        sourcing_pipeline,
        "create_product_image_video_fallback",
        fake_image_fallback,
    )
    monkeypatch.setattr(searcher, "start_browser", fail_browser)
    monkeypatch.setattr(pp, "_convert_keywords", fake_keywords)
    monkeypatch.setattr(pp, "_resolve_purchase_link", lambda url: {
        "purchase_url": url, "deep_link": url, "source": "manual",
    })
    monkeypatch.setattr(reg_mod, "get_uploaded_registry", lambda: Registry())

    report = asyncio.run(pp.run_platform_sourcing(
        "https://link.coupang.com/a/f8i3PuVSqi",
        output_dir=str(tmp_path / "output"),
        before_commit=committed.append,
        allow_image_fallback=allow_image_fallback,
    ))

    if allow_image_fallback:
        assert report["ok"] is True
        assert report["source_kind"] == "coupang_image"
        assert report["auto_publish_safe"] is False
        assert report["requires_review"] is True
        assert report["fallback_reason"] == "no_marketplace_video"
        assert report["final_video"] == str(fallback_video)
        assert report["blocked_stages"] == ["youtube_upload", "linktree_publish"]
        assert report["fallback_failure"]["code"] == "browser_start_failed"
    else:
        assert report["ok"] is False
        assert report["source_kind"] == ""
        assert report["final_video"] == ""
        assert report["failure"]["code"] == "browser_start_failed"
    assert committed == []


def test_download_only_stops_before_reedit_and_keeps_source(monkeypatch, tmp_path):
    from core.sourcing import coupang_scraper

    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")

    async def fake_scrape(_browser, _url):
        return {"name": "미니 선풍기"}

    async def fake_keywords(_product_name, _client):
        return {"chinese": "迷你手持风扇", "english": "mini handheld fan"}

    search_options = {}

    async def fake_search(*_args, **kwargs):
        search_options.update(kwargs)
        return {
            "platform": "xiaohongshu",
            "video_file": str(source),
            "video_url": "https://www.xiaohongshu.com/explore/66a1b2c3d4e5f6a7b8c9d0e1",
            "size_mb": 1,
            "via": "test",
            "title": "迷你手持风扇 使用演示",
            "relevance_score": 0.98,
        }

    class Registry:
        def used_source_ids(self):
            return set()

    monkeypatch.setattr(coupang_scraper, "scrape_product", fake_scrape)
    monkeypatch.setattr(pp, "_convert_keywords", fake_keywords)
    monkeypatch.setattr(pp, "_resolve_purchase_link", lambda url: {
        "purchase_url": url, "deep_link": "", "source": "original",
    })
    monkeypatch.setattr(searcher, "search_platform_shorts", fake_search)
    monkeypatch.setattr(
        reeditor,
        "reedit",
        lambda *_args, **_kwargs: pytest.fail("download-only must not reedit"),
    )
    monkeypatch.setattr(reg_mod, "get_uploaded_registry", lambda: Registry())

    report = asyncio.run(pp.run_platform_sourcing(
        "https://www.coupang.com/vp/products/1",
        output_dir=str(tmp_path),
        browser=object(),
        download_only=True,
    ))

    assert report["ok"] is True
    assert search_options["prefer_best"] is False
    assert search_options["min_relevance_score"] == 0.75
    assert report["download_only"] is True
    assert report["downloaded_video"] == str(source)
    assert source.exists()
    assert report["final_video"] == ""
