# -*- coding: utf-8 -*-
import asyncio

import pytest

from core.sourcing import platform_shorts_searcher as platform_searcher
from core.sourcing.keyword_converter import convert_keywords_rule_based
from core.sourcing.product_searcher import (
    _category_terms_for_keyword,
    _download_hls_via_ffmpeg,
    _get_media_response,
    _is_safe_remote_media_url,
    _open_pinned_media_hop,
    _passes_category_guard,
    _preferred_chinese_query_variants,
    find_products_with_video,
)


@pytest.mark.parametrize(
    ("title", "expected_chinese_anchor"),
    [
        ("대용량 휴대용 무선 텀블러 믹서기", "便携式无线榨汁杯"),
        ("자동 디스펜서 거품비누 손세정기", "自动泡沫洗手机"),
        ("접이식 휴대용 핸디형 스팀다리미", "手持挂烫机"),
        ("무선 미니 가습기", "迷你加湿器"),
        ("충전식 전동 와인 오프너", "电动红酒开瓶器"),
        ("무선 마늘 야채 다지기 초퍼", "无线电动蒜泥器"),
        ("충전식 모션 센서등 동작감지 조명", "人体感应灯"),
        ("강아지 고양이 반려동물 스팀 브러쉬", "宠物蒸汽梳"),
        ("2단 접이식 노트북 거치대", "折叠笔记本电脑支架"),
        ("목걸이 목 선풍기", "挂脖风扇"),
    ],
)
def test_live_product_families_keep_exact_chinese_compound(
    title, expected_chinese_anchor
):
    converted = convert_keywords_rule_based(title)
    assert expected_chinese_anchor in converted["chinese"]


@pytest.mark.parametrize(
    ("title", "expected_chinese", "expected_english"),
    [
        (
            "커피세컨즈 전동 우유거품기, 노즐3종, 거치대",
            "电动奶泡器",
            "electric milk frother",
        ),
        (
            "키친아트 솔리드 전기주전자, KAEK-B1500FT",
            "电水壶",
            "electric kettle",
        ),
        (
            "이코코 자동 치약 짜개 디스펜서, 혼합색상, 1개",
            "自动挤牙膏器",
            "automatic toothpaste dispenser",
        ),
        (
            "YEAAYE 전동 후추 그라인더 KT-701S, 1개, 80ml",
            "电动胡椒研磨器",
            "electric pepper grinder",
        ),
    ],
)
def test_live_product_variants_preserve_specific_automatic_intent(
    title, expected_chinese, expected_english
):
    converted = convert_keywords_rule_based(title)
    assert converted["chinese"].startswith(expected_chinese)
    assert converted["english"].startswith(expected_english)


def test_specific_compound_suppresses_nested_generic_product_family():
    frother = convert_keywords_rule_based("전동 우유거품기 노즐 3종")
    toothpaste = convert_keywords_rule_based("자동 치약 짜개 디스펜서")
    grinder = convert_keywords_rule_based("전동 후추 그라인더")

    assert "打蛋器" not in frother["chinese"]
    assert "egg whisk" not in frother["english"]
    assert toothpaste["chinese"] == "自动挤牙膏器"
    assert grinder["chinese"] == "电动胡椒研磨器"


@pytest.mark.parametrize(
    ("title", "candidate", "wrong_candidate"),
    [
        (
            "전동 우유거품기",
            "南极人调速电动奶泡器 手持咖啡打奶泡器",
            "无线电动打蛋器 烘焙奶油搅拌器",
        ),
        (
            "전동 휘핑기",
            "无线电动打蛋器 奶油烘焙打发器",
            "咖啡电动奶泡器 手持打奶泡器",
        ),
        (
            "전기주전자",
            "小熊电热水壶 家用自动断电烧水壶",
            "不锈钢保温随行杯",
        ),
        (
            "전동 후추 그라인더",
            "电动胡椒研磨器 厨房自动研磨瓶",
            "咖啡豆电动研磨器",
        ),
    ],
)
def test_narrow_platform_product_family_can_exceed_strict_95_gate(
    title, candidate, wrong_candidate
):
    converted = convert_keywords_rule_based(title)
    references = [title, converted["chinese"], converted["english"]]
    terms = _category_terms_for_keyword(
        converted["english"], reference_name=title, keyword_cn=converted["chinese"]
    )

    relevant, score = platform_searcher._relevance_result(
        candidate, references, 0.950001, terms
    )
    wrong, _ = platform_searcher._relevance_result(
        wrong_candidate, references, 0.950001, terms
    )

    assert terms
    assert relevant is True
    assert score is not None and score > 0.95
    assert wrong is False


