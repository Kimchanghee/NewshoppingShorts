# -*- coding: utf-8 -*-
"""
3플랫폼(샤오홍슈/도우인/콰이쇼우) 키워드 영상 검색기.

기존 AliExpress/1688 소싱과 동일 패턴(zendriver + _extract_video_urls + _download_video)을
재사용해서 상품명 키워드로 세 채널을 검색하고, 안전 기준을 통과한 후보 중
상품 관련성 점수가 가장 높은 영상을 선택한다.

다운로드 전략(성공률 순):
  1) 검색 결과에서 영상 '페이지 링크'(douyin.com/video/{id} 등)를 긁어 yt-dlp에 위임
     — 서명된 CDN URL·만료 문제를 yt-dlp가 처리(도우인/콰이쇼우 추출기 지원).
  2) 폴백: 페이지 HTML에서 직접 mp4 URL 추출(RENDER_DATA 디코드 포함) 후 requests 다운로드.

다운로드 후 ffprobe로 길이/해상도 검증(광고·무관 초장·초단 영상 걸러냄).
`skip_source_ids`로 이미 사용한 소스 영상 재사용을 차단한다.

현실 주의: 도우인/샤오홍슈는 안티봇·로그인 게이트가 강함. `~/.ssmaker/zendriver_profile`
영구 프로필에 사용자가 한 번 로그인해두면 이후 세션에서 재사용된다. 콰이쇼우가 상대적으로 접근이 쉬움.
"""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional, Set

from utils.logging_config import get_logger

# 기존 소싱 유틸 재사용(중복 구현 방지).
from core.sourcing.product_searcher import (
    _download_video,
    _extract_video_urls,
    _generic_reference_lacks_richer_evidence,
    _multi_reference_score,
    _page_has_access_challenge,
    _passes_category_guard,
    _passes_reference_constraints,
)

logger = get_logger(__name__)

# 순서는 동점일 때의 우선순위다. 상품 후기·판매 영상 비중이 높은
# 실제 다운로드 성공률이 높은 도우인을 먼저 보고, 샤오홍슈·콰이쇼우로 폴백한다.
# Douyin first: its public detail pages expose a playable Resource Timing URL
# most consistently. Xiaohongshu/Kuaishou remain automatic fallbacks.
DEFAULT_PLATFORM_ORDER = ["douyin", "xiaohongshu", "kuaishou"]
SUPPORTED_COMMERCE_PLATFORMS = frozenset(DEFAULT_PLATFORM_ORDER)

# 검증 기준(쇼츠 소스로 쓸 수 있는 영상).
MIN_SOURCE_SECONDS = 4.0
# Product demonstrations are often longer than a finished Short.  The existing
# re-editor selects/trims the usable segment, so accept source material up to
# five minutes while still rejecting accidental long-form downloads.
MAX_SOURCE_SECONDS = 300.0
MIN_SOURCE_SHORT_SIDE = 480


def _diagnostic_event(
    diagnostics: Optional[Dict[str, Any]],
    code: str,
    *,
    platform: str = "",
    detail: str = "",
) -> None:
    """Accumulate safe failure evidence without changing the search result API."""
    if diagnostics is None:
        return
    counts = diagnostics.setdefault("counts", {})
    counts[code] = int(counts.get(code, 0) or 0) + 1
    if platform:
        platforms = diagnostics.setdefault("platforms", {})
        platform_counts = platforms.setdefault(platform, {})
        platform_counts[code] = int(platform_counts.get(code, 0) or 0) + 1
    if detail:
        diagnostics["last_detail"] = str(detail).strip()[:160]
    events = diagnostics.setdefault("events", [])
    events.append({
        "code": str(code or ""),
        "platform": str(platform or ""),
        "detail": str(detail or "").strip()[:160],
    })
    del events[:-50]


_BROWSER_SESSION_EXCEPTION_NAMES = frozenset({
    "BrowserClosed",
    "BrowserError",
    "ConnectionClosed",
    "ConnectionClosedError",
    "InvalidState",
    "TargetClosedError",
    "WebSocketException",
})


def _is_browser_session_error(exc: BaseException) -> bool:
    """Classify typed transport/session failures without matching messages."""
    if isinstance(exc, (ConnectionError, BrokenPipeError, EOFError)):
        return True
    return any(
        cls.__name__ in _BROWSER_SESSION_EXCEPTION_NAMES
        for cls in type(exc).__mro__
    )


def _has_browser_session_failure(
    diagnostics: Optional[Dict[str, Any]],
) -> bool:
    counts = (diagnostics or {}).get("counts") or {}
    return bool(counts.get("browser_session_failed"))


def _normalized_relevance_text(value: str) -> str:
    return " ".join(re.findall(r"[0-9a-zA-Z가-힣\u3400-\u9fff]+", str(value or "").lower()))


def _queries_for_chinese_platform(queries: List[str]) -> List[str]:
    """Use translated Chinese queries; never paste Korean into Chinese sites."""
    clean = list(dict.fromkeys(
        " ".join(re.sub(r"[가-힣]+", " ", str(query or "")).split())
        for query in queries
        if str(query or "").strip()
    ))
    non_korean = [query for query in clean if query]
    chinese = [query for query in non_korean if re.search(r"[\u3400-\u9fff]", query)]
    return chinese or non_korean


def candidate_relevance_score(evidence: str, references: List[str]) -> Optional[float]:
    """Score candidate-owned title/caption evidence against product references.

    Search queries are deliberately not accepted as evidence.  The caller may
    provide product-derived multilingual names as references, while *evidence*
    must come from yt-dlp or the candidate page itself.
    """
    candidate = _normalized_relevance_text(evidence)
    if not candidate:
        return None
    candidate_tokens = set(candidate.split())
    eligible_references: List[str] = []
    best_coverage = 0.0
    for raw_reference in references or []:
        reference = _normalized_relevance_text(raw_reference)
        if not reference:
            continue
        reference_tokens = set(reference.split())
        compact_reference = reference.replace(" ", "")
        # A generic one-word translation such as "fan" is not a product
        # identity. Letting it reach 100% coverage made unrelated videos pass.
        if len(reference_tokens) < 2 and len(compact_reference) < 4:
            continue
        eligible_references.append(raw_reference)
        coverage = len(candidate_tokens & reference_tokens) / max(1, len(reference_tokens))
        if coverage >= 0.9 and _generic_reference_lacks_richer_evidence(
            evidence, raw_reference, references
        ):
            coverage = min(coverage, 0.89)
        best_coverage = max(best_coverage, coverage)
    if not eligible_references:
        return 0.0
    if not _passes_reference_constraints(evidence, eligible_references):
        return 0.0

    # Use the same multilingual semantic/Jaccard scorer as product sourcing.
    # Reference-token coverage remains as candidate-owned literal evidence so
    # an exact product phrase followed by caption words ("... 사용 후기") keeps
    # its prior positive behavior without restoring fuzzy sequence matching.
    shared_score = _multi_reference_score(evidence, eligible_references)
    return min(1.0, max(0.0, shared_score, best_coverage))


def _relevance_result(
    evidence: str,
    references: List[str],
    min_score: float,
    category_terms: Optional[List[str]] = None,
) -> tuple[bool, Optional[float]]:
    if not _passes_category_guard(evidence, category_terms or []):
        return False, 0.0
    if not _passes_reference_constraints(evidence, references):
        return False, 0.0
    score = candidate_relevance_score(evidence, references)
    # Chinese captions are commonly written without spaces, so token/Jaccard
    # scoring can under-rate an obvious family match ("自动打蛋器" vs
    # "电动打蛋器").  A literal CJK/Korean category anchor is candidate-owned
    # evidence and is sufficient for the user's product-video policy. Explicit
    # contradictions/accessory checks above still have veto power.
    evidence_lower = str(evidence or "").lower()
    strong_category_match = any(
        len(compact) >= 2
        and bool(re.search(r"[가-힣\u3400-\u9fff]", compact))
        and compact.lower() in evidence_lower
        for term in (category_terms or [])
        if (compact := re.sub(r"\s+", "", str(term or "")))
    )
    if score is not None and strong_category_match:
        score = max(score, 0.75)
    # The caller selects the policy. Marketplace identity matching normally
    # passes 0.9; product-video discovery intentionally passes 0.75 because it
    # needs the same product family, not the identical seller/model.
    threshold = max(0.70, min(1.0, min_score))
    return score is not None and score >= threshold, score

