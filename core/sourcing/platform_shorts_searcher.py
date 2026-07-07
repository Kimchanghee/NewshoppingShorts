# -*- coding: utf-8 -*-
"""
3플랫폼(도우인/콰이쇼우/샤오홍슈) 키워드 영상 검색기.

기존 AliExpress/1688 소싱과 동일 패턴(zendriver + _extract_video_urls + _download_video)을
재사용해서, 상품명 키워드로 세 채널을 '순서대로' 검색하고 먼저 영상이 나오는 곳에서
다운로드한다(first-hit-wins).

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
    _page_has_access_challenge,
)

logger = get_logger(__name__)

# 순서 = 우선순위(먼저 나오는 곳 사용).
# bilibili: 검색이 비로그인 개방 + yt-dlp 완전 지원 → 로그인 없이도 성공하는 최종 폴백.
DEFAULT_PLATFORM_ORDER = ["douyin", "kuaishou", "xiaohongshu", "bilibili"]

# 검증 기준(쇼츠 소스로 쓸 수 있는 영상).
MIN_SOURCE_SECONDS = 4.0
MAX_SOURCE_SECONDS = 90.0
MIN_SOURCE_SHORT_SIDE = 480

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
_YTDLP_PLATFORMS = {"douyin", "kuaishou", "bilibili"}

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
# DuckDuckGo(html 버전, JS 불필요·봇 관대)에 site: 필터로 위임하고,
# 다운로드는 기존 yt-dlp+쿠키 경로를 그대로 쓴다.
_EXTERNAL_SITE_FILTER = {
    "douyin": "douyin.com/video",
    "kuaishou": "kuaishou.com/short-video",
    "bilibili": "bilibili.com/video",
}


async def _external_search_links(
    browser: Any, platform: str, query: str, output_dir: str = ""
) -> List[str]:
    """DuckDuckGo html 검색으로 플랫폼 영상 페이지 링크 수집(비로그인 폴백)."""
    site = _EXTERNAL_SITE_FILTER.get(platform)
    if not site:
        return []
    q = urllib.parse.quote(f"{query} site:{site}")
    url = f"https://html.duckduckgo.com/html/?q={q}"
    try:
        tab = await asyncio.wait_for(browser.get(url, new_tab=True), timeout=PAGE_OPEN_TIMEOUT)
    except Exception:
        return []
    if tab is None:
        return []
    try:
        await asyncio.sleep(2.5)
        links = await _extract_video_page_links(tab, platform, output_dir, f"ddg:{query}")
        if links:
            logger.info("[PlatformSearch] %s: 외부검색(DDG) 링크 %d개", platform, len(links))
        return links
    finally:
        try:
            await asyncio.wait_for(tab.close(), timeout=5)
        except Exception:
            pass

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
            return {}
        out: Dict[str, float] = {}
        for line in (r.stdout or "").splitlines():
            k, _, v = line.partition("=")
            try:
                out[k.strip()] = float(v.strip())
            except ValueError:
                continue
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
                zd.start(user_data_dir=profile, headless=False),
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


async def _extract_platform_videos(tab: Any) -> List[str]:
    """제네릭 추출 + 플랫폼 CDN 보강."""
    urls: List[str] = []
    try:
        urls = list(await asyncio.wait_for(_extract_video_urls(tab), timeout=EVAL_TIMEOUT * 2) or [])
    except Exception:
        urls = []
    try:
        extra = await asyncio.wait_for(
            tab.evaluate(_PLATFORM_MP4_JS, await_promise=False), timeout=EVAL_TIMEOUT
        )
        if isinstance(extra, list):
            for u in extra:
                if isinstance(u, str) and u.startswith("http") and u not in urls:
                    urls.append(u)
    except Exception:
        pass
    return [u for u in urls if u.startswith("http")]


async def _browser_cookies_for(browser: Any, platform: str) -> Dict[str, str]:
    """자동화 브라우저의 플랫폼 도메인 쿠키(dict) — 서명 CDN 다운로드 성공률용."""
    keyword = {"douyin": "douyin", "kuaishou": "kuaishou", "xiaohongshu": "xiaohongshu"}.get(platform, platform)
    out: Dict[str, str] = {}
    try:
        cookies = await asyncio.wait_for(browser.cookies.get_all(), timeout=EVAL_TIMEOUT)
        for c in cookies or []:
            try:
                domain = str(getattr(c, "domain", "") or "")
                if keyword in domain:
                    out[str(getattr(c, "name", ""))] = str(getattr(c, "value", ""))
            except Exception:
                continue
    except Exception:
        pass
    return out


async def _extract_video_page_links(
    tab: Any, platform: str, output_dir: str = "", query: str = ""
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
    except Exception:
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
        except Exception:
            pass

    seen, links = set(), []
    for m in pat.finditer(html):
        path_part = m.group(1)
        vid = m.group(2)
        if vid in seen:
            continue
        seen.add(vid)
        links.append(_PAGE_LINK_BASE[platform] + path_part)
    # SSR 스토어 ID 보강
    tmpl = _ID_LINK_TEMPLATE.get(platform)
    for idpat in _ID_PATTERNS.get(platform, []):
        for m in idpat.finditer(html):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            links.append(tmpl.format(id=vid))
    return links


def _ytdlp_download(page_url: str, output_dir: str,
                    cookies: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
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
            return None

        cv = collector.collect_one(page_url, download=True, cookies=cookies)
        if cv.ok and cv.local_path and os.path.exists(cv.local_path):
            return {
                "local_path": cv.local_path,
                "duration": cv.duration,
                "title": cv.title,
                "width": cv.width,
                "height": cv.height,
            }
        if cv.error:
            logger.info("[PlatformSearch] yt-dlp 수집 실패(%s): %s", page_url[:60], cv.error[:160])
    except Exception as e:
        logger.info("[PlatformSearch] yt-dlp 실패(%s): %s", page_url[:60], str(e)[:160])
    return None


# 페이지 열기/스크립트 평가가 무한 대기하지 않도록 하는 타임아웃(초).
PAGE_OPEN_TIMEOUT = 40.0
EVAL_TIMEOUT = 15.0
# 플랫폼 1곳당 시간 예산(초) — 초과 시 다음 플랫폼으로.
PER_PLATFORM_BUDGET = 240.0


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
    browser: Any, link: str, platform: str, output_dir: str
) -> Optional[Dict[str, Any]]:
    """범용 브라우저 컨텍스트 다운로드 — yt-dlp가 막힐 때(도우인 'Fresh cookies' 등).

    영상 '페이지'는 비로그인 시청이 가능하므로, 페이지를 탭으로 열어 RENDER_DATA/
    playAddr에서 mp4 URL을 뽑고 세션 쿠키로 직접 받는다(빌리빌리 412 대응과 동일 패턴).
    """
    try:
        tab = await asyncio.wait_for(browser.get(link, new_tab=True), timeout=PAGE_OPEN_TIMEOUT)
    except Exception:
        return None
    if tab is None:
        return None
    try:
        await asyncio.sleep(3.0)
        urls: List[str] = []
        for _ in range(3):
            urls = await _extract_platform_videos(tab)
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
        except Exception:
            pass
        cookies = await _browser_cookies_for(browser, platform)
        for vurl in urls[:3]:
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

        cookies = await _browser_cookies_for(browser, "bilibili")
        referer = link
        tag = uuid.uuid4().hex[:8]

        dash = data.get("dash") or {}
        videos = dash.get("video") or []
        if videos:
            vurl = videos[0].get("baseUrl") or videos[0].get("base_url") or ""
            audios = dash.get("audio") or []
            aurl = (audios[0].get("baseUrl") or audios[0].get("base_url") or "") if audios else ""
            vpath = os.path.join(output_dir, f"bili_{tag}_v.m4s")
            vsize = await asyncio.wait_for(
                asyncio.to_thread(_download_video, vurl, vpath, referer, cookies=cookies),
                timeout=180,
            ) if vurl else None
            if not vsize:
                return None
            apath = ""
            if aurl:
                apath = os.path.join(output_dir, f"bili_{tag}_a.m4s")
                asize = await asyncio.wait_for(
                    asyncio.to_thread(_download_video, aurl, apath, referer, cookies=cookies),
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
            size = await asyncio.wait_for(
                asyncio.to_thread(_download_video, u, path, referer, cookies=cookies),
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
) -> Optional[Dict[str, Any]]:
    """단일 플랫폼에서 쿼리들로 검색, 첫 '검증 통과' 영상 반환."""
    import time as _time

    tmpl = _SEARCH_URL.get(platform)
    if not tmpl:
        return None
    os.makedirs(output_dir, exist_ok=True)
    skip = skip_source_ids or set()
    deadline = _time.monotonic() + max(30.0, float(budget_seconds))

    # 홈 워밍업: 기본 쿠키(ttwid/did 등)를 먼저 심어 비로그인 검색 렌더 성공률을 올린다.
    warmup = _WARMUP_URL.get(platform)
    if warmup:
        try:
            wtab = await asyncio.wait_for(browser.get(warmup, new_tab=True), timeout=PAGE_OPEN_TIMEOUT)
            await asyncio.sleep(2.5)
            try:
                await asyncio.wait_for(wtab.close(), timeout=5)
            except Exception:
                pass
        except Exception:
            pass

    for q in [x for x in queries if str(x or "").strip()]:
        if _time.monotonic() > deadline:
            logger.info("[PlatformSearch] %s: 시간 예산 초과 — 다음 플랫폼으로", platform)
            return None
        url = tmpl.format(kw=urllib.parse.quote(str(q)))
        logger.info("[PlatformSearch] %s 검색: %s", platform, q)
        # 새 탭 격리: 이전 페이지가 로딩 중 멈춰도(실측: 콰이쇼우) 다음 검색이 막히지 않도록.
        try:
            tab = await asyncio.wait_for(browser.get(url, new_tab=True), timeout=PAGE_OPEN_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("[PlatformSearch] %s 페이지 열기 %.0fs 초과 — 스킵", platform, PAGE_OPEN_TIMEOUT)
            continue
        except Exception as e:
            logger.warning("[PlatformSearch] %s 열기 실패: %s", platform, e)
            continue
        if tab is None:
            continue
        hit = None
        try:
            hit = await _search_query_on_tab(
                browser, tab, platform, q, url, output_dir, page_wait, skip, deadline
            )
        except Exception as e:
            # 쿼리 하나가 죽어도 다음 쿼리/플랫폼은 계속 — 전체 소싱을 무너뜨리지 않는다.
            logger.warning("[PlatformSearch] %s 쿼리 처리 오류(계속 진행): %s", platform, str(e)[:140])
        finally:
            try:
                await asyncio.wait_for(tab.close(), timeout=5)
            except Exception:
                pass
        if hit:
            return hit
    return None


async def _search_query_on_tab(
    browser: Any, tab: Any, platform: str, q: str, url: str,
    output_dir: str, page_wait: float, skip: Set[str], deadline: float,
) -> Optional[Dict[str, Any]]:
    """열린 탭에서 챌린지 확인→링크 추출→다운로드까지. 성공 시 hit dict."""
    import time as _time

    if True:
        try:
            if await asyncio.wait_for(_page_has_access_challenge(tab), timeout=EVAL_TIMEOUT):
                logger.info("[PlatformSearch] %s 로그인/차단 화면 — 스킵(프로필 로그인 필요)", platform)
                return None
        except Exception:
            pass
        # lazy-load 유도
        try:
            await asyncio.sleep(page_wait)
            for _ in range(3):
                await asyncio.wait_for(
                    tab.evaluate("window.scrollBy(0, document.body.scrollHeight/2)", await_promise=False),
                    timeout=EVAL_TIMEOUT,
                )
                await asyncio.sleep(1.2)
        except Exception:
            pass

        # ── 전략 1: 영상 페이지 링크 → yt-dlp(브라우저 쿠키 동봉) ──
        if platform in _YTDLP_PLATFORMS:
            page_links = await _extract_video_page_links(tab, platform, output_dir, q)
            logger.info("[PlatformSearch] %s: 영상 페이지 링크 %d개", platform, len(page_links))
            if not page_links:
                # 플랫폼 자체 검색이 게이트일 때: 외부 검색엔진으로 영상 페이지를 찾는다.
                page_links = await _external_search_links(browser, platform, q, output_dir)
            fresh_links = [l for l in page_links if _normalize_source_id(l) not in skip]
            if len(page_links) != len(fresh_links):
                logger.info("[PlatformSearch] %s: 이미 사용한 영상 %d개 스킵",
                            platform, len(page_links) - len(fresh_links))
            ytdlp_cookies = (
                await _browser_cookies_for(browser, platform) if fresh_links else {}
            )
            for link in fresh_links[:4]:
                if _time.monotonic() > deadline:
                    logger.info("[PlatformSearch] %s: 시간 예산 초과(yt-dlp 단계)", platform)
                    return None
                try:
                    got = await asyncio.wait_for(
                        asyncio.to_thread(_ytdlp_download, link, output_dir, ytdlp_cookies),
                        timeout=240,
                    )
                except asyncio.TimeoutError:
                    logger.warning("[PlatformSearch] %s yt-dlp 240s 초과: %s", platform, link[:60])
                    got = None
                if not got and platform == "bilibili":
                    # 412 리스크컨트롤 폴백: 브라우저 컨텍스트에서 직접 스트림 다운로드.
                    got = await _bilibili_browser_download(browser, link, output_dir)
                elif not got:
                    # 도우인('Fresh cookies')·콰이쇼우 폴백: 영상 페이지는 비로그인
                    # 시청 가능 — 페이지를 열어 mp4를 직접 추출·다운로드.
                    got = await _browser_page_video_download(browser, link, platform, output_dir)
                if not got:
                    continue
                ok, why = validate_source_video(got["local_path"])
                if not ok:
                    logger.info("[PlatformSearch] %s 후보 탈락(%s): %s", platform, why, link[:60])
                    try:
                        os.remove(got["local_path"])
                    except OSError:
                        pass
                    continue
                size_mb = os.path.getsize(got["local_path"]) / (1024 * 1024)
                via = str(got.get("via") or "yt-dlp")
                logger.info("[PlatformSearch] %s %s 성공 %.1fMB: %s", platform, via, size_mb, link[:60])
                return {
                    "platform": platform, "query": q, "video_url": link,
                    "video_file": got["local_path"], "size_mb": round(size_mb, 1),
                    "via": via, "title": got.get("title", ""),
                }

        # ── 전략 2(폴백): 직접 mp4 추출 → requests 다운로드 ──
        video_urls = await _extract_platform_videos(tab)
        video_urls = [u for u in video_urls if _normalize_source_id(u) not in skip]
        if not video_urls:
            logger.info("[PlatformSearch] %s: 영상 URL 못 찾음", platform)
            return None

        referer = _REFERER.get(platform, url)
        session_cookies = await _browser_cookies_for(browser, platform)
        for vurl in video_urls[:5]:
            if _time.monotonic() > deadline:
                logger.info("[PlatformSearch] %s: 시간 예산 초과(직접 다운로드 단계)", platform)
                return None
            filepath = os.path.join(output_dir, f"platform_{platform}_{uuid.uuid4().hex[:8]}.mp4")
            try:
                size = await asyncio.wait_for(
                    asyncio.to_thread(
                        _download_video, vurl, filepath, referer, cookies=session_cookies
                    ),
                    timeout=180,
                )
            except asyncio.TimeoutError:
                size = None
            if not size:
                continue
            ok, why = validate_source_video(filepath)
            if not ok:
                logger.info("[PlatformSearch] %s 후보 탈락(%s)", platform, why)
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                continue
            logger.info("[PlatformSearch] %s 다운로드 성공 %.1fMB", platform, size)
            return {
                "platform": platform, "query": q, "video_url": vurl,
                "video_file": filepath, "size_mb": size, "via": "direct",
            }
    return None


async def search_platform_shorts(
    browser: Any, queries: List[str], output_dir: str,
    platforms: Optional[List[str]] = None,
    skip_source_ids: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """플랫폼을 순서대로 시도, 먼저 성공하는 곳의 영상 반환(first-hit-wins)."""
    for platform in (platforms or DEFAULT_PLATFORM_ORDER):
        hit = await search_one_platform(
            browser, platform, queries, output_dir, skip_source_ids=skip_source_ids
        )
        if hit:
            return hit
    return None


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
            browser, queries, output_dir, platforms, skip_source_ids=skip_source_ids
        )
    finally:
        if own:
            try:
                await browser.stop()
            except Exception:
                pass