def test_bathroom_scrubber_rejects_explicit_kitchen_dish_brush():
    title = "화장실 무선 전동 욕실 청소기 2in1 화장실 청소솔"
    converted = convert_keywords_rule_based(title)
    references = [title, converted["chinese"], converted["english"]]
    terms = _category_terms_for_keyword(
        converted["english"], reference_name=title, keyword_cn=converted["chinese"]
    )

    relevant, score = platform_searcher._relevance_result(
        "无线电动浴室清洁刷 家用卫生间长柄刷", references, 0.950001, terms
    )
    wrong, wrong_score = platform_searcher._relevance_result(
        "厨房洗碗电动刷 餐具清洁刷", references, 0.950001, terms
    )
    negative_manual_wording, negative_manual_score = platform_searcher._relevance_result(
        "多功能电动清洁刷 浴室瓷砖轻松刷洗 省力告别手动硬搓",
        references,
        0.950001,
        terms,
    )

    assert relevant is True
    assert score is not None and score > 0.95
    assert wrong is False
    assert wrong_score == 0.0
    assert negative_manual_wording is True
    assert negative_manual_score is not None and negative_manual_score > 0.95


@pytest.mark.parametrize(
    ("keyword_en", "keyword_cn", "candidate", "wrong_candidate"),
    [
        ("portable wireless blender cup", "便携式无线榨汁杯", "无线榨汁杯搅拌机", "保温随行杯"),
        ("automatic foam soap dispenser", "自动泡沫洗手机", "感应泡沫皂液器", "浴室置物架"),
        ("portable handheld garment steamer", "手持挂烫机", "便携蒸汽熨斗挂烫机", "厨房蒸锅"),
        ("mini humidifier", "迷你加湿器", "桌面喷雾加湿器", "迷你电风扇"),
        ("electric wine opener", "电动红酒开瓶器", "自动红酒开瓶器", "电动削皮器"),
        ("wireless garlic food chopper", "无线电动蒜泥器", "无线蒜泥器绞肉机", "手动切菜板"),
        ("motion sensor rechargeable light", "人体感应灯", "充电人体感应灯", "手机充电器"),
        ("pet steam brush", "宠物蒸汽梳", "猫狗宠物蒸汽梳", "浴室清洁刷"),
        ("foldable laptop stand", "折叠笔记本电脑支架", "铝合金笔记本电脑支架", "手机支架"),
        ("neck fan", "挂脖风扇", "无叶挂脖风扇", "桌面小风扇"),
    ],
)
def test_live_product_families_use_specific_category_guard(
    keyword_en, keyword_cn, candidate, wrong_candidate
):
    terms = _category_terms_for_keyword(keyword_en, keyword_cn=keyword_cn)
    assert terms
    assert _passes_category_guard(candidate, terms)
    assert not _passes_category_guard(wrong_candidate, terms)


def test_garment_steamer_queries_cover_native_seller_aliases():
    queries = _preferred_chinese_query_variants(
        "手持挂烫机 便携式蒸汽熨斗", "portable handheld garment steamer"
    )
    assert queries[0] == "手持挂烫机 便携式蒸汽熨斗"
    assert "手持挂烫机" in queries
    assert "蒸汽熨斗" in queries
    assert "便携挂烫机" in queries