# 플랫폼별 검색 URL 템플릿 + 다운로드 referer.
_SEARCH_URL = {
    "douyin": "https://www.douyin.com/search/{kw}?type=video",
    "kuaishou": "https://www.kuaishou.com/search/video?searchKey={kw}",
    "xiaohongshu": "https://www.xiaohongshu.com/search_result?keyword={kw}&type=video",
    "bilibili": "https://search.bilibili.com/video?keyword={kw}&order=click",
}
_REFERER = {
    "douyin": "https://www.douyin.com/",
    "kuaishou": "https://www.kuaishou.com/",
    "xiaohongshu": "https://www.xiaohongshu.com/",
    "bilibili": "https://www.bilibili.com/",
}

# yt-dlp 추출기가 지원하는 플랫폼(영상 페이지 링크 → yt-dlp 다운로드).
_YTDLP_PLATFORMS = {"douyin", "kuaishou", "xiaohongshu", "bilibili"}

# 검색 결과에서 영상 '페이지 링크'를 찾는 패턴(href/절대경로 모두).
_PAGE_LINK_PATTERNS = {
    "douyin": re.compile(r"(?:https?://www\.douyin\.com)?(/video/(\d{10,25}))"),
    "kuaishou": re.compile(r"(?:https?://www\.kuaishou\.com)?(/short-video/([0-9A-Za-z_-]{8,}))"),
    "xiaohongshu": re.compile(r"(?:https?://www\.xiaohongshu\.com)?(/explore/([0-9a-f]{20,}))"),
    "bilibili": re.compile(r"(?:https?://www\.bilibili\.com)?(/video/(BV[0-9A-Za-z]{10}))"),
}
_PAGE_LINK_BASE = {
    "douyin": "https://www.douyin.com",
    "kuaishou": "https://www.kuaishou.com",
    "xiaohongshu": "https://www.xiaohongshu.com",
    "bilibili": "https://www.bilibili.com",
}

# 플랫폼 CDN mp4 보강 추출(제네릭 _extract_video_urls가 놓칠 때 대비).
# 도우인 RENDER_DATA는 percent-encoded JSON이라 디코드 후에도 스캔한다.
_PLATFORM_MP4_JS = r"""
(() => {
    let html = document.documentElement ? document.documentElement.innerHTML : '';
    try {
        const rd = document.getElementById('RENDER_DATA');
        if (rd && rd.textContent) html += decodeURIComponent(rd.textContent);
    } catch (e) {}
    const out = new Set();
    const pats = [
        /(https?:\/\/[a-z0-9.-]*douyinvod\.com[^\s"'\\<>]*?\.mp4[^\s"'\\<>]*)/g,
        /(https?:\/\/[a-z0-9.-]*\.douyinpic\.com[^\s"'\\<>]*?\.mp4[^\s"'\\<>]*)/g,
        /(https?:\/\/[a-z0-9.-]*kwaicdn\.com[^\s"'\\<>]*?\.mp4[^\s"'\\<>]*)/g,
        /(https?:\/\/[a-z0-9.-]*txmov2[^\s"'\\<>]*?\.mp4[^\s"'\\<>]*)/g,
        /(https?:\/\/[a-z0-9.-]*xhscdn\.com[^\s"'\\<>]*?\.mp4[^\s"'\\<>]*)/g,
        /"playAddr"\s*:\s*"([^"]+\.mp4[^"]*)"/g,
        /"url"\s*:\s*"([^"]+\.mp4[^"]*)"/g,
    ];
    for (const re of pats) { let m; while ((m = re.exec(html))) out.add(m[1].replace(/\\u002F/g,'/').replace(/\\\//g,'/')); }
    document.querySelectorAll('video[src]').forEach(v => { if (v.src && !v.src.startsWith('blob:')) out.add(v.src); });
    // Modern Douyin/Kuaishou players commonly use MediaSource blobs.  The
    // actual MP4 request is still visible in Resource Timing, but its signed
    // CDN path often has no `.mp4` suffix (Douyin uses
    // `.../video/tos/...?...&mime_type=video_mp4`).  Looking only at DOM
    // attributes therefore misses a video which is already playing.
    try {
        performance.getEntriesByType('resource').forEach(entry => {
            const u = String(entry && entry.name || '').replace(/&amp;/g, '&');
            if (!u.startsWith('http')) return;
            if (
                /[?&]mime_type=video_(?:mp4|x-flv)(?:&|$)/i.test(u) ||
                /\/video\/tos\//i.test(u) ||
                /(?:douyinvod|zjcdn|kwaicdn|txmov2|xhscdn)\./i.test(u) &&
                    /(?:video|play|\.mp4|\.m3u8)/i.test(u)
            ) out.add(u);
        });
    } catch (e) {}
    return [...out];
})()
"""

_PAGE_HTML_JS = r"""
(() => {
    let html = document.documentElement ? document.documentElement.outerHTML : '';
    document.querySelectorAll('a[href]').forEach(a => {
        html += '\n' + a.href;
        try { html += '\n' + decodeURIComponent(a.href); } catch (e) {}
    });
    // SSR/상태 스토어 — 로그인 없이도 검색 결과 데이터가 들어있는 경우가 많다.
    try { const rd = document.getElementById('RENDER_DATA');
          if (rd && rd.textContent) html += '\n' + decodeURIComponent(rd.textContent); } catch (e) {}
    try { if (window.__APOLLO_STATE__) html += '\n' + JSON.stringify(window.__APOLLO_STATE__); } catch (e) {}
    try { if (window._ROUTER_DATA) html += '\n' + JSON.stringify(window._ROUTER_DATA); } catch (e) {}
    try { if (window.__INITIAL_STATE__) html += '\n' + JSON.stringify(window.__INITIAL_STATE__); } catch (e) {}
    return html.slice(0, 6000000);
})()
"""

# SSR JSON 스토어에서 영상 ID를 직접 뽑는 보조 패턴(href가 없어도 링크 구성 가능).
_ID_PATTERNS = {
    "douyin": [
        re.compile(r'"aweme_id"\s*:\s*"(\d{15,25})"'),
        re.compile(r'"awemeId"\s*:\s*"(\d{15,25})"'),
    ],
    "kuaishou": [
        re.compile(r'VisionVideoDetailPhoto:([0-9A-Za-z_-]{8,})'),
        re.compile(r'"photoId"\s*:\s*"([0-9A-Za-z_-]{8,})"'),
    ],
    "bilibili": [
        re.compile(r'"bvid"\s*:\s*"(BV[0-9A-Za-z]{10})"'),
    ],
}
_ID_LINK_TEMPLATE = {
    "douyin": "https://www.douyin.com/video/{id}",
    "kuaishou": "https://www.kuaishou.com/short-video/{id}",
    "bilibili": "https://www.bilibili.com/video/{id}",
}

# 검색 전 홈 방문으로 기본 쿠키(ttwid/did 등)를 심는다 — 비로그인 검색 렌더 성공률용.
_WARMUP_URL = {
    "douyin": "https://www.douyin.com/",
    "kuaishou": "https://www.kuaishou.com/",
    "xiaohongshu": "https://www.xiaohongshu.com/",
}

# 외부 검색엔진 폴백 — 플랫폼 '검색'만 게이트일 뿐 영상 페이지는 비로그인 시청 가능
# (실측: 도우인 검색=셸만 렌더, 콰이쇼우 검색=홈 리다이렉트). 그래서 검색은
# 일반 Chrome/로그인 프로필에서 성공률이 가장 높았던 Google 색인 검색을
# 먼저 사용하고, DuckDuckGo/Bing/Brave를 순차 폴백한다. 다운로드는 기존
# yt-dlp+쿠키 경로를 그대로 쓴다.
_EXTERNAL_SITE_FILTER = {
    "douyin": "douyin.com/video",
    "kuaishou": "kuaishou.com/short-video",
    "xiaohongshu": "xiaohongshu.com/explore",
    "bilibili": "bilibili.com/video",
}
_EXTERNAL_SEARCH_PROVIDERS = ("google", "duckduckgo", "bing", "brave")


def _external_search_url(provider: str, query: str) -> str:
    encoded = urllib.parse.quote(query)
    if provider == "google":
        return f"https://www.google.com/search?q={encoded}&hl=zh-CN"
    if provider == "duckduckgo":
        return f"https://html.duckduckgo.com/html/?q={encoded}"
    if provider == "bing":
        return f"https://www.bing.com/search?q={encoded}&setlang=zh-Hans"
    if provider == "brave":
        return f"https://search.brave.com/search?q={encoded}&source=web"
    return ""


def _page_links_from_html(platform: str, page_html: str) -> List[str]:
    """Extract canonical, deduplicated platform video pages from HTML text."""
    pat = _PAGE_LINK_PATTERNS.get(platform)
    if pat is None or not isinstance(page_html, str) or not page_html:
        return []
    seen: Set[str] = set()
    links: List[str] = []
    for match in pat.finditer(page_html):
        path_part = match.group(1)
        video_id = match.group(2)
        if video_id in seen:
            continue
        seen.add(video_id)
        links.append(_PAGE_LINK_BASE[platform] + path_part)
    template = _ID_LINK_TEMPLATE.get(platform)
    for id_pattern in _ID_PATTERNS.get(platform, []):
        for match in id_pattern.finditer(page_html):
            video_id = match.group(1)
            if video_id in seen:
                continue
            seen.add(video_id)
            links.append(template.format(id=video_id))
    return links


def _http_external_search_links(
    provider: str, platform: str, url: str
) -> List[str]:
    """Read server-rendered search HTML when an automated browser is challenged."""
    if provider != "brave" or not url.startswith("https://search.brave.com/"):
        return []
    import html as html_module
    import requests

    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        },
        timeout=15,
    )
    response.raise_for_status()
    page_html = html_module.unescape(str(response.text or ""))[:6_000_000]
    decoded = urllib.parse.unquote(page_html)
    if decoded != page_html:
        page_html += "\n" + decoded
    return _page_links_from_html(platform, page_html)