def test_neck_fan_queries_do_not_fall_back_only_to_handheld_fans():
    queries = _preferred_chinese_query_variants(
        "挂脖风扇 便携式手持风扇", "neck fan portable handheld fan"
    )
    assert queries[0] == "挂脖风扇 便携式手持风扇"
    assert "挂脖风扇" in queries
    assert "颈挂风扇" in queries
    assert "无叶挂脖风扇" in queries


def test_specific_neck_fan_intent_wins_over_generic_portable_fan_translation():
    references = [
        "목 선풍기 무선 휴대용 선풍기",
        "挂脖风扇 便携式手持风扇",
        "neck fan portable handheld fan",
    ]
    terms = _category_terms_for_keyword(
        references[-1], reference_name=references[0], keyword_cn=references[1]
    )

    relevant, score = platform_searcher._relevance_result(
        "户外挂脖风扇 上班族夏日降温神器", references, 0.75, terms
    )
    assert relevant is True
    assert score is not None and score >= 0.75

    wrong, _ = platform_searcher._relevance_result(
        "桌面小风扇 办公室迷你风扇", references, 0.75, terms
    )
    assert wrong is False


def test_neck_fan_rejects_keyword_stuffed_waist_fan_listing():
    references = [
        "목 선풍기 무선 휴대용 선풍기",
        "挂脖风扇 便携式手持风扇",
        "neck fan portable handheld fan",
    ]
    terms = _category_terms_for_keyword(
        references[-1], reference_name=references[0], keyword_cn=references[1]
    )

    relevant, score = platform_searcher._relevance_result(
        "有厘头高速挂腰风扇大容量户外随身USB小风扇无叶涡轮挂脖风扇",
        references,
        0.75,
        terms,
    )

    assert relevant is False
    assert score == 0.0


def test_candidate_budget_is_spread_across_query_aliases():
    attempted = set()
    skip = set()

    first = platform_searcher._take_fresh_page_links(
        [f"https://www.douyin.com/video/700000000000000000{i}" for i in range(4)],
        attempted,
        skip,
    )
    second = platform_searcher._take_fresh_page_links(
        [f"https://www.douyin.com/video/710000000000000000{i}" for i in range(4)],
        attempted,
        skip,
    )
    third = platform_searcher._take_fresh_page_links(
        [f"https://www.douyin.com/video/720000000000000000{i}" for i in range(4)],
        attempted,
        skip,
    )
    exhausted = platform_searcher._take_fresh_page_links(
        ["https://www.douyin.com/video/7300000000000000000"], attempted, skip
    )

    assert [len(first), len(second), len(third), len(exhausted)] == [2, 2, 2, 0]
    assert len(attempted) == platform_searcher.MAX_PAGE_ATTEMPTS_PER_PLATFORM


def test_platform_relevance_uses_shared_score_and_reference_constraints(monkeypatch):
    monkeypatch.setattr(platform_searcher, "_multi_reference_score", lambda evidence, refs: 0.94)

    score = platform_searcher.candidate_relevance_score(
        "Cordless kitchen cleaning demonstration",
        ["electric spin scrubber cleaning brush"],
    )
    assert score == 0.94

    accessory = "Replacement Brush Heads for Electric Spin Scrubber Accessories"
    relevant, score = platform_searcher._relevance_result(
        accessory,
        ["electric spin scrubber cordless cleaning brush"],
        0.9,
        ["brush"],
    )
    assert relevant is False
    assert score == 0.0


def test_platform_relevance_preserves_exact_candidate_owned_product_phrase():
    score = platform_searcher.candidate_relevance_score(
        "미니 선풍기 사용 후기",
        ["미니 선풍기"],
    )
    assert score is not None and score >= 0.9


def test_platform_generic_reference_cannot_override_richer_subtype_intent():
    refs = [
        "automatic electric cleaning brush spin scrubber",
        "cleaning brush",
    ]
    relevant, score = platform_searcher._relevance_result(
        "cleaning brush", refs, 0.9, ["brush"]
    )
    assert relevant is False
    assert score is not None and score < 0.9


def test_platform_legacy_source_urls_are_canonicalized_before_skip():
    assert platform_searcher._canonical_source_ids(
        {"https://www.douyin.com/video/7351234567890123456?from=old"}
    ) == {"douyin:7351234567890123456"}