async def _external_search_links(
    browser: Any, platform: str, query: str, output_dir: str = "",
    diagnostics: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Search public indexes in order and skip blocked providers automatically."""
    site = _EXTERNAL_SITE_FILTER.get(platform)
    if not site:
        return []
    # Xiaohongshu /explore mixes image notes and videos under one URL shape.
    # Adding the native "video" intent word cuts photo-only notes before the
    # extractor stage; Douyin/Kuaishou URL paths are already video-specific.
    intent_query = f"{query} 视频" if platform == "xiaohongshu" else query
    search_query = f"{intent_query} site:{site}"
    blocked_providers = set(
        str(value)
        for value in ((diagnostics or {}).get("blocked_search_providers") or [])
    )

    def block_provider(provider_name: str) -> None:
        blocked_providers.add(provider_name)
        if diagnostics is not None:
            stored = diagnostics.setdefault("blocked_search_providers", [])
            if provider_name not in stored:
                stored.append(provider_name)

    # A paired extension uses the user's already-running Chrome profile. This
    # avoids copying cookies and still gives SSMaker the indexed public page
    # links that were visible in a normal logged-in Chrome session.
    try:
        from core.sourcing.chrome_extension_bridge import get_chrome_extension_bridge

        extension_bridge = get_chrome_extension_bridge()
        # App startup normally owns the bridge. Starting lazily as well keeps
        # queue-only and diagnostic entrypoints able to use the paired Chrome
        # profile without requiring the full GUI process.
        extension_bridge.start()
        if extension_bridge.is_connected():
            extension_links = await asyncio.wait_for(
                asyncio.to_thread(
                    extension_bridge.search_index,
                    platform,
                    intent_query,
                    35.0,
                ),
                timeout=40.0,
            )
            if extension_links:
                logger.info(
                    "[PlatformSearch] %s: 로그인된 Chrome 색인 링크 %d개",
                    platform,
                    len(extension_links),
                )
                return extension_links
            _diagnostic_event(
                diagnostics,
                "no_results",
                platform="search:chrome_extension",
            )
    except asyncio.TimeoutError:
        _diagnostic_event(
            diagnostics,
            "page_open_timeout",
            platform="search:chrome_extension",
        )
    except Exception as exc:
        _diagnostic_event(
            diagnostics,
            "page_open_error",
            platform="search:chrome_extension",
            detail=type(exc).__name__,
        )

    for provider in _EXTERNAL_SEARCH_PROVIDERS:
        if provider in blocked_providers:
            continue
        url = _external_search_url(provider, search_query)
        if not url:
            continue
        diagnostic_platform = f"search:{provider}"
        if provider == "brave":
            try:
                links = await asyncio.wait_for(
                    asyncio.to_thread(
                        _http_external_search_links, provider, platform, url
                    ),
                    timeout=PAGE_OPEN_TIMEOUT,
                )
            except asyncio.TimeoutError:
                _diagnostic_event(
                    diagnostics, "page_open_timeout", platform=diagnostic_platform
                )
                continue
            except Exception as exc:
                status_code = getattr(
                    getattr(exc, "response", None), "status_code", None
                )
                code = "rate_limited" if status_code == 429 else "page_open_error"
                detail = f"HTTP {status_code}" if status_code else type(exc).__name__
                if code == "rate_limited":
                    block_provider(provider)
                _diagnostic_event(
                    diagnostics,
                    code,
                    platform=diagnostic_platform,
                    detail=detail,
                )
                continue
            if links:
                logger.info(
                    "[PlatformSearch] %s: 외부검색(%s HTTP) 링크 %d개",
                    platform,
                    provider,
                    len(links),
                )
                return links
            _diagnostic_event(
                diagnostics, "no_results", platform=diagnostic_platform
            )
            continue
        try:
            tab = await asyncio.wait_for(
                browser.get(url, new_tab=True), timeout=PAGE_OPEN_TIMEOUT
            )
        except asyncio.TimeoutError:
            _diagnostic_event(
                diagnostics, "page_open_timeout", platform=diagnostic_platform
            )
            continue
        except Exception as exc:
            if _is_browser_session_error(exc):
                _diagnostic_event(
                    diagnostics,
                    "browser_session_failed",
                    platform=diagnostic_platform,
                    detail=type(exc).__name__,
                )
                return []
            _diagnostic_event(
                diagnostics,
                "page_open_error",
                platform=diagnostic_platform,
                detail=type(exc).__name__,
            )
            continue
        if tab is None:
            _diagnostic_event(diagnostics, "empty_page", platform=diagnostic_platform)
            continue
        try:
            await asyncio.sleep(2.5)
            if await asyncio.wait_for(
                _page_has_access_challenge(tab), timeout=EVAL_TIMEOUT
            ):
                logger.info(
                    "[PlatformSearch] 외부검색 %s 봇 확인 화면 — 다음 검색엔진으로",
                    provider,
                )
                _diagnostic_event(
                    diagnostics,
                    "access_challenge",
                    platform=diagnostic_platform,
                    detail="bot or login challenge",
                )
                block_provider(provider)
                continue
            links = await _extract_video_page_links(
                tab,
                platform,
                output_dir,
                f"{provider}:{query}",
                diagnostics=diagnostics,
            )
            if links:
                logger.info(
                    "[PlatformSearch] %s: 외부검색(%s) 링크 %d개",
                    platform,
                    provider,
                    len(links),
                )
                return links
            _diagnostic_event(
                diagnostics, "no_results", platform=diagnostic_platform
            )
        finally:
            try:
                await asyncio.wait_for(tab.close(), timeout=5)
            except Exception:
                pass
    return []

_DEBUG_DUMP_ENV = "SSMAKER_PLATFORM_DEBUG_DUMP"


def _debug_dump_enabled() -> bool:
    return str(os.environ.get(_DEBUG_DUMP_ENV, "")).strip() == "1"


def _normalize_source_id(url: str) -> str:
    """레지스트리와 동일 규칙의 소스 식별자(의존 없이 로컬 복제)."""
    try:
        from managers.uploaded_registry import normalize_source_id
        return normalize_source_id(url)
    except Exception:
        return str(url or "").strip().split("?")[0].split("#")[0].rstrip("/").lower()[:300]


def _canonical_source_ids(values: Optional[Set[str]]) -> Set[str]:
    return {
        canonical
        for value in (values or set())
        if (canonical := _normalize_source_id(str(value or "")))
    }


def probe_media_file(path: str) -> Dict[str, float]:
    """ffprobe로 길이(초)/가로/세로 조회. 실패 시 빈 dict."""
    if not path or not os.path.exists(path):
        return {}
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1"],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode != 0:
            raise RuntimeError("ffprobe failed")
        out: Dict[str, float] = {}
        for line in (r.stdout or "").splitlines():
            k, _, v = line.partition("=")
            try:
                out[k.strip()] = float(v.strip())
            except ValueError:
                continue
        if out:
            return out
    except Exception:
        pass

    # Packaged/runtime machines do not always expose ffprobe on PATH. OpenCV
    # is already an application dependency, and gives us a deterministic
    # duration/resolution fallback instead of silently trusting file size.
    try:
        import cv2

        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            capture.release()
            return {}
        width = float(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = float(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        capture.release()
        out = {"width": width, "height": height}
        if fps > 0 and frames > 0:
            out["duration"] = frames / fps
        return out
    except Exception:
        return {}


def validate_source_video(path: str) -> tuple[bool, str]:
    """소스로 쓸 수 있는 영상인지 검증(길이·해상도). (ok, reason)."""
    info = probe_media_file(path)
    if not info:
        # ffprobe가 없거나 실패 — 파일 크기만으로 통과시킴(과차단 방지).
        try:
            return (os.path.getsize(path) > 200_000), "probe_unavailable"
        except OSError:
            return False, "file_missing"
    dur = float(info.get("duration") or 0)
    w, h = int(info.get("width") or 0), int(info.get("height") or 0)
    if dur and (dur < MIN_SOURCE_SECONDS or dur > MAX_SOURCE_SECONDS):
        return False, f"duration_{dur:.1f}s"
    if w and h and min(w, h) < MIN_SOURCE_SHORT_SIDE:
        return False, f"resolution_{w}x{h}"
    return True, ""


BROWSER_START_TIMEOUT = 60.0


def _kill_orphan_profile_chrome(profile: str) -> int:
    """전용 자동화 프로필을 잡고 있는 고아 Chrome 종료(시작 실패 복구용).

    이 프로필은 ssmaker 자동화 전용이라, 시작이 실패했다는 것은 이전 실행이
    비정상 종료돼 Chrome만 남은 상태(실측: 12개 잔존 → 프로필 잠금)일 가능성이 높다.
    """
    killed = 0
    try:
        import psutil
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                name = (p.info.get("name") or "").lower()
                if not name.startswith("chrome"):
                    continue
                cmdline = p.info.get("cmdline") or []
                if any(profile in (a or "") for a in cmdline):
                    p.kill()
                    killed += 1
            except Exception:
                continue
    except Exception as e:
        logger.debug("[PlatformSearch] 고아 Chrome 정리 불가: %s", e)
    if killed:
        logger.warning("[PlatformSearch] 프로필 점유 고아 Chrome %d개 정리", killed)
    return killed


async def start_browser() -> Any:
    """영구 프로필 zendriver 브라우저 시작(사용자 로그인 재사용).

    같은 프로필을 잡고 있는 이전 자동화 Chrome이 남아 있으면 zd.start가 행/실패한다.
    → 타임아웃 + 고아 Chrome 정리 후 1회 재시도.
    """
    import zendriver as zd
    profile = os.path.join(os.path.expanduser("~"), ".ssmaker", "zendriver_profile")
    os.makedirs(profile, exist_ok=True)

    last_err: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            return await asyncio.wait_for(
                zd.start(
                    user_data_dir=profile,
                    headless=False,
                    sandbox=False,
                    browser_args=[
                        "--window-size=1400,900",
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--lang=zh-CN",
                        "--accept-lang=zh-CN,zh;q=0.9,en;q=0.7",
                    ],
                    # Chrome cold starts can exceed zendriver's 250ms default,
                    # especially after a forced cleanup of a stale profile.
                    browser_connection_timeout=1.5,
                    browser_connection_max_tries=40,
                ),
                timeout=BROWSER_START_TIMEOUT,
            )
        except (asyncio.TimeoutError, Exception) as e:  # zendriver raises plain Exception
            last_err = e
            if attempt == 1:
                logger.warning(
                    "[PlatformSearch] 브라우저 시작 실패(1차): %s — 고아 Chrome 정리 후 재시도",
                    str(e)[:120],
                )
                await asyncio.to_thread(_kill_orphan_profile_chrome, profile)
                await asyncio.sleep(2.0)
    raise RuntimeError(
        "자동화 브라우저를 시작할 수 없어요. 이전 자동화 Chrome 창이 남아 있으면 모두 닫은 뒤 "
        f"다시 시도해 주세요. (원인: {str(last_err)[:120]})"
    )


async def _extract_platform_videos(
    tab: Any,
    diagnostics: Optional[Dict[str, Any]] = None,
    platform: str = "",
) -> List[str]:
    """제네릭 추출 + 플랫폼 CDN 보강."""
    urls: List[str] = []
    try:
        urls = list(await asyncio.wait_for(_extract_video_urls(tab), timeout=EVAL_TIMEOUT * 2) or [])
    except Exception as exc:
        if _is_browser_session_error(exc):
            _diagnostic_event(
                diagnostics,
                "browser_session_failed",
                platform=platform,
                detail=type(exc).__name__,
            )
            raise
        urls = []
    try:
        extra = await asyncio.wait_for(
            tab.evaluate(_PLATFORM_MP4_JS, await_promise=False), timeout=EVAL_TIMEOUT
        )
        if isinstance(extra, list):
            for u in extra:
                if isinstance(u, str) and u.startswith("http") and u not in urls:
                    urls.append(u)
    except Exception as exc:
        if _is_browser_session_error(exc):
            _diagnostic_event(
                diagnostics,
                "browser_session_failed",
                platform=platform,
                detail=type(exc).__name__,
            )
            raise
    return [u for u in urls if _is_probable_platform_media_url(u)]


def _is_probable_platform_media_url(url: str) -> bool:
    """Drop page manifests and API documents before the downloader sees them."""
    try:
        parsed = urllib.parse.urlsplit(str(url or "").strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    rejected_suffixes = (
        ".css",
        ".gif",
        ".htm",
        ".html",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".m3u8",
        ".png",
        ".svg",
        ".webmanifest",
        ".xml",
    )
    if path.endswith(rejected_suffixes):
        return False
    if any(marker in path for marker in ("manifest.json", "/webmanifest", "/favicon")):
        return False
    if "mime_type=" in query and not re.search(
        r"(?:^|&)mime_type=video_(?:mp4|x-flv)(?:&|$)", query
    ):
        return False
    return True


async def _browser_cookies_for(
    browser: Any,
    platform: str,
    target_url: str = "",
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Return only cookies whose browser domain matches the target host."""
    keyword = {"douyin": "douyin", "kuaishou": "kuaishou", "xiaohongshu": "xiaohongshu"}.get(platform, platform)
    target_host = (urllib.parse.urlsplit(target_url).hostname or "").rstrip(".").lower()
    out: Dict[str, str] = {}
    try:
        cookies = await asyncio.wait_for(browser.cookies.get_all(), timeout=EVAL_TIMEOUT)
        for c in cookies or []:
            try:
                domain = str(getattr(c, "domain", "") or "")
                cookie_host = domain.lstrip(".").rstrip(".").lower()
                domain_matches_target = bool(target_host) and (
                    target_host == cookie_host or target_host.endswith(f".{cookie_host}")
                )
                if domain_matches_target or (not target_host and keyword in cookie_host):
                    out[str(getattr(c, "name", ""))] = str(getattr(c, "value", ""))
            except Exception:
                continue
    except Exception as exc:
        if _is_browser_session_error(exc):
            _diagnostic_event(
                diagnostics,
                "browser_session_failed",
                platform=platform,
                detail=type(exc).__name__,
            )
            raise
    return out


async def _extract_video_page_links(
    tab: Any,
    platform: str,
    output_dir: str = "",
    query: str = "",
    diagnostics: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """검색 결과 페이지에서 영상 '페이지 링크'를 추출(yt-dlp 위임용).

    href 스캔 + SSR 상태 스토어(RENDER_DATA/__APOLLO_STATE__ 등)의 영상 ID 스캔을
    함께 사용 — 로그인 없이도 데이터가 스토어에 실려 오는 경우를 잡는다.
    """
    pat = _PAGE_LINK_PATTERNS.get(platform)
    if pat is None:
        return []
    try:
        html = await asyncio.wait_for(
            tab.evaluate(_PAGE_HTML_JS, await_promise=False), timeout=EVAL_TIMEOUT
        )
    except Exception as exc:
        if _is_browser_session_error(exc):
            _diagnostic_event(
                diagnostics,
                "browser_session_failed",
                platform=platform,
                detail=type(exc).__name__,
            )
            raise
        return []
    if not isinstance(html, str) or not html:
        return []

    if _debug_dump_enabled() and output_dir:
        try:
            dump = os.path.join(
                output_dir, f"debug_{platform}_{uuid.uuid4().hex[:6]}.html"
            )
            with open(dump, "w", encoding="utf-8", errors="replace") as f:
                f.write(f"<!-- query: {query} -->\n")
                f.write(html)
            logger.info("[PlatformSearch] 디버그 덤프: %s (%d bytes)", dump, len(html))
        except Exception as exc:
            if _is_browser_session_error(exc):
                _diagnostic_event(
                    diagnostics,
                    "browser_session_failed",
                    platform=platform,
                    detail=type(exc).__name__,
                )
                raise

    return _page_links_from_html(platform, html)


def _ytdlp_download(
    page_url: str,
    output_dir: str,
    cookies: Optional[Dict[str, str]] = None,
    relevance_references: Optional[List[str]] = None,
    min_relevance_score: float = 0.9,
    category_terms: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """yt-dlp로 영상 페이지 다운로드(동기). 성공 시 {local_path, duration, ...}.

    다운로드 전에 메타만 먼저 뽑아 길이를 확인한다 — 빌리빌리처럼 긴 영상이 많은
    플랫폼에서 수백 MB를 받고 나서 버리는 낭비를 막는다.
    cookies: 자동화 브라우저 세션 쿠키(빌리빌리 412 리스크컨트롤 회피, 실측).
    """
    try:
        from core.sourcing.platform_video_collector import PlatformVideoCollector
        collector = PlatformVideoCollector(output_dir=output_dir)

        meta = collector.collect_one(page_url, download=False, cookies=cookies)
        if not meta.ok and meta.error:
            # 메타 추출부터 막히면 다운로드도 같은 이유로 실패 — 즉시 브라우저 폴백으로.
            return None
        if meta.ok and meta.duration and (
            meta.duration < MIN_SOURCE_SECONDS or meta.duration > MAX_SOURCE_SECONDS
        ):
            logger.info("[PlatformSearch] 길이 부적합 %.0fs — 스킵: %s",
                        meta.duration, page_url[:60])
            return {
                "technical_rejected": True,
                "reason": f"duration_{meta.duration:.1f}s",
                "title": str(meta.title or ""),
            }

        # yt-dlp can read the public title/caption without downloading the
        # media. Reject unrelated results here so a broad recall query never
        # wastes bandwidth on a clip that will be deleted immediately.
        evidence = str(meta.title or "").strip() if meta.ok else ""
        relevance_score: Optional[float] = None
        if relevance_references and evidence:
            relevant, relevance_score = _relevance_result(
                evidence,
                list(relevance_references),
                min_relevance_score,
                list(category_terms or []),
            )
            if not relevant:
                logger.info(
                    "[PlatformSearch] metadata relevance reject score=%s: %s",
                    relevance_score,
                    evidence[:100],
                )
                return {
                    "relevance_rejected": True,
                    "title": evidence,
                    "relevance_score": relevance_score,
                }
        elif relevance_references:
            # Let the browser-page fallback inspect document.title instead of
            # downloading a source whose identity evidence is still unknown.
            return None

        cv = collector.collect_one(page_url, download=True, cookies=cookies)
        if cv.ok and cv.local_path and os.path.exists(cv.local_path):
            return {
                "local_path": cv.local_path,
                "duration": cv.duration,
                "title": cv.title,
                "width": cv.width,
                "height": cv.height,
                "relevance_score": relevance_score,
            }
        if cv.error:
            logger.info("[PlatformSearch] yt-dlp 수집 실패(%s): %s", page_url[:60], cv.error[:160])
    except Exception as e:
        logger.info("[PlatformSearch] yt-dlp 실패(%s): %s", page_url[:60], str(e)[:160])
    return None


# 페이지 열기/스크립트 평가가 무한 대기하지 않도록 하는 타임아웃(초).
PAGE_OPEN_TIMEOUT = 40.0
EVAL_TIMEOUT = 15.0
# 플랫폼 1곳당 시간/후보 예산. 사진 노트·깨진 링크가 반복되어도
# 풀자동화 한 건이 무한정 늘어지지 않고 다음 플랫폼으로 넘어간다.
PER_PLATFORM_BUDGET = 120.0
MAX_PAGE_ATTEMPTS_PER_PLATFORM = 6
MAX_PAGE_ATTEMPTS_PER_QUERY = 2


def _take_fresh_page_links(
    page_links: List[str], attempted: Set[str], skip: Set[str]
) -> List[str]:
    """Reserve a small candidate slice without starving later query aliases."""
    fresh_links: List[str] = []
    for link in page_links:
        if len(fresh_links) >= MAX_PAGE_ATTEMPTS_PER_QUERY:
            break
        if len(attempted.difference(skip)) >= MAX_PAGE_ATTEMPTS_PER_PLATFORM:
            break
        source_id = _normalize_source_id(link)
        if source_id in attempted:
            continue
        attempted.add(source_id)
        fresh_links.append(link)
    return fresh_links


def _mux_streams(video_path: str, audio_path: Optional[str], out_path: str) -> bool:
    """DASH 분리 스트림(m4s)을 mp4로 합침(-c copy)."""
    cmd = ["ffmpeg", "-y", "-i", video_path]
    if audio_path and os.path.exists(audio_path):
        cmd += ["-i", audio_path]
    cmd += ["-c", "copy", "-movflags", "+faststart", out_path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


async def _browser_page_video_download(
    browser: Any, link: str, platform: str, output_dir: str,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """범용 브라우저 컨텍스트 다운로드 — yt-dlp가 막힐 때(도우인 'Fresh cookies' 등).

    영상 '페이지'는 비로그인 시청이 가능하므로, 페이지를 탭으로 열어 RENDER_DATA/
    playAddr에서 mp4 URL을 뽑고 세션 쿠키로 직접 받는다(빌리빌리 412 대응과 동일 패턴).
    """
    try:
        tab = await asyncio.wait_for(browser.get(link, new_tab=True), timeout=PAGE_OPEN_TIMEOUT)
    except Exception as exc:
        if _is_browser_session_error(exc):
            _diagnostic_event(
                diagnostics,
                "browser_session_failed",
                platform=platform,
                detail=type(exc).__name__,
            )
        return None
    if tab is None:
        return None
    try:
        await asyncio.sleep(3.0)
        try:
            if await asyncio.wait_for(
                _page_has_access_challenge(tab), timeout=EVAL_TIMEOUT
            ):
                _diagnostic_event(
                    diagnostics,
                    "access_challenge",
                    platform=platform,
                    detail="video page login or bot challenge",
                )
                return None
        except Exception as exc:
            if _is_browser_session_error(exc):
                _diagnostic_event(
                    diagnostics,
                    "browser_session_failed",
                    platform=platform,
                    detail=type(exc).__name__,
                )
                return None
        urls: List[str] = []
        for _ in range(3):
            urls = await _extract_platform_videos(
                tab, diagnostics=diagnostics, platform=platform
            )
            if urls:
                break
            await asyncio.sleep(2.0)
        if not urls:
            logger.info("[PlatformSearch] %s 페이지에서 mp4 못 찾음: %s", platform, link[:60])
            return None
        page_title = ""
        try:
            page_title = str(await asyncio.wait_for(
                tab.evaluate("document.title", await_promise=False), timeout=5
            ) or "")[:120]
            if page_title:
                logger.info("[PlatformSearch] %s 소스 제목: %s", platform, page_title[:80])
        except Exception as exc:
            if _is_browser_session_error(exc):
                _diagnostic_event(
                    diagnostics,
                    "browser_session_failed",
                    platform=platform,
                    detail=type(exc).__name__,
                )
                raise
        for vurl in urls[:3]:
            cookies = await _browser_cookies_for(
                browser, platform, vurl, diagnostics=diagnostics
            )
            path = os.path.join(output_dir, f"platform_{platform}_{uuid.uuid4().hex[:8]}.mp4")
            try:
                size = await asyncio.wait_for(
                    asyncio.to_thread(_download_video, vurl, path, link, cookies=cookies),
                    timeout=180,
                )
            except asyncio.TimeoutError:
                size = None
            if size:
                logger.info("[PlatformSearch] %s 브라우저 컨텍스트 다운로드 성공 %.1fMB", platform, size)
                return {"local_path": path, "duration": 0.0, "title": page_title, "via": "browser"}
        return None
    finally:
        try:
            await asyncio.wait_for(tab.close(), timeout=5)
        except Exception:
            pass


async def _bilibili_browser_download(
    browser: Any, link: str, output_dir: str
) -> Optional[Dict[str, Any]]:
    """빌리빌리 폴백: yt-dlp가 412(리스크컨트롤)로 막힐 때, 영상 페이지를 브라우저로
    열어 window.__playinfo__의 스트림 URL을 세션 쿠키로 직접 받는다(실측 대응)."""
    import json as _json

    try:
        tab = await asyncio.wait_for(browser.get(link, new_tab=True), timeout=PAGE_OPEN_TIMEOUT)
    except Exception:
        return None
    if tab is None:
        return None
    try:
        await asyncio.sleep(3.0)
        raw = None
        for _ in range(3):
            try:
                raw = await asyncio.wait_for(
                    tab.evaluate("JSON.stringify(window.__playinfo__ || null)", await_promise=False),
                    timeout=EVAL_TIMEOUT,
                )
            except Exception:
                raw = None
            if raw and raw != "null":
                break
            await asyncio.sleep(2.0)
        if not raw or raw == "null":
            logger.info("[PlatformSearch] bilibili __playinfo__ 없음: %s", link[:60])
            return None
        info = _json.loads(raw) if isinstance(raw, str) else (raw or {})
        data = info.get("data") or {}

        # 길이 확인(ms) — 과長 영상 다운로드 낭비 방지.
        timelength_ms = float(data.get("timelength") or 0)
        if timelength_ms and timelength_ms / 1000.0 > MAX_SOURCE_SECONDS:
            logger.info("[PlatformSearch] bilibili 길이 부적합 %.0fs — 스킵", timelength_ms / 1000.0)
            return None

        referer = link
        tag = uuid.uuid4().hex[:8]

        dash = data.get("dash") or {}
        videos = dash.get("video") or []
        if videos:
            vurl = videos[0].get("baseUrl") or videos[0].get("base_url") or ""
            audios = dash.get("audio") or []
            aurl = (audios[0].get("baseUrl") or audios[0].get("base_url") or "") if audios else ""
            vpath = os.path.join(output_dir, f"bili_{tag}_v.m4s")
            video_cookies = await _browser_cookies_for(browser, "bilibili", vurl)
            vsize = await asyncio.wait_for(
                asyncio.to_thread(_download_video, vurl, vpath, referer, cookies=video_cookies),
                timeout=180,
            ) if vurl else None
            if not vsize:
                return None
            apath = ""
            if aurl:
                apath = os.path.join(output_dir, f"bili_{tag}_a.m4s")
                audio_cookies = await _browser_cookies_for(browser, "bilibili", aurl)
                asize = await asyncio.wait_for(
                    asyncio.to_thread(_download_video, aurl, apath, referer, cookies=audio_cookies),
                    timeout=180,
                )
                if not asize:
                    apath = ""
            out = os.path.join(output_dir, f"platform_bilibili_{tag}.mp4")
            ok = await asyncio.to_thread(_mux_streams, vpath, apath or None, out)
            for p in (vpath, apath):
                if p:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            if ok:
                return {"local_path": out, "duration": timelength_ms / 1000.0, "title": ""}
            return None

        durl = data.get("durl") or []
        if durl:
            u = str(durl[0].get("url") or "")
            if not u:
                return None
            path = os.path.join(output_dir, f"platform_bilibili_{tag}.flv")
            media_cookies = await _browser_cookies_for(browser, "bilibili", u)
            size = await asyncio.wait_for(
                asyncio.to_thread(_download_video, u, path, referer, cookies=media_cookies),
                timeout=180,
            )
            if size:
                return {"local_path": path, "duration": timelength_ms / 1000.0, "title": ""}
        return None
    finally:
        try:
            await asyncio.wait_for(tab.close(), timeout=5)
        except Exception:
            pass


async def search_one_platform(
    browser: Any, platform: str, queries: List[str], output_dir: str,
    page_wait: float = 4.0,
    skip_source_ids: Optional[Set[str]] = None,
    budget_seconds: float = PER_PLATFORM_BUDGET,
    relevance_references: Optional[List[str]] = None,
    min_relevance_score: float = 0.9,
    category_terms: Optional[List[str]] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Return the first technically valid candidate that also passes relevance."""
    import time as _time

    tmpl = _SEARCH_URL.get(platform)
    if not tmpl:
        _diagnostic_event(diagnostics, "unsupported_platform", platform=platform)
        return None
    os.makedirs(output_dir, exist_ok=True)
    skip = _canonical_source_ids(skip_source_ids)
    # A result often appears under every query variant. Track attempted page
    # IDs for this platform run so photo notes, broken videos and rejected
    # clips are never probed repeatedly.
    tried_source_ids = set(skip)
    deadline = _time.monotonic() + max(30.0, float(budget_seconds))

    # 홈 워밍업: 기본 쿠키(ttwid/did 등)를 먼저 심어 비로그인 검색 렌더 성공률을 올린다.
    warmup = _WARMUP_URL.get(platform)
    if warmup:
        try:
            wtab = await asyncio.wait_for(browser.get(warmup, new_tab=True), timeout=PAGE_OPEN_TIMEOUT)
            await asyncio.sleep(2.5)
            try:
                if await asyncio.wait_for(
                    _page_has_access_challenge(wtab), timeout=EVAL_TIMEOUT
                ):
                    _diagnostic_event(
                        diagnostics,
                        "access_challenge",
                        platform=platform,
                        detail="warmup page login or bot challenge",
                    )
            except Exception as exc:
                if _is_browser_session_error(exc):
                    raise
            try:
                await asyncio.wait_for(wtab.close(), timeout=5)
            except Exception:
                pass
        except Exception as exc:
            if _is_browser_session_error(exc):
                _diagnostic_event(
                    diagnostics,
                    "browser_session_failed",
                    platform=platform,
                    detail=type(exc).__name__,
                )
                return None

    for q in _queries_for_chinese_platform(queries):
        if _time.monotonic() > deadline:
            logger.info("[PlatformSearch] %s: 시간 예산 초과 — 다음 플랫폼으로", platform)
            _diagnostic_event(diagnostics, "time_budget_exceeded", platform=platform)
            return None
        url = tmpl.format(kw=urllib.parse.quote(str(q)))
        logger.info("[PlatformSearch] %s 검색: %s", platform, q)
        # 새 탭 격리: 이전 페이지가 로딩 중 멈춰도(실측: 콰이쇼우) 다음 검색이 막히지 않도록.
        try:
            tab = await asyncio.wait_for(browser.get(url, new_tab=True), timeout=PAGE_OPEN_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("[PlatformSearch] %s 페이지 열기 %.0fs 초과 — 스킵", platform, PAGE_OPEN_TIMEOUT)
            _diagnostic_event(diagnostics, "page_open_timeout", platform=platform)
            continue
        except Exception as e:
            logger.warning("[PlatformSearch] %s 열기 실패: %s", platform, e)
            if _is_browser_session_error(e):
                _diagnostic_event(
                    diagnostics,
                    "browser_session_failed",
                    platform=platform,
                    detail=type(e).__name__,
                )
                return None
            _diagnostic_event(
                diagnostics, "page_open_error", platform=platform,
                detail=type(e).__name__,
            )
            continue
        if tab is None:
            _diagnostic_event(diagnostics, "empty_page", platform=platform)
            continue
        hit = None
        try:
            hit = await _search_query_on_tab(
                browser, tab, platform, q, url, output_dir, page_wait, skip, deadline,
                relevance_references or [], min_relevance_score,
                category_terms or [], tried_source_ids,
                diagnostics=diagnostics,
            )
        except Exception as e:
            # 쿼리 하나가 죽어도 다음 쿼리/플랫폼은 계속 — 전체 소싱을 무너뜨리지 않는다.
            logger.warning("[PlatformSearch] %s 쿼리 처리 오류(계속 진행): %s", platform, str(e)[:140])
            if _is_browser_session_error(e):
                _diagnostic_event(
                    diagnostics,
                    "browser_session_failed",
                    platform=platform,
                    detail=type(e).__name__,
                )
                return None
            _diagnostic_event(
                diagnostics, "query_error", platform=platform,
                detail=type(e).__name__,
            )
        finally:
            try:
                await asyncio.wait_for(tab.close(), timeout=5)
            except Exception:
                pass
        if _has_browser_session_failure(diagnostics):
            return None
        if hit:
            return hit
        if len(tried_source_ids.difference(skip)) >= MAX_PAGE_ATTEMPTS_PER_PLATFORM:
            logger.info(
                "[PlatformSearch] %s: 후보 %d개 점검 완료 — 다음 플랫폼으로",
                platform,
                MAX_PAGE_ATTEMPTS_PER_PLATFORM,
            )
            return None
    return None


async def _search_query_on_tab(
    browser: Any, tab: Any, platform: str, q: str, url: str,
    output_dir: str, page_wait: float, skip: Set[str], deadline: float,
    relevance_references: List[str], min_relevance_score: float,
    category_terms: List[str],
    tried_source_ids: Optional[Set[str]] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """열린 탭에서 챌린지 확인→링크 추출→다운로드까지. 성공 시 hit dict."""
    import time as _time

    if True:
        native_access_blocked = False
        try:
            if await asyncio.wait_for(_page_has_access_challenge(tab), timeout=EVAL_TIMEOUT):
                logger.info(
                    "[PlatformSearch] %s 로그인/차단 화면 — 외부 검색으로 전환",
                    platform,
                )
                _diagnostic_event(
                    diagnostics,
                    "access_challenge",
                    platform=platform,
                    detail="native search login or bot challenge",
                )
                native_access_blocked = True
        except Exception as exc:
            if _is_browser_session_error(exc):
                raise
        # lazy-load 유도
        if not native_access_blocked:
            try:
                await asyncio.sleep(page_wait)
                for _ in range(3):
                    await asyncio.wait_for(
                        tab.evaluate("window.scrollBy(0, document.body.scrollHeight/2)", await_promise=False),
                        timeout=EVAL_TIMEOUT,
                    )
                    await asyncio.sleep(1.2)
                if await asyncio.wait_for(
                    _page_has_access_challenge(tab), timeout=EVAL_TIMEOUT
                ):
                    logger.info(
                        "[PlatformSearch] %s 지연 로그인/차단 화면 — 외부 검색으로 전환",
                        platform,
                    )
                    _diagnostic_event(
                        diagnostics,
                        "access_challenge",
                        platform=platform,
                        detail="challenge appeared after page load",
                    )
                    native_access_blocked = True
            except Exception as exc:
                if _is_browser_session_error(exc):
                    raise

        # ── 전략 1: 영상 페이지 링크 → yt-dlp(브라우저 쿠키 동봉) ──
        if platform in _YTDLP_PLATFORMS:
            page_links = [] if native_access_blocked else await _extract_video_page_links(
                tab, platform, output_dir, q, diagnostics=diagnostics
            )
            logger.info("[PlatformSearch] %s: 영상 페이지 링크 %d개", platform, len(page_links))
            # Native result pages frequently expose only one stale/deleted
            # result to a logged-out session.  Merge external indexed results
            # until we have enough unique candidates instead of treating one
            # unusable URL as a complete search.
            if len(page_links) < 4:
                external_links = await _external_search_links(
                    browser, platform, q, output_dir, diagnostics=diagnostics
                )
                seen_links = {_normalize_source_id(link) for link in page_links}
                for link in external_links:
                    source_id = _normalize_source_id(link)
                    if source_id and source_id not in seen_links:
                        seen_links.add(source_id)
                        page_links.append(link)
            attempted = tried_source_ids if tried_source_ids is not None else set(skip)
            fresh_links = _take_fresh_page_links(page_links, attempted, skip)
            if len(page_links) != len(fresh_links):
                logger.info("[PlatformSearch] %s: 이미 사용/시도한 영상 %d개 스킵",
                            platform, len(page_links) - len(fresh_links))
                _diagnostic_event(
                    diagnostics, "duplicate_source",
                    platform=platform,
                    detail=str(len(page_links) - len(fresh_links)),
                )
            if not page_links:
                _diagnostic_event(
                    diagnostics, "no_results", platform=platform, detail=q
                )
            ytdlp_cookies = (
                await _browser_cookies_for(
                    browser, platform, diagnostics=diagnostics
                )
                if fresh_links
                else {}
            )
            # Spread the finite platform budget across exact and family-alias
            # queries. Four stale links from the first over-specific query used
            # to starve simpler native phrases such as 手持挂烫机.
            for link in fresh_links:
                if _time.monotonic() > deadline:
                    logger.info("[PlatformSearch] %s: 시간 예산 초과(yt-dlp 단계)", platform)
                    _diagnostic_event(diagnostics, "time_budget_exceeded", platform=platform)
                    return None
                try:
                    got = await asyncio.wait_for(
                        asyncio.to_thread(
                            _ytdlp_download,
                            link,
                            output_dir,
                            ytdlp_cookies,
                            relevance_references,
                            min_relevance_score,
                            category_terms,
                        ),
                        timeout=240,
                    )
                except asyncio.TimeoutError:
                    logger.warning("[PlatformSearch] %s yt-dlp 240s 초과: %s", platform, link[:60])
                    _diagnostic_event(
                        diagnostics,
                        "download_timeout",
                        platform=platform,
                        detail=_normalize_source_id(link),
                    )
                    got = None
                if got and (
                    got.get("relevance_rejected") or got.get("technical_rejected")
                ):
                    _diagnostic_event(
                        diagnostics,
                        "relevance_rejected" if got.get("relevance_rejected") else "technical_rejected",
                        platform=platform,
                        detail=_normalize_source_id(link),
                    )
                    continue
                if not got and platform == "bilibili":
                    # 412 리스크컨트롤 폴백: 브라우저 컨텍스트에서 직접 스트림 다운로드.
                    got = await _bilibili_browser_download(browser, link, output_dir)
                elif not got:
                    # 도우인('Fresh cookies')·콰이쇼우 폴백: 영상 페이지는 비로그인
                    # 시청 가능 — 페이지를 열어 mp4를 직접 추출·다운로드.
                    got = await _browser_page_video_download(
                        browser,
                        link,
                        platform,
                        output_dir,
                        diagnostics=diagnostics,
                    )
                if not got:
                    _diagnostic_event(
                        diagnostics,
                        "download_failed",
                        platform=platform,
                        detail=_normalize_source_id(link),
                    )
                    continue
                ok, why = validate_source_video(got["local_path"])
                if not ok:
                    logger.info("[PlatformSearch] %s 후보 탈락(%s): %s", platform, why, link[:60])
                    try:
                        os.remove(got["local_path"])
                    except OSError:
                        pass
                    _diagnostic_event(
                        diagnostics, "technical_rejected", platform=platform,
                        detail=f"{_normalize_source_id(link)}: {why}",
                    )
                    continue
                size_mb = os.path.getsize(got["local_path"]) / (1024 * 1024)
                via = str(got.get("via") or "yt-dlp")
                evidence = str(got.get("title") or "").strip()
                relevant, relevance_score = _relevance_result(
                    evidence,
                    relevance_references,
                    min_relevance_score,
                    category_terms,
                )
                if not relevant:
                    logger.warning(
                        "[PlatformSearch] 상품 연관성 미달/알 수 없음 score=%s title=%r",
                        relevance_score,
                        evidence[:80],
                    )
                    try:
                        os.remove(got["local_path"])
                    except OSError:
                        pass
                    _diagnostic_event(
                        diagnostics,
                        "relevance_rejected",
                        platform=platform,
                        detail=(
                            f"{_normalize_source_id(link)}: score={relevance_score}"
                        ),
                    )
                    continue
                logger.info("[PlatformSearch] %s %s 성공 %.1fMB: %s", platform, via, size_mb, link[:60])
                return {
                    "platform": platform, "query": q, "video_url": link,
                    "video_file": got["local_path"], "size_mb": round(size_mb, 1),
                    "via": via, "title": evidence,
                    "relevance_score": relevance_score,
                    "relevance_evidence": "candidate_title",
                }

        # ── 전략 2(폴백): 직접 mp4 추출 → requests 다운로드 ──
        if native_access_blocked:
            return None
        video_urls = await _extract_platform_videos(
            tab, diagnostics=diagnostics, platform=platform
        )
        video_urls = [u for u in video_urls if _normalize_source_id(u) not in skip]
        if not video_urls:
            logger.info("[PlatformSearch] %s: 영상 URL 못 찾음", platform)
            _diagnostic_event(
                diagnostics, "no_video_url", platform=platform, detail=q
            )
            return None

        referer = _REFERER.get(platform, url)
        for vurl in video_urls[:5]:
            if _time.monotonic() > deadline:
                logger.info("[PlatformSearch] %s: 시간 예산 초과(직접 다운로드 단계)", platform)
                _diagnostic_event(diagnostics, "time_budget_exceeded", platform=platform)
                return None
            filepath = os.path.join(output_dir, f"platform_{platform}_{uuid.uuid4().hex[:8]}.mp4")
            session_cookies = await _browser_cookies_for(
                browser, platform, vurl, diagnostics=diagnostics
            )
            try:
                size = await asyncio.wait_for(
                    asyncio.to_thread(
                        _download_video, vurl, filepath, referer, cookies=session_cookies
                    ),
                    timeout=180,
                )
            except asyncio.TimeoutError:
                _diagnostic_event(
                    diagnostics,
                    "download_timeout",
                    platform=platform,
                    detail=_normalize_source_id(vurl),
                )
                size = None
            if not size:
                _diagnostic_event(
                    diagnostics,
                    "download_failed",
                    platform=platform,
                    detail=_normalize_source_id(vurl),
                )
                continue
            ok, why = validate_source_video(filepath)
            if not ok:
                logger.info("[PlatformSearch] %s 후보 탈락(%s)", platform, why)
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                _diagnostic_event(
                    diagnostics, "technical_rejected", platform=platform,
                    detail=why,
                )
                continue
            # Direct media URLs do not carry candidate-owned title/caption
            # evidence.  Treat them as unknown instead of trusting the search
            # query that happened to reveal the URL.
            logger.warning("[PlatformSearch] 후보 메타데이터 없음 — 자동 게시 안전 게이트로 차단")
            try:
                os.remove(filepath)
            except OSError:
                pass
            _diagnostic_event(
                diagnostics,
                "missing_candidate_metadata",
                platform=platform,
                detail=_normalize_source_id(vurl),
            )
            continue
    return None


async def search_platform_shorts(
    browser: Any, queries: List[str], output_dir: str,
    platforms: Optional[List[str]] = None,
    skip_source_ids: Optional[Set[str]] = None,
    relevance_references: Optional[List[str]] = None,
    min_relevance_score: float = 0.9,
    category_terms: Optional[List[str]] = None,
    prefer_best: bool = True,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Return the strongest relevance-safe candidate across enabled platforms.

    Every platform still searches in deterministic priority order.  When
    ``prefer_best`` is true (the full-automation default), one safe candidate
    per platform is compared instead of allowing an early 0.90 hit to hide a
    later exact match.  Downloaded non-selected candidates are removed.
    """
    requested = platforms or DEFAULT_PLATFORM_ORDER
    active_platforms = list(dict.fromkeys(
        str(platform or "").strip().lower()
        for platform in requested
        if str(platform or "").strip().lower() in SUPPORTED_COMMERCE_PLATFORMS
    )) or list(DEFAULT_PLATFORM_ORDER)
    if diagnostics is not None:
        diagnostics["requested_platforms"] = list(active_platforms)

    safe_hits: List[Dict[str, Any]] = []
    for platform in active_platforms:
        hit = await search_one_platform(
            browser,
            platform,
            queries,
            output_dir,
            skip_source_ids=skip_source_ids,
            relevance_references=relevance_references,
            min_relevance_score=min_relevance_score,
            category_terms=category_terms,
            diagnostics=diagnostics,
        )
        if _has_browser_session_failure(diagnostics):
            break
        if hit:
            _diagnostic_event(diagnostics, "success", platform=platform)
            if not prefer_best:
                return hit
            safe_hits.append(hit)
            # No later candidate can exceed an exact score.
            if float(hit.get("relevance_score") or 0.0) >= 1.0:
                break
    if not safe_hits:
        return None

    selected = max(
        enumerate(safe_hits),
        key=lambda pair: (float(pair[1].get("relevance_score") or 0.0), -pair[0]),
    )[1]
    selected_path = os.path.abspath(str(selected.get("video_file") or ""))
    for candidate in safe_hits:
        candidate_path = str(candidate.get("video_file") or "")
        if not candidate_path:
            continue
        if os.path.abspath(candidate_path) == selected_path:
            continue
        try:
            os.remove(candidate_path)
        except OSError:
            pass
    return selected


async def collect_by_keyword(
    queries: List[str], output_dir: str, platforms: Optional[List[str]] = None,
    browser: Any = None,
    skip_source_ids: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """브라우저 관리 포함 편의 진입점. browser 미제공 시 직접 시작/종료."""
    own = False
    if browser is None:
        browser = await start_browser()
        own = True
    try:
        return await search_platform_shorts(
            browser,
            queries,
            output_dir,
            platforms,
            skip_source_ids=skip_source_ids,
            relevance_references=list(queries),
        )
    finally:
        if own:
            try:
                await browser.stop()
            except Exception:
                pass