def test_media_url_guard_rejects_private_network_targets():
    assert not _is_safe_remote_media_url("http://127.0.0.1/video.mp4")
    assert not _is_safe_remote_media_url("http://169.254.169.254/latest/meta-data")
    assert _is_safe_remote_media_url("https://8.8.8.8/video.mp4")


def test_browser_cookies_are_scoped_to_target_domain():
    class _Cookie:
        def __init__(self, domain, name, value):
            self.domain = domain
            self.name = name
            self.value = value

    class _Cookies:
        async def get_all(self):
            return [
                _Cookie(".douyin.com", "sessionid", "secret"),
                _Cookie(".douyinvod.com", "cdn", "signed"),
            ]

    class _Browser:
        cookies = _Cookies()

    scoped = asyncio.run(
        platform_searcher._browser_cookies_for(
            _Browser(), "douyin", "https://v1.douyinvod.com/video.mp4"
        )
    )
    assert scoped == {"cdn": "signed"}


def test_media_request_never_sends_cookies_over_http(monkeypatch):
    headers_seen = []

    class _Response:
        status_code = 200
        headers = {}

    def fake_open(_url, headers):
        headers_seen.append(headers)
        return _Response()

    monkeypatch.setattr(
        "core.sourcing.product_searcher._open_pinned_media_hop", fake_open
    )
    _get_media_response(
        "http://8.8.8.8/video.mp4",
        headers={},
        cookies={"sid": "secret"},
    )
    assert "Cookie" not in headers_seen[0]


def test_media_request_rejects_https_to_http_downgrade(monkeypatch):
    class _Redirect:
        status_code = 302
        headers = {"Location": "http://8.8.8.8/video.mp4"}

        def close(self):
            return None

    monkeypatch.setattr(
        "core.sourcing.product_searcher._open_pinned_media_hop",
        lambda *_args, **_kwargs: _Redirect(),
    )
    with pytest.raises(ValueError, match="downgrade"):
        _get_media_response(
            "https://8.8.8.8/video.mp4",
            headers={},
            cookies={"sid": "secret"},
        )


def test_hls_download_is_fail_closed():
    assert _download_hls_via_ffmpeg(
        "https://8.8.8.8/playlist.m3u8", "unused.mp4", "https://example.com"
    ) is None


def test_media_hop_connects_to_the_validated_ip(monkeypatch):
    from urllib.parse import urlparse
    from utils import Tool, url_security

    connections = []

    class _RawResponse:
        status = 200
        headers = {}

        def read(self, _amount=-1):
            return b""

        def close(self):
            return None

    class _Connection:
        def __init__(self, hostname, pinned_ip, *, port, timeout):
            connections.append((hostname, pinned_ip, port, timeout))

        def request(self, _method, _path, headers):
            assert headers["Host"] == "media.example"

        def getresponse(self):
            return _RawResponse()

        def close(self):
            return None

    monkeypatch.setattr(
        url_security,
        "resolve_public_http_url",
        lambda url: (urlparse(url), ("93.184.216.34",)),
    )
    monkeypatch.setattr(Tool, "_PinnedHTTPSConnection", _Connection)

    response = _open_pinned_media_hop("https://media.example/video.mp4", {})
    response.close()
    assert connections == [("media.example", "93.184.216.34", 443, 60)]


def test_product_detail_duplicate_is_skipped_before_navigation():
    class BrowserThatMustNotNavigate:
        async def get(self, url):
            raise AssertionError(f"duplicate URL navigated: {url}")

    result = asyncio.run(
        find_products_with_video(
            BrowserThatMustNotNavigate(),
            [{
                "url": "https://www.aliexpress.com/item/1005001234567890.html?spm=new",
                "title": "Electric Spin Scrubber Cleaning Brush",
                "score": 1.0,
            }],
            ".",
            "aliexpress",
            skip_source_ids={
                "https://m.aliexpress.com/item/1005001234567890.html?aff=old"
            },
        )
    )

    assert result == []
