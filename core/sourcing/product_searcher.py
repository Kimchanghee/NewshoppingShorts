"""
AliExpress / 1688 product searcher using zendriver (CDP).
Searches by keyword, finds products with videos, downloads them.
"""
from __future__ import annotations

import asyncio
import os
import re
import uuid
from typing import Any, Dict, List, Optional

import requests

from utils.logging_config import get_logger

logger = get_logger(__name__)


# Tokens that inflate Jaccard similarity without identifying the product family.
# Filtered out before scoring so generic words like "set", "1pc", "kitchen" don't
# match a phone stand to a sponge holder just because both say "for kitchen use".
_STOPWORD_TOKENS = {
    # English packaging / commerce noise
    "set", "kit", "pack", "pcs", "pc", "1pc", "2pc", "3pc", "4pc", "5pc",
    "1ea", "2ea", "ea", "lot", "lots", "piece", "pieces", "pair", "pairs",
    "for", "with", "and", "the", "of", "a", "an", "to", "in", "on", "by",
    "new", "hot", "best", "top", "high", "premium", "quality", "free",
    "shipping", "fast", "ship", "wholesale", "drop", "dropship", "color",
    "size", "small", "medium", "large", "mini", "max", "pro", "plus",
    "design", "style", "type", "model", "edition", "version",
    # Korean packaging / commerce noise
    "세트", "묶음", "개입", "구성", "구입", "추천", "정품", "특가", "할인",
    # Chinese commerce noise (single chars common across categories)
    "套", "件", "新", "款", "热", "卖", "包", "邮", "装", "组",
    # Pure numbers small enough to be quantities
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
}

# Descriptive modifiers that frequently hurt search recall when used as head
# terms (e.g. "triangle sink" retrieves basin fixtures instead of strainers).
_HEAD_NOISE_TOKENS = {
    "triangle", "triangular", "round", "square", "magnetic",
    "stainless", "steel", "kitchen", "bathroom", "household",
    "small", "large", "mini",
}

# Product-family anchors used to prioritize semantically important tokens over
# shape/color/material descriptors in head-noun search queries.
_HEAD_ANCHOR_PARTS = (
    "strainer", "filter", "drain", "basket", "holder", "rack", "sink",
    "sponge", "garbage", "waste",
    "거름망", "싱크", "배수", "필터", "걸이", "수세미",
    "水槽", "过滤", "沥水", "挂架",
)


# Korean / English / Chinese synonym groups. The tokenizer rewrites every member
# of a group to a canonical form so `수세미`, `스폰지`, `스펀지` all become the same
# token — the single biggest win for cross-vendor matching since AliExpress's
# Korean translation of Chinese product titles routinely uses different
# loanword spellings than the Coupang seller does.
#
# Format: each tuple is (canonical, *aliases). Canonical is what every alias
# rewrites to. The first member of every tuple is the canonical.
_SYNONYM_GROUPS: list[tuple[str, ...]] = [
    # Sponge / scrubber
    ("수세미", "스폰지", "스펀지", "수세이"),
    # Holder / stand / mount / cradle
    ("거치대", "홀더", "스탠드", "받침대", "받침", "스텐드"),
    # Hook
    ("후크", "걸이", "훅", "행거"),
    # Container / box
    ("용기", "통", "케이스", "박스", "함", "박스형", "보관함"),
    # Bag / pouch
    ("가방", "백", "파우치", "주머니"),
    # Knife
    ("칼", "나이프"),
    # Scissors / shears
    ("가위", "쉐어"),
    # Cutting board
    ("도마", "커팅보드", "촙핑보드"),
    # Pot / pan
    ("냄비", "팟", "포트"),
    ("팬", "후라이팬", "프라이팬", "프라이"),
    # Bottle
    ("병", "보틀", "바틀"),
    # Cup / mug / tumbler
    ("컵", "머그", "텀블러", "텀블"),
    # Filter / strainer
    ("거름망", "스트레이너", "필터"),
    # Tray
    ("트레이", "쟁반"),
    # Mat / pad
    ("매트", "패드"),
    # Charger
    ("충전기", "차저"),
    # Cable
    ("케이블", "선", "코드", "와이어"),
    # Phone (digital)
    ("휴대폰", "핸드폰", "스마트폰", "폰"),
    # Earphone / headphone
    ("이어폰", "에어팟", "이어버드"),
    ("헤드폰", "헤드셋"),
    # Mask / pad (beauty)
    ("마스크팩", "팩", "시트마스크"),
    # Cushion / pillow
    ("쿠션", "베개", "쿠숀"),
    # Slippers / sandals
    ("슬리퍼", "쪼리", "샌들"),
]


# Build {alias -> canonical} map at import time
_SYNONYM_REWRITE: dict[str, str] = {}
for _group in _SYNONYM_GROUPS:
    canonical = _group[0]
    for alias in _group:
        _SYNONYM_REWRITE[alias] = canonical


def _normalize_synonyms(token: str) -> str:
    """Return canonical form for synonym tokens (수세미 ↔ 스폰지 ↔ 스펀지)."""
    return _SYNONYM_REWRITE.get(token, token)


def _tokenize(s: str):
    """Tokenize a product title into Jaccard tokens.

    - lowercases
    - splits CJK / Hangul / Latin / digits
    - explodes Chinese strings into per-character tokens too (so "海绵架"
      contributes 海, 绵, 架 individually for cross-vendor matching)
    - rewrites synonyms to canonical form (수세미 ↔ 스폰지)
    - drops generic stopwords that inflate scores without meaning
    """
    if not s:
        return set()
    s = s.lower()
    tokens = set(re.findall(r'[\u4e00-\u9fff]+|[\uac00-\ud7af]+|[a-z]+|\d+', s))
    chars = set()
    bigrams = set()
    for t in list(tokens):
        if re.match(r'[\u4e00-\u9fff]', t):
            chars.update(t)
            # Adjacent-character bigrams are far more discriminative than single
            # CJK chars: a phone stand (\u624b\u673a\u652f\u67b6) and a sponge rack (\u6d77\u7ef5\u67b6) both
            # contain \u67b6, but share no bigram \u2014 so bigrams curb common-character
            # similarity inflation while still rewarding genuine overlap. Single
            # chars are kept too, so cross-vendor partial matches still register.
            for i in range(len(t) - 1):
                bigrams.add(t[i:i + 2])
    tokens.update(chars)
    tokens.update(bigrams)
    # Rewrite Korean synonyms to canonical, then drop noise.
    normalized = {_normalize_synonyms(t) for t in tokens}
    return {t for t in normalized if t not in _STOPWORD_TOKENS}


def _similarity_score(name1: str, name2: str) -> float:
    """Token-based Jaccard similarity supporting CJK + Latin, with stopword filter."""
    if not name1 or not name2:
        return 0.0
    t1, t2 = _tokenize(name1), _tokenize(name2)
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def _multi_reference_score(
    candidate_title: str,
    references: List[str],
) -> float:
    """Best similarity of candidate title against several reference strings.

    Cross-language matching: a 1688 candidate titled "海绵架 厨房水池沥水架" should
    score against ALL of {Korean original title, Chinese keyword, English keyword}
    and we take the max — this lifts cross-vendor accuracy because no single
    reference language overlaps every candidate language.
    """
    return max((_similarity_score(candidate_title, r) for r in references if r), default=0.0)


async def _extract_video_urls(tab: Any) -> List[str]:
    """Extract video URLs from a product detail page.

    AliExpress and 1688 store video URLs in MANY different places depending on
    the product, page version, and lazy-load state. This function probes every
    known location:

    1. Native <video> elements (rare on these sites)
    2. <source> elements inside <video>
    3. data-* attributes (data-video-url, data-src, data-poster-video, ...)
    4. Inline JSON in script tags (window.runParams, __INIT_DATA__, etc.)
    5. Regex over the full document HTML for known CDN patterns
    6. Schema.org VideoObject in <script type="application/ld+json">
    7. Any element with class containing "video" that has a src/data-src
    8. JS variable patterns like videoPath, videoUrl, playUrl, mp4Url

    Returns up to 15 candidate URLs (de-duplicated).
    """
    return await tab.evaluate("""
        (() => {
            const urls = new Set();
            const add = (u) => {
                if (!u || typeof u !== 'string') return;
                u = u.replace(/\\\\u002F/g, '/').replace(/\\\\\\//g, '/');
                if (u.startsWith('//')) u = 'https:' + u;
                if (!u.startsWith('http')) return;
                // Filter clearly non-video URLs
                if (/\\.(jpg|jpeg|png|gif|webp|svg|ico|css|js)(\\?|$)/i.test(u)) return;
                urls.add(u);
            };

            // 1. <video> elements + <source>
            document.querySelectorAll('video').forEach(v => {
                add(v.src); add(v.currentSrc);
                v.querySelectorAll('source').forEach(s => add(s.src));
            });

            // 2. data-* attributes commonly used for lazy-load
            ['data-video-url','data-video','data-src','data-poster-video',
             'data-mp4','data-url-video','data-videourl','data-videosrc'].forEach(attr => {
                document.querySelectorAll('['+attr+']').forEach(el => add(el.getAttribute(attr)));
            });

            // 3. AliExpress runParams / 1688 detailData / Tao detail JSON
            try {
                if (window.runParams && window.runParams.data) {
                    const d = window.runParams.data;
                    const probe = (o) => {
                        if (!o || typeof o !== 'object') return;
                        for (const k in o) {
                            const v = o[k];
                            if (typeof v === 'string' && /\\.(mp4|m3u8|webm)/i.test(v)) add(v);
                            else if (typeof v === 'object') probe(v);
                        }
                    };
                    probe(d);
                }
                if (window.detailData) {
                    if (window.detailData.videoUrl) add(window.detailData.videoUrl);
                    if (window.detailData.video && window.detailData.video.url) add(window.detailData.video.url);
                }
                if (window.__INIT_DATA__) {
                    const probe = (o) => {
                        if (!o || typeof o !== 'object') return;
                        for (const k in o) {
                            const v = o[k];
                            if (typeof v === 'string' && /\\.(mp4|m3u8|webm)/i.test(v)) add(v);
                            else if (typeof v === 'object') probe(v);
                        }
                    };
                    probe(window.__INIT_DATA__);
                }
            } catch(e) {}

            // 4. Regex sweep over full HTML (catches inline JSON we couldn't reach).
            // We also un-escape common JSON encodings (\\\" → \", \\u002F → /,
            // \\/ → /, &amp; → &) so URLs that were stored as JSON-escaped
            // strings inside <script> tags get matched by the patterns below.
            const rawHtml = document.documentElement.innerHTML;
            const html = rawHtml
                .replace(/\\\\u002F/g, '/')
                .replace(/\\\\\\//g, '/')
                .replace(/\\\\&/g, '&')
                .replace(/&amp;/g, '&');
            const patterns = [
                /"(https?:\\/\\/[^"\\\\]*?\\.mp4[^"\\\\]*?)"/g,
                /"(https?:\\/\\/[^"\\\\]*?\\.m3u8[^"\\\\]*?)"/g,
                /"(https?:\\/\\/[^"\\\\]*?\\.webm[^"\\\\]*?)"/g,
                /"videoUrl"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"videoPath"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"video_url"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"videoUri"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"videoSrc"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"playUrl"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"playUrl"\\s*:\\s*"([^"]+)"/g,    // Some pages give relative path
                /"playerUrl"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"mp4Url"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"contentUrl"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /(https?:\\/\\/cloud\\.video\\.taobao\\.com[^\\s"'\\\\<>]+)/g,
                /(https?:\\/\\/[a-z0-9.-]*alicdn\\.com[^\\s"'\\\\<>]*?\\.mp4[^\\s"'\\\\<>]*)/g,
                /(https?:\\/\\/[a-z0-9.-]*\\.tbcdn\\.cn[^\\s"'\\\\<>]*?\\.mp4[^\\s"'\\\\<>]*)/g,
                /(https?:\\/\\/v\\.alicdn\\.com[^\\s"'\\\\<>]+)/g,
                /(https?:\\/\\/[a-z0-9.-]*1688\\.com[^\\s"'\\\\<>]*?\\.mp4[^\\s"'\\\\<>]*)/g,
                // AliExpress mobile pages embed video inside iframe srcs
                /<iframe[^>]+src=["']([^"']*video[^"']*)["']/gi,
                // Sometimes video URL is in a poster attribute or a meta tag
                /<video[^>]+src=["']([^"']+)["']/gi,
                /<source[^>]+src=["']([^"']+)["']/gi,
            ];
            patterns.forEach(p => {
                let m;
                while ((m = p.exec(html)) !== null) {
                    add(m[1] || m[0]);
                }
            });

            // 5. Schema.org VideoObject
            document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                try {
                    const d = JSON.parse(s.textContent);
                    const visit = (obj) => {
                        if (!obj) return;
                        if (Array.isArray(obj)) { obj.forEach(visit); return; }
                        if (typeof obj === 'object') {
                            if (obj['@type'] === 'VideoObject') {
                                add(obj.contentUrl);
                                add(obj.embedUrl);
                            }
                            for (const k in obj) visit(obj[k]);
                        }
                    };
                    visit(d);
                } catch(e) {}
            });

            // 6. Class-name based search (player wrappers)
            document.querySelectorAll('[class*="video" i], [class*="Video"], [class*="player" i]').forEach(el => {
                ['src','data-src','data-video','data-url'].forEach(a => add(el.getAttribute(a)));
            });

            // Score: prefer mp4 over m3u8, prefer Tao/Ali CDN over generic
            const ranked = [...urls].sort((a, b) => {
                const score = (u) => {
                    let s = 0;
                    if (/\\.mp4/i.test(u)) s += 10;
                    if (/cloud\\.video\\.taobao\\.com/i.test(u)) s += 5;
                    if (/alicdn\\.com/i.test(u)) s += 3;
                    if (/\\.m3u8/i.test(u)) s += 1;
                    return -s;  // ascending sort, lower = better
                };
                return score(a) - score(b);
            });

            return ranked.slice(0, 15);
        })()
    """) or []


# Hard caps so a mis-detected URL (an HLS playlist that trickles bytes, or an
# unexpectedly huge file) can never hang the pipeline or fill the disk. The
# requests stream `timeout` only bounds the gap *between* chunks, not the whole
# transfer — these enforce the overall ceilings. Override via env if needed.
_DOWNLOAD_MAX_BYTES = int(os.getenv("SSMAKER_DOWNLOAD_MAX_BYTES", str(200 * 1024 * 1024)))
_DOWNLOAD_MAX_SECONDS = float(os.getenv("SSMAKER_DOWNLOAD_MAX_SECONDS", "180"))


def _download_hls_via_ffmpeg(url: str, filepath: str, referer: str,
                             max_seconds: float = _DOWNLOAD_MAX_SECONDS) -> Optional[float]:
    """Best-effort HLS (.m3u8) download via ffmpeg.

    Marketplace videos are occasionally served only as HLS playlists, which the
    plain byte-stream path can't assemble (it would just save the text manifest
    and fail validation). When ffmpeg is available we remux the stream into the
    mp4 at `filepath`. Any failure returns None — no worse than the old behavior
    where every .m3u8 URL was discarded outright.
    """
    import subprocess
    try:
        from utils.ffmpeg import resolve_ffmpeg_exe
        ffmpeg = resolve_ffmpeg_exe()
    except Exception:
        ffmpeg = None
    if not ffmpeg:
        logger.info("[ProductSearcher] HLS url but ffmpeg unavailable, skip: %s", url[:80])
        return None
    try:
        cmd = [
            ffmpeg, "-y",
            "-headers", f"Referer: {referer}\r\n",
            "-i", url,
            "-c", "copy", "-bsf:a", "aac_adtstoasc",
            filepath,
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=max_seconds)
        if proc.returncode != 0 or not os.path.exists(filepath):
            logger.info("[ProductSearcher] ffmpeg HLS download failed (rc=%s): %s",
                        getattr(proc, "returncode", "?"), url[:80])
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
        size = os.path.getsize(filepath)
        if size < 10_000 or not _is_valid_video_file(filepath):
            logger.warning("[ProductSearcher] HLS result invalid/too small, discarding: %s", filepath)
            os.remove(filepath)
            return None
        return round(size / (1024 * 1024), 1)
    except subprocess.TimeoutExpired:
        logger.warning("[ProductSearcher] ffmpeg HLS timeout (%ss): %s", max_seconds, url[:80])
    except Exception as e:
        logger.info("[ProductSearcher] ffmpeg HLS error: %s", e)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except OSError:
        pass
    return None


def _download_video(url: str, filepath: str, referer: str, max_retries: int = 2,
                    max_bytes: int = _DOWNLOAD_MAX_BYTES,
                    max_seconds: float = _DOWNLOAD_MAX_SECONDS) -> Optional[float]:
    """Download video file with retry. Returns size in MB or None on failure.

    Enforces both a maximum byte size and a maximum wall-clock duration per
    attempt — requests' stream `timeout` only limits the gap between chunks, so
    a slow trickle or an unexpectedly huge file would otherwise run unbounded.
    """
    import time

    # HLS playlists need ffmpeg; the byte-stream path below can't assemble them.
    if ".m3u8" in url.lower():
        return _download_hls_via_ffmpeg(url, filepath, referer, max_seconds)

    for attempt in range(1, max_retries + 1):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": referer,
            }
            r = requests.get(url, headers=headers, timeout=(10, 60), stream=True)
            if r.status_code != 200:
                logger.warning("[ProductSearcher] Download HTTP %d (attempt %d/%d): %s",
                               r.status_code, attempt, max_retries, url[:80])
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None

            deadline = time.time() + max_seconds
            total = 0
            aborted: Optional[str] = None
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    f.write(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        aborted = f"size > {max_bytes} bytes"
                        break
                    if time.time() > deadline:
                        aborted = f"exceeded {max_seconds:.0f}s"
                        break

            if aborted:
                logger.warning("[ProductSearcher] Download aborted (%s): %s", aborted, url[:80])
                if os.path.exists(filepath):
                    os.remove(filepath)
                return None  # too big / too slow won't improve on retry

            if total < 10_000:  # <10KB = not a real video
                logger.warning("[ProductSearcher] File too small (%d bytes), discarding", total)
                os.remove(filepath)
                return None

            # Validate video file header (mp4 ftyp box or other common signatures)
            if not _is_valid_video_file(filepath):
                logger.warning("[ProductSearcher] Invalid video file, discarding: %s", filepath)
                os.remove(filepath)
                return None

            return round(total / (1024 * 1024), 1)

        except requests.exceptions.Timeout:
            logger.warning("[ProductSearcher] Download timeout (attempt %d/%d): %s",
                           attempt, max_retries, url[:80])
        except requests.exceptions.ConnectionError:
            logger.warning("[ProductSearcher] Connection error (attempt %d/%d): %s",
                           attempt, max_retries, url[:80])
        except Exception as e:
            logger.warning("[ProductSearcher] Download error (attempt %d/%d): %s", attempt, max_retries, e)

        if os.path.exists(filepath):
            os.remove(filepath)
        if attempt < max_retries:
            time.sleep(2)

    return None


def _is_valid_video_file(filepath: str) -> bool:
    """Quick check: verify file starts with known video signatures."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(12)
        if len(header) < 8:
            return False
        # MP4/MOV: ftyp box at offset 4
        if header[4:8] == b'ftyp':
            return True
        # WebM: EBML header
        if header[:4] == b'\x1a\x45\xdf\xa3':
            return True
        # AVI: RIFF....AVI
        if header[:4] == b'RIFF' and header[8:12] == b'AVI ':
            return True
        # FLV
        if header[:3] == b'FLV':
            return True
        # Unknown signature – reject
        return False
    except Exception:
        return False


def _simplify_to_head_noun(keyword: str, max_tokens: int = 2) -> str:
    """Reduce a long compound search keyword to its core head-noun form.

    e.g. "spice container set seasoning jar airtight spice container"
         → "spice container"

    Strategy:
      - Drop stopword tokens (set, kit, pack, ...)
      - Drop duplicates while preserving order
      - Keep only the first `max_tokens` non-stopword tokens
    Long compound keywords often return 0 or noisy results on marketplace
    search; the simplified form gets MORE candidates.
    """
    if not keyword:
        return ""
    raw_tokens = re.findall(r'[\u4e00-\u9fff]+|[\uac00-\ud7af]+|[a-z]+|\d+', keyword.lower())
    seen, kept = set(), []
    for t in raw_tokens:
        if t in _STOPWORD_TOKENS:
            continue
        if t in _HEAD_NOISE_TOKENS:
            continue
        if t in seen:
            continue
        seen.add(t)
        kept.append(t)
    if not kept:
        return ""

    anchors = [t for t in kept if any(a in t for a in _HEAD_ANCHOR_PARTS)]
    head_tokens: list[str] = []
    for t in anchors:
        if t not in head_tokens:
            head_tokens.append(t)
        if len(head_tokens) >= max_tokens:
            break

    if len(head_tokens) < max_tokens:
        for t in kept:
            if t in head_tokens:
                continue
            head_tokens.append(t)
            if len(head_tokens) >= max_tokens:
                break

    return " ".join(head_tokens)


async def _do_aliexpress_search(
    browser: Any, query: str, log_label: str, video_filter: bool = False,
) -> List[Dict[str, Any]]:
    """Single search attempt on AliExpress wholesale endpoint.

    When `video_filter` is True we append AliExpress's video-only filter, which
    restricts results to listings that have a seller-uploaded video. This is
    the single biggest lever for getting downloadable videos.

    Returns the raw candidate list (unsorted, unscored). Caller scores+merges.
    """
    import urllib.parse
    # Live-verified (2026-05): AliExpress does NOT honor a generic "video only"
    # search filter. Appending filterCategory=video&filter=hasVideo returns the
    # IDENTICAL result pool as the plain query (params are dropped and the
    # request is redirected to the localized /w/ results page). So `video_filter`
    # no longer changes the URL — it is kept only for call-site compatibility,
    # and callers must not assume the results are video-only.
    url = f"https://www.aliexpress.com/wholesale?SearchText={urllib.parse.quote(query)}"
    logger.info("[ProductSearcher] AliExpress search [%s%s]: %s",
                log_label, " VIDEO" if video_filter else "", query)
    print(f"[ProductSearcher] AliExpress search [{log_label}{' VIDEO' if video_filter else ''}]: {query}")

    tab = await browser.get(url)
    if tab is None:
        return []

    extract_js = """
        (() => {
            const seen = new Set();
            const items = [];
            const push = (id, title, price, image) => {
                if (!id || seen.has(id)) return;
                seen.add(id);
                const cleanTitle = (title || '').trim().substring(0, 140);
                const cleanPrice = (price || '').trim().substring(0, 60);
                items.push({
                    id,
                    title: cleanTitle || null,
                    price: cleanPrice || null,
                    image: image || null,
                    url: 'https://www.aliexpress.com/item/' + id + '.html',
                });
            };

            document.querySelectorAll('a[href*="/item/"], a[href*="aliexpress.us/item/"]').forEach(a => {
                if (items.length >= 60) return;
                const href = a.href || a.getAttribute('href') || '';
                const match = href.match(/item\\/(\\d{9,})/);
                if (!match) return;
                const card = a.closest(
                    '[class*="card"], [class*="Card"], [class*="product"], [class*="snippet"], li, article, div'
                ) || a.parentElement;
                const img = card ? card.querySelector('img[src]') : null;
                const priceEl = card ? card.querySelector('[class*="price"], [class*="Price"], [data-price]') : null;
                const titleEl = card
                    ? (card.querySelector('h1, h2, h3, [class*="title"], [class*="Title"], a[title], [aria-label]') || a)
                    : a;
                const title = (titleEl?.textContent || titleEl?.getAttribute?.('title') || titleEl?.getAttribute?.('aria-label') || '');
                const price = (priceEl?.textContent || priceEl?.getAttribute?.('data-price') || '');
                push(match[1], title, price, img ? img.src : '');
            });

            // Fallback: when cards are script-rendered, IDs still appear in HTML.
            const html = document.documentElement ? document.documentElement.innerHTML : '';
            const idMatches = [...html.matchAll(/item\\/(\\d{9,})\\.html/g)];
            idMatches.forEach((m) => {
                if (items.length >= 60) return;
                push(m[1], '', '', '');
            });
            return items;
        })()
    """

    # Wait adaptively for dynamic result rendering instead of one fixed sleep.
    raw: List[Dict[str, Any]] = []
    for i in range(8):
        await tab.sleep(1.2 if i else 2.0)
        try:
            raw = await tab.evaluate(extract_js) or []
        except Exception:
            raw = []
        if raw:
            break
        try:
            # Trigger lazy rendering / hydration.
            await tab.evaluate(f"window.scrollTo(0, {600 + i * 400})")
        except Exception:
            pass

    if raw:
        return raw

    # Detect challenge pages to improve debugging.
    try:
        challenge = await tab.evaluate(
            """
            (() => {
                const t = (document.title || '') + '\\n' + (location.href || '');
                const b = (document.body && document.body.innerText) ? document.body.innerText.slice(0, 5000) : '';
                return /captcha|verify|robot|security|challenge|punish/i.test(t + '\\n' + b);
            })()
            """
        )
        if challenge:
            logger.info("[ProductSearcher] AliExpress endpoint challenged on query='%s'", query[:60])
    except Exception:
        pass
    return []


async def search_aliexpress(
    browser: Any,
    keyword_en: str,
    reference_name: str,
    keyword_cn: str = "",
) -> List[Dict[str, Any]]:
    """
    Search AliExpress and return product candidates sorted by similarity.

    Multi-attempt strategy (priority on getting candidates with videos):
      1. Head-noun + VIDEO filter — biggest lever, returns ONLY listings
         that have seller-uploaded videos.
      2. Full keyword + VIDEO filter — precision pass with same video filter.
      3. Head-noun (no filter) — for products where filter returned too few.
      4. Full keyword (no filter) — fallback for niche queries.
      5. Korean reference name — AliExpress KR serves Korean-translated
         results; only used if total < 10.

    All raw candidates are merged, deduplicated by item ID, scored against the
    full reference set, and returned sorted by score.
    """
    import urllib.parse

    raw_all: list[dict] = []
    seen_ids: set[str] = set()

    head = _simplify_to_head_noun(keyword_en, max_tokens=2) or ""

    per_attempt_timeout = 14

    async def _run_attempt(q: str, label: str, use_video_filter: bool) -> None:
        if not q:
            return
        try:
            r = await asyncio.wait_for(
                _do_aliexpress_search(
                    browser,
                    q,
                    label,
                    video_filter=use_video_filter,
                ),
                timeout=per_attempt_timeout,
            )
        except asyncio.TimeoutError:
            logger.info(
                "[ProductSearcher] AliExpress %s attempt timed out (%ss)",
                label,
                per_attempt_timeout,
            )
            return
        except Exception as e:
            logger.info("[ProductSearcher] AliExpress %s attempt failed: %s", label, e)
            return
        for x in r:
            xid = x.get("id")
            if xid and xid not in seen_ids:
                seen_ids.add(xid)
                raw_all.append(x)

    # AliExpress doesn't honor a video-only filter (live-verified), so the
    # former "+VIDEO" passes were byte-for-byte duplicates of the plain passes
    # and only wasted navigations. Run distinct queries instead.
    # Attempt 1 — head-noun
    if head:
        await _run_attempt(head, "head-noun", False)

    # Attempt 2 — full keyword
    if len(raw_all) < 12 and keyword_en and keyword_en != head:
        await _run_attempt(keyword_en, "full", False)

    # Attempt 3 — Korean reference name
    if len(raw_all) < 10 and reference_name:
        kr_head = re.sub(r"[\[\]\(\)\{\}\|/,;]", " ", reference_name)
        kr_head = " ".join(kr_head.split()[:3])
        if kr_head:
            await _run_attempt(kr_head, "kr-head", False)

    raw = raw_all
    print(f"[ProductSearcher] AliExpress merged total: {len(raw)} candidates (video-filter prioritized)")

    # Score and sort — score against ALL three reference forms (Korean original
    # title, English keyword, Chinese keyword) and take the max. This is the
    # single biggest accuracy lever for cross-language matching: AliExpress
    # candidates often mix English titles with stray CN tokens, and a Korean
    # reference will share zero tokens with either alone.
    references = [reference_name, keyword_en, keyword_cn]
    candidates = []
    for p in raw:
        title = p.get("title", "")
        score = _multi_reference_score(title, references)
        candidates.append({**p, "score": score, "source": "aliexpress"})
    candidates.sort(key=lambda x: x["score"], reverse=True)

    logger.info("[ProductSearcher] AliExpress: %d candidates", len(candidates))
    return candidates


async def search_aliexpress_quick(
    browser: Any,
    keyword_en: str,
    reference_name: str,
    keyword_cn: str = "",
) -> List[Dict[str, Any]]:
    """Short fallback for AliExpress when the full multi-pass search times out.

    Runs only 2-3 essential passes and returns partial candidates quickly so the
    pipeline can continue instead of collapsing to zero candidates.
    """
    raw_all: list[dict] = []
    seen_ids: set[str] = set()

    head = _simplify_to_head_noun(keyword_en, max_tokens=2) or ""
    # AliExpress video filter is a no-op (see search_aliexpress) — distinct queries only.
    attempts: list[tuple[str, str, bool]] = []
    if head:
        attempts.append((head, "quick-head-noun", False))
    if keyword_en and keyword_en != head:
        attempts.append((keyword_en, "quick-full", False))

    per_attempt_timeout = 15

    for query, label, use_video_filter in attempts:
        if not query:
            continue
        try:
            raw = await asyncio.wait_for(
                _do_aliexpress_search(
                    browser, query, label, video_filter=use_video_filter
                ),
                timeout=per_attempt_timeout,
            )
        except asyncio.TimeoutError:
            logger.info(
                "[ProductSearcher] AliExpress %s timed out (%ss)",
                label,
                per_attempt_timeout,
            )
            continue
        except Exception as e:
            logger.info("[ProductSearcher] AliExpress %s failed: %s", label, e)
            continue

        for x in raw:
            xid = x.get("id")
            if xid and xid not in seen_ids:
                seen_ids.add(xid)
                raw_all.append(x)
        if len(raw_all) >= 20:
            break

    references = [reference_name, keyword_en, keyword_cn]
    candidates = []
    for p in raw_all:
        title = p.get("title", "")
        score = _multi_reference_score(title, references)
        candidates.append({**p, "score": score, "source": "aliexpress"})
    candidates.sort(key=lambda x: x["score"], reverse=True)
    logger.info("[ProductSearcher] AliExpress quick: %d candidates", len(candidates))
    return candidates


async def _do_1688_search(
    browser: Any, query: str, log_label: str, video_filter: bool = False,
) -> List[Dict[str, Any]]:
    """Single 1688 search attempt — tries multiple endpoints in order.

    Endpoints (best to worst guest-accessibility):
      1. m.1688.com mobile search — least login pressure, has video=1 filter
      2. show.1688.com video discovery — pages dedicated to video listings
      3. s.1688.com legacy desktop — last resort

    When `video_filter` is True we add the `video=1` query param (mobile) /
    `filter=video` (desktop) so only video-bearing offers come back.
    """
    import urllib.parse
    q = urllib.parse.quote(query)
    # The desktop selloffer search is the working endpoint (the old m.1688.com
    # mobile endpoints now 404 / "旺铺不存在"). We append the homepage-searchbox
    # spm + charset so the URL matches a genuine in-site search; combined with
    # the Referer navigation below, this clears 1688's anti-bot wall WITHOUT login.
    _base = (
        "https://s.1688.com/selloffer/offer_search.htm"
        f"?keywords={q}&spm=a260k.home2025.searchbox.0&charset=utf8"
    )
    if video_filter:
        candidate_urls = [_base + "&filter=video", _base]
    else:
        candidate_urls = [_base]
    logger.info("[ProductSearcher] 1688 search [%s%s]: %s",
                log_label, " VIDEO" if video_filter else "", query)
    print(f"[ProductSearcher] 1688 search [{log_label}{' VIDEO' if video_filter else ''}]: {query}")

    # Warm up on the 1688 homepage, then navigate the search URL carrying the
    # homepage Referer (via CDP). Direct deep-links get an "unusual traffic"
    # captcha; the SAME request with Referer: https://www.1688.com/ renders
    # normally — no login required (live-verified 2026-06). Falls back to a plain
    # navigation if the CDP path is unavailable.
    home = "https://www.1688.com/"
    try:
        from zendriver import cdp as _cdp
    except Exception:
        _cdp = None

    warm_tab = None
    try:
        warm_tab = await browser.get(home)
        await warm_tab.sleep(2)
    except Exception:
        warm_tab = None

    for url in candidate_urls:
        tab = None
        try:
            if warm_tab is not None and _cdp is not None:
                await warm_tab.send(_cdp.page.navigate(url=url, referrer=home))
                tab = warm_tab
                await tab.sleep(3)
            else:
                tab = await browser.get(url)
                if tab is None:
                    continue
                await tab.sleep(3)
        except Exception:
            try:
                tab = await browser.get(url)
            except Exception:
                tab = None
            if tab is None:
                continue
            await tab.sleep(3)

        current_url = await tab.evaluate("window.location.href") or ""
        # Only a real anti-bot wall blocks us — NOT login. 1688 content loads for
        # guests; a login prompt is a dismissible overlay with the offer cards in
        # the DOM behind it, so we never bail on login redirects.
        if any(x in current_url for x in ("_____tmd_____", "punish", "captcha", "nouser")):
            logger.info("[ProductSearcher] 1688 endpoint %s anti-bot challenged, trying next", url[:60])
            continue
        # Scroll for lazy-load. Some 1688 endpoints occasionally return an
        # intermediate/blank document where document.body is still null; treat
        # that as an empty endpoint and keep trying the next URL.
        page_ready = await tab.evaluate("""
            (() => {
                const h = Math.max(
                    document.body?.scrollHeight || 0,
                    document.documentElement?.scrollHeight || 0
                );
                if (!h) return false;
                window.scrollTo(0, h / 2);
                return true;
            })()
        """)
        if not page_ready:
            logger.info("[ProductSearcher] 1688 endpoint %s returned blank document", url[:60])
            continue
        await tab.sleep(1)
        await tab.evaluate("""
            (() => {
                const h = Math.max(
                    document.body?.scrollHeight || 0,
                    document.documentElement?.scrollHeight || 0
                );
                if (h) window.scrollTo(0, h);
            })()
        """)
        await tab.sleep(1)

        raw = await tab.evaluate("""
            (() => {
                const results = [];
                const seen = new Set();
                // Mobile and desktop both use offer/<id> patterns; mobile also
                // emits ?offerId=<id> on item links
                document.querySelectorAll(
                    'a[href*="detail.1688.com"],'
                    + 'a[href*="m.1688.com/offer"],'
                    + 'a[href*="offer/"],'
                    + 'a[href*="offerId"]'
                ).forEach(a => {
                    if (results.length >= 30) return;
                    const href = a.href || '';
                    let oid = null;
                    let m = href.match(/offer\\/(\\d{10,})/);
                    if (m) oid = m[1];
                    if (!oid) { m = href.match(/offerId[=:](\\d{10,})/); if (m) oid = m[1]; }
                    if (!oid) { m = href.match(/(\\d{10,})\\.html/); if (m) oid = m[1]; }
                    if (!oid || seen.has(oid)) return;
                    seen.add(oid);
                    const c = a.closest('[class*="item"], [class*="card"], [class*="offer"], li, div') || a.parentElement;
                    const img = c ? c.querySelector('img[src]') : null;
                    const tEl = c ? (c.querySelector('[class*="title"], h4, h3, h2') || a) : a;
                    const title = (tEl.title || tEl.textContent || '').trim();
                    const pEl = c ? c.querySelector('[class*="price"]') : null;
                    results.push({
                        id: oid, title: title.substring(0, 120),
                        price: pEl ? pEl.textContent.trim() : null,
                        image: img ? img.src : null,
                        url: 'https://detail.1688.com/offer/' + oid + '.html'
                    });
                });
                if (!results.length) {
                    const html = document.documentElement ? document.documentElement.innerHTML : '';
                    const push = (oid) => {
                        if (!oid || seen.has(oid) || results.length >= 30) return;
                        seen.add(oid);
                        results.push({
                            id: oid,
                            title: null,
                            price: null,
                            image: null,
                            url: 'https://detail.1688.com/offer/' + oid + '.html'
                        });
                    };
                    [...html.matchAll(/offer\\/(\\d{10,})\\.html/g)].forEach(m => push(m[1]));
                    [...html.matchAll(/offerId[=:](\\d{10,})/g)].forEach(m => push(m[1]));
                }
                return results;
            })()
        """) or []
        if raw:
            return raw
    return []


async def search_1688(
    browser: Any,
    keyword_cn: str,
    reference_name: str,
) -> List[Dict[str, Any]]:
    """
    Search 1688. Prioritizes the mobile + video-filter endpoint which is
    much more guest-friendly and surfaces only video-bearing offers.

    Order:
      1. head-noun + VIDEO filter (m.1688.com)
      2. full keyword + VIDEO filter
      3. head-noun without filter (recall pass)
      4. full keyword without filter
    """
    raw_all: list[dict] = []
    seen_ids: set[str] = set()

    head = _simplify_to_head_noun(keyword_cn, max_tokens=2) or ""
    per_attempt_timeout = 15

    async def _run_attempt(q: str, label: str, use_video_filter: bool) -> None:
        if not q:
            return
        try:
            r = await asyncio.wait_for(
                _do_1688_search(
                    browser,
                    q,
                    label,
                    video_filter=use_video_filter,
                ),
                timeout=per_attempt_timeout,
            )
        except asyncio.TimeoutError:
            logger.info(
                "[ProductSearcher] 1688 %s attempt timed out (%ss)",
                label,
                per_attempt_timeout,
            )
            return
        except Exception as e:
            logger.info("[ProductSearcher] 1688 %s attempt failed: %s", label, e)
            return
        for x in r:
            xid = x.get("id")
            if xid and xid not in seen_ids:
                seen_ids.add(xid)
                raw_all.append(x)

    # _do_1688_search now falls back from the video-filtered URL to the plain
    # URL internally, so one pass per distinct query is enough (the old no-filter
    # head/full passes just re-fetched the same desktop results).
    if head:
        await _run_attempt(head, "head-noun", True)

    if len(raw_all) < 12 and keyword_cn and keyword_cn != head:
        await _run_attempt(keyword_cn, "full", True)

    raw = raw_all
    if not raw:
        logger.info("[ProductSearcher] 1688 returned 0 candidates (likely login wall)")
        print(f"[ProductSearcher] 1688 returned 0 candidates")
        return []

    print(f"[ProductSearcher] 1688 merged total: {len(raw)} candidates")

    references = [reference_name, keyword_cn]
    candidates = []
    for p in raw:
        title = p.get("title", "")
        score = _multi_reference_score(title, references)
        candidates.append({**p, "score": score, "source": "1688"})
    candidates.sort(key=lambda x: x["score"], reverse=True)

    logger.info("[ProductSearcher] 1688: %d candidates", len(candidates))
    return candidates


async def search_1688_quick(
    browser: Any,
    keyword_cn: str,
    reference_name: str,
    keyword_en: str = "",
) -> List[Dict[str, Any]]:
    """Short fallback for 1688 when the full multi-pass search times out."""
    raw_all: list[dict] = []
    seen_ids: set[str] = set()

    head = _simplify_to_head_noun(keyword_cn, max_tokens=4) or ""
    # _do_1688_search already falls back filter->plain internally; distinct queries only.
    attempts: list[tuple[str, str, bool]] = []
    if head:
        attempts.append((head, "quick-head-noun", True))
    if keyword_cn and keyword_cn != head:
        attempts.append((keyword_cn, "quick-full", True))

    per_attempt_timeout = 15

    for query, label, use_video_filter in attempts:
        if not query:
            continue
        try:
            raw = await asyncio.wait_for(
                _do_1688_search(
                    browser, query, label, video_filter=use_video_filter
                ),
                timeout=per_attempt_timeout,
            )
        except asyncio.TimeoutError:
            logger.info(
                "[ProductSearcher] 1688 %s timed out (%ss)",
                label,
                per_attempt_timeout,
            )
            continue
        except Exception as e:
            logger.info("[ProductSearcher] 1688 %s failed: %s", label, e)
            continue

        for x in raw:
            xid = x.get("id")
            if xid and xid not in seen_ids:
                seen_ids.add(xid)
                raw_all.append(x)
        if len(raw_all) >= 20:
            break

    if not raw_all:
        logger.info("[ProductSearcher] 1688 quick returned 0 candidates")
        return []

    references = [reference_name, keyword_cn, keyword_en]
    candidates = []
    for p in raw_all:
        title = p.get("title", "")
        score = _multi_reference_score(title, references)
        candidates.append({**p, "score": score, "source": "1688"})
    candidates.sort(key=lambda x: x["score"], reverse=True)
    logger.info("[ProductSearcher] 1688 quick: %d candidates", len(candidates))
    return candidates


async def search_1688_by_image(
    browser: Any,
    image_url: str,
    reference_name: str,
    keyword_cn: str = "",
    keyword_en: str = "",
) -> List[Dict[str, Any]]:
    """Image-first 1688 search.

    1688 desktop endpoints are often challenge-gated for bot-like traffic.
    Mobile endpoints tend to be more tolerant, so we try mobile-first and then
    desktop URL-parameter image-search endpoints.
    """
    import urllib.parse

    if not image_url or not image_url.startswith("http"):
        return []

    print(f"[ProductSearcher] 1688 IMAGE search: {image_url[:80]}")
    logger.info("[ProductSearcher] 1688 image search: %s", image_url[:80])

    encoded = urllib.parse.quote(image_url, safe="")
    search_urls = [
        # Mobile-first (usually less login pressure)
        f"https://m.1688.com/offer/search.htm?imageAddress={encoded}",
        f"https://m.1688.com/page/offerlist.html?imageAddress={encoded}",
        # Desktop image-search pages (may hit anti-bot wall; still worth trying)
        f"https://s.1688.com/youyuan/index.htm?imageAddress={encoded}",
        f"https://s.1688.com/selloffer/offer_search.htm?imageAddress={encoded}",
    ]

    raw_all: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for idx, url in enumerate(search_urls, start=1):
        try:
            tab = await browser.get(url)
            if tab is None:
                continue
            await tab.sleep(7)

            current_url = await tab.evaluate("window.location.href") or ""
            # Only bail on a real anti-bot wall, not on login (1688 content loads
            # for guests; login prompts are dismissible overlays).
            if any(x in current_url for x in ("_____tmd_____", "punish", "captcha", "nouser")):
                logger.info("[ProductSearcher] 1688 image endpoint anti-bot challenged: %s", current_url[:100])
                continue

            # Trigger lazy-load before scraping cards.
            for y in (300, 700, 1200, 1800):
                await tab.evaluate(f"window.scrollTo(0, {y})")
                await tab.sleep(1)
            await tab.evaluate("window.scrollTo(0, 0)")
            await tab.sleep(1)

            raw = await tab.evaluate("""
                (() => {
                    const results = [];
                    const seen = new Set();
                    document.querySelectorAll(
                        'a[href*="detail.1688.com"],'
                        + 'a[href*="m.1688.com/offer"],'
                        + 'a[href*="offer/"],'
                        + 'a[href*="offerId"]'
                    ).forEach(a => {
                        if (results.length >= 40) return;
                        const href = a.href || '';
                        let oid = null;
                        let m = href.match(/offer\\/(\\d{10,})/);
                        if (m) oid = m[1];
                        if (!oid) { m = href.match(/offerId[=:](\\d{10,})/); if (m) oid = m[1]; }
                        if (!oid) { m = href.match(/(\\d{10,})\\.html/); if (m) oid = m[1]; }
                        if (!oid || seen.has(oid)) return;
                        seen.add(oid);
                        const c = a.closest('[class*="item"], [class*="card"], [class*="offer"], li, div') || a.parentElement;
                        const img = c ? c.querySelector('img[src]') : null;
                        const tEl = c ? (c.querySelector('[class*="title"], h4, h3, h2') || a) : a;
                        const title = (tEl.title || tEl.textContent || '').trim();
                        const pEl = c ? c.querySelector('[class*="price"]') : null;
                        results.push({
                            id: oid,
                            title: title.substring(0, 120),
                            price: pEl ? pEl.textContent.trim() : null,
                            image: img ? img.src : null,
                            url: 'https://detail.1688.com/offer/' + oid + '.html'
                        });
                    });
                    return results;
                })()
            """) or []

            for x in raw:
                xid = x.get("id")
                if xid and xid not in seen_ids:
                    seen_ids.add(xid)
                    raw_all.append(x)

            logger.info(
                "[ProductSearcher] 1688 image endpoint #%d yielded %d new candidates",
                idx,
                len(raw),
            )
        except Exception as e:
            logger.warning("[ProductSearcher] 1688 image endpoint #%d error: %s", idx, e)

    if not raw_all:
        print("[ProductSearcher] 1688 IMAGE search: 0 candidates")
        return []

    references = [reference_name, keyword_cn, keyword_en]
    candidates = []
    for p in raw_all:
        title = p.get("title", "")
        text_score = _multi_reference_score(title, references)
        candidates.append(
            {
                **p,
                "score": min(1.0, text_score + 0.10),
                "source": "1688",
                "image_search": True,
            }
        )
    candidates.sort(key=lambda x: x["score"], reverse=True)
    print(f"[ProductSearcher] 1688 IMAGE search: {len(candidates)} candidates")
    return candidates




async def search_aliexpress_by_image(
    browser: Any,
    image_url: str,
    reference_name: str,
    keyword_en: str = "",
    keyword_cn: str = "",
) -> List[Dict[str, Any]]:
    """Image-based search on AliExpress as a fallback when text search yields
    too few candidates. AliExpress's image-search endpoint accepts an image URL
    via the `imageAddress` query parameter, so we can drive it without uploading
    a file (which would require a multipart POST and a CSRF token).

    Returns the same candidate dict shape as `search_aliexpress`.
    """
    import urllib.parse
    if not image_url or not image_url.startswith("http"):
        return []

    print(f"[ProductSearcher] AliExpress IMAGE search: {image_url[:80]}")
    logger.info("[ProductSearcher] AliExpress image search: %s", image_url[:80])

    encoded = urllib.parse.quote(image_url, safe="")
    search_urls = [
        f"https://www.aliexpress.com/p/searchByImg.html?imageAddress={encoded}",
        f"https://www.aliexpress.com/p/imageSearch/index.html?imageAddress={encoded}",
    ]

    raw_all: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for idx, url in enumerate(search_urls, start=1):
        try:
            tab = await browser.get(url)
            if tab is None:
                continue
            await tab.sleep(7)
            for y in (300, 700, 1200, 1700):
                await tab.evaluate(f"window.scrollTo(0, {y})")
                await tab.sleep(1)
            await tab.evaluate("window.scrollTo(0, 0)")
            await tab.sleep(1)

            raw = await tab.evaluate("""
                (() => {
                    const seen = new Set();
                    const items = [];
                    const pushItem = (id, title, image) => {
                        if (!id || seen.has(id)) return;
                        seen.add(id);
                        items.push({
                            id,
                            title: (title || '').trim().substring(0, 120) || null,
                            image: image || null,
                            url: 'https://ko.aliexpress.com/item/' + id + '.html',
                        });
                    };

                    document.querySelectorAll('a[href*="/item/"]').forEach(a => {
                        if (items.length >= 60) return;
                        const href = a.href || '';
                        const match = href.match(/item\\/(\\d+)/);
                        if (!match) return;
                        const card = a.closest('[class*="card"], [class*="Card"], [class*="product"], [class*="snippet"], li, div') || a.parentElement;
                        const img = card ? card.querySelector('img') : null;
                        const titleEl = card ? (card.querySelector('h1, h2, h3, [class*="title"], [class*="Title"]') || a) : a;
                        pushItem(match[1], titleEl ? titleEl.textContent : '', img ? img.src : '');
                    });

                    // Fallback: parse IDs from the full HTML when cards are rendered
                    // through script-driven templates.
                    const html = document.documentElement ? document.documentElement.innerHTML : '';
                    const idMatches = [...html.matchAll(/item\\/(\\d{9,})\\.html/g)];
                    idMatches.forEach((m) => {
                        if (items.length >= 60) return;
                        pushItem(m[1], '', '');
                    });
                    return items;
                })()
            """) or []

            added = 0
            for item in raw:
                iid = str(item.get("id") or "")
                if not iid or iid in seen_ids:
                    continue
                seen_ids.add(iid)
                raw_all.append(item)
                added += 1
            logger.info(
                "[ProductSearcher] AliExpress image endpoint #%d yielded %d new candidates",
                idx,
                added,
            )
            if len(raw_all) >= 30:
                break
        except Exception as e:
            logger.warning("[ProductSearcher] AliExpress image endpoint #%d error: %s", idx, e)

    raw = raw_all

    # Score candidates against the same reference set as text search. Image
    # search is intrinsically high-precision (visual match) so even a weak text
    # score still represents a likely-correct candidate — but we score for
    # ranking purposes when there are many candidates.
    references = [reference_name, keyword_en, keyword_cn]
    candidates = []
    for p in raw:
        title = p.get("title", "")
        text_score = _multi_reference_score(title, references)
        # Boost by 0.10 because image-search candidates are pre-filtered by
        # visual similarity, so even low text overlap is meaningful.
        candidates.append({
            **p, "score": min(1.0, text_score + 0.10), "source": "aliexpress",
            "image_search": True,
        })
    candidates.sort(key=lambda x: x["score"], reverse=True)
    print(f"[ProductSearcher] AliExpress IMAGE search: {len(candidates)} candidates")
    return candidates


MIN_SIMILARITY_SCORE = 0.15  # candidates below this are too dissimilar to trust


# Category guard: words that MUST appear (case-insensitive substring) in candidate
# title for the candidate to be considered. This is what raises matching accuracy
# from "any video" to "video that's actually the same kind of product" — a sponge
# holder search rejects cards whose title doesn't mention sponge/sink/수세미 etc.
#
# Each guard maps a category keyword (matched against the English search term) to
# a list of tokens at least one of which must appear in the candidate title.
# Tokens span English / Korean / Chinese — most candidate titles include at least
# one language's category word so a single token list covers all marketplaces.
_CATEGORY_GUARDS: Dict[str, List[str]] = {
    # ──── Kitchen — sink / sponge / dish ────
    "sponge": ["sponge", "sink", "수세미", "海绵", "厨房"],
    "kitchen sink": ["sink", "sponge", "수세미", "싱크", "海绵", "厨房"],
    "dish drying": ["dish", "drying", "rack", "건조", "식기", "碗碟", "沥水"],
    "dish rack": ["dish", "drying", "rack", "건조", "식기", "碗碟", "沥水"],
    "dish drainer": ["dish", "drainer", "drying", "rack", "식기", "건조", "碗碟", "沥水"],
    "drying rack": ["dish", "drying", "rack", "건조", "식기", "碗碟", "沥水"],
    "sink strainer": ["strainer", "sink", "drain", "filter", "거름망", "싱크", "씽크", "水槽", "过滤"],
    "strainer holder": ["strainer", "sink", "drain", "filter", "거름망", "싱크", "씽크", "水槽", "过滤"],
    "food waste strainer": ["strainer", "sink", "drain", "filter", "food", "거름망", "음식물", "水槽", "过滤"],

    # ──── Kitchen — cutting / chopping ────
    "cutting board": ["cutting", "board", "chop", "도마", "砧板", "切菜"],
    "chopping board": ["cutting", "board", "chop", "도마", "砧板", "切菜"],
    "chopper": ["chop", "slicer", "cutter", "다지기", "썰기", "切", "剁", "碎"],
    "vegetable chopper": ["veg", "chop", "slicer", "cutter", "야채", "채칼", "切菜", "切", "蔬菜"],
    "vegetable slicer": ["veg", "slicer", "cutter", "chop", "야채", "채칼", "切菜", "切", "蔬菜"],
    "slicer": ["slicer", "cutter", "chop", "채칼", "切", "切菜"],
    "grater": ["grater", "grate", "강판", "刨", "擦"],
    "peeler": ["peel", "필러", "刨", "削皮"],

    # ──── Kitchen — knife / scissors ────
    "kitchen knife": ["knife", "kitchen", "주방", "도", "刀", "厨"],
    "kitchen scissors": ["scissor", "shear", "가위", "剪刀", "剪"],
    "scissors": ["scissor", "shear", "가위", "剪刀", "剪"],
    "knife sharpener": ["sharpen", "knife", "숫돌", "磨刀"],

    # ──── Kitchen — small tools ────
    "garlic press": ["garlic", "press", "마늘", "蒜", "压"],
    "can opener": ["can", "open", "캔", "开罐", "开瓶"],
    "bottle opener": ["bottle", "open", "병따개", "开瓶"],
    "egg beater": ["egg", "beater", "whisk", "거품기", "蛋", "打蛋"],
    "whisk": ["whisk", "beater", "거품기", "打蛋"],
    "ladle": ["ladle", "spoon", "국자", "勺"],
    "spatula": ["spatula", "turner", "뒤집개", "주걱", "铲", "勺"],
    "tongs": ["tong", "집게", "夹"],
    "rolling pin": ["rolling", "pin", "밀대", "擀面"],
    "ice tray": ["ice", "tray", "얼음", "冰", "冰格"],
    "ice cube": ["ice", "cube", "얼음", "冰", "冰格"],

    # ──── Kitchen — storage / organizing ────
    "spice": ["spice", "season", "조미", "양념", "调味"],
    "spice rack": ["spice", "season", "rack", "조미", "양념", "调味"],
    "seasoning": ["spice", "season", "조미", "양념", "调味"],
    "kitchen hook": ["hook", "후크", "걸이", "挂钩"],
    "kitchen shelf": ["shelf", "rack", "선반", "架", "置物"],
    "kitchen rack": ["rack", "shelf", "선반", "거치", "架", "置物"],
    "kitchen organizer": ["organiz", "storage", "정리", "수납", "收纳", "整理"],
    "storage box": ["storage", "box", "수납", "정리", "收纳", "盒"],
    "drawer organizer": ["drawer", "organiz", "서랍", "抽屉", "收纳"],
    "fridge organizer": ["fridge", "refrig", "organiz", "냉장고", "冰箱", "收纳"],
    "egg holder": ["egg", "holder", "tray", "계란", "鸡蛋", "蛋"],

    # ──── Kitchen — cooking equipment ────
    "frying pan": ["pan", "fry", "팬", "锅"],
    "pan": ["pan", "팬", "锅"],
    "pot": ["pot", "냄비", "锅"],
    "steamer": ["steam", "찜", "蒸"],
    "kettle": ["kettle", "주전자", "壶"],
    "blender": ["blend", "mixer", "믹서", "搅拌"],
    "manual juicer": ["juicer", "juice", "수동", "착즙", "榨汁"],
    "juicer": ["juicer", "juice", "착즙", "榨汁"],
    "rice scoop": ["rice", "scoop", "주걱", "饭勺", "饭铲"],
    "rice cooker": ["rice", "cook", "밥솥", "电饭"],

    # ──── Kitchen — containers ────
    "food container": ["container", "box", "통", "盒", "容器"],
    "lunch box": ["lunch", "box", "도시락", "便当"],
    "water bottle": ["water", "bottle", "물병", "水壶"],
    "tumbler": ["tumbler", "텀블러", "杯"],
    "mug": ["mug", "cup", "머그", "杯"],

    # ──── Kitchen — cleaning ────
    "dish brush": ["brush", "수세", "솔", "刷"],
    "cleaning brush": ["brush", "솔", "清洁", "刷"],
    "drain": ["drain", "배수", "下水", "沥"],

    # ──── Bath / shower ────
    "shower": ["shower", "샤워", "花洒"],
    "shower head": ["shower", "head", "샤워", "花洒"],
    "soap dispenser": ["soap", "dispens", "디스펜서", "皂液"],
    "toothpaste": ["toothpaste", "치약", "牙膏"],
    "toothbrush": ["toothbrush", "칫솔", "牙刷"],
    "bath": ["bath", "shower", "욕실", "浴"],

    # ──── Storage / general organizing ────
    "clothes hanger": ["hanger", "옷걸이", "衣架"],
    "shoe rack": ["shoe", "rack", "신발", "鞋"],
    "cable organizer": ["cable", "wire", "케이블", "线", "理线"],

    # ──── Phone / digital ────
    "phone stand": ["phone", "휴대폰", "핸드폰", "手机"],
    "phone holder": ["phone", "휴대폰", "핸드폰", "手机"],
    "phone case": ["phone", "case", "휴대폰", "케이스", "手机", "壳"],
    "phone ring": ["ring", "grip", "그립", "指环", "戒指"],
    "tablet stand": ["tablet", "ipad", "태블릿", "平板"],
    "magsafe": ["magsafe", "magnetic", "magnet"],
    "earphone": ["earphone", "earbud", "이어폰", "이어버드", "耳机"],
    "headphone": ["headphone", "headset", "헤드폰", "헤드셋", "耳机"],
    "charger": ["charger", "charging", "충전", "充电"],
    "cable": ["cable", "wire", "cord", "케이블", "선", "코드", "线"],
    "power bank": ["power", "bank", "보조배터리", "充电宝", "移动电源"],
    "wireless": ["wireless", "bluetooth", "bt", "无线", "蓝牙"],
    "smartwatch": ["watch", "smartwatch", "스마트워치", "手表"],
    "speaker": ["speaker", "스피커", "音箱"],

    # ──── Beauty / personal care ────
    "mask pack": ["mask", "마스크팩", "面膜"],
    "face mask": ["mask", "face", "마스크팩", "면", "面膜"],
    "skincare": ["skincare", "cream", "lotion", "serum", "essence", "스킨", "크림", "토너", "护肤"],
    "lipstick": ["lipstick", "lip", "립스틱", "唇"],
    "perfume": ["perfume", "fragrance", "향수", "香水"],
    "shampoo": ["shampoo", "샴푸", "洗发"],
    "soap": ["soap", "비누", "皂"],
    "hair dryer": ["dryer", "hair", "드라이기", "吹风"],
    "hair brush": ["brush", "comb", "빗", "梳"],
    "razor": ["razor", "shaver", "면도", "剃须"],
    "nail": ["nail", "manicure", "네일", "美甲", "指甲"],

    # ──── Fashion / clothing ────
    "tshirt": ["t-shirt", "tshirt", "shirt", "티셔츠", "셔츠", "T恤"],
    "hoodie": ["hoodie", "후드", "卫衣"],
    "pants": ["pants", "trousers", "바지", "裤"],
    "jeans": ["jeans", "denim", "청바지", "牛仔"],
    "dress": ["dress", "원피스", "连衣裙"],
    "skirt": ["skirt", "스커트", "치마", "裙"],
    "sock": ["sock", "양말", "袜"],
    "shoes": ["shoes", "sneaker", "신발", "운동화", "鞋"],
    "sneakers": ["sneaker", "shoes", "운동화", "鞋"],
    "slippers": ["slipper", "sandal", "슬리퍼", "쪼리", "拖鞋"],
    "sandals": ["sandal", "샌들", "凉鞋"],
    "bag": ["bag", "pouch", "가방", "파우치", "包"],
    "backpack": ["backpack", "백팩", "双肩包"],
    "wallet": ["wallet", "purse", "지갑", "钱包"],
    "belt": ["belt", "벨트", "皮带"],
    "hat": ["hat", "cap", "모자", "帽"],
    "scarf": ["scarf", "muffler", "스카프", "머플러", "围巾"],
    "glove": ["glove", "장갑", "手套"],
    "necklace": ["necklace", "목걸이", "项链"],
    "earring": ["earring", "귀걸이", "耳环"],
    "ring": ["ring", "반지", "戒指"],
    "bracelet": ["bracelet", "팔찌", "手链"],
    "watch": ["watch", "시계", "手表"],
    "sunglasses": ["sunglasses", "선글라스", "墨镜"],

    # ──── Home / furniture / decor ────
    "pillow": ["pillow", "cushion", "베개", "쿠션", "枕"],
    "blanket": ["blanket", "throw", "담요", "毯"],
    "curtain": ["curtain", "커튼", "窗帘"],
    "rug": ["rug", "carpet", "mat", "러그", "카펫", "地毯", "垫"],
    "lamp": ["lamp", "light", "램프", "조명", "灯"],
    "candle": ["candle", "양초", "蜡烛"],
    "vase": ["vase", "꽃병", "花瓶"],
    "clock": ["clock", "시계", "钟"],
    "mirror": ["mirror", "거울", "镜"],
    "frame": ["frame", "액자", "框"],

    # ──── Toys / kids ────
    "toy": ["toy", "장난감", "玩具"],
    "doll": ["doll", "인형", "娃娃"],
    "puzzle": ["puzzle", "퍼즐", "拼图"],
    "lego": ["lego", "block", "레고", "블록", "积木"],
    "stationery": ["stationer", "펜", "노트", "文具", "笔", "本"],
    "pen": ["pen", "펜", "笔"],
    "notebook": ["notebook", "diary", "노트", "笔记"],

    # ──── Pets ────
    "pet": ["pet", "dog", "cat", "강아지", "고양이", "宠物", "狗", "猫"],
    "dog": ["dog", "강아지", "狗"],
    "cat": ["cat", "고양이", "猫"],

    # ──── Fitness / sports ────
    "yoga mat": ["yoga", "mat", "요가", "瑜伽"],
    "dumbbell": ["dumbbell", "weight", "덤벨", "哑铃"],
    "fitness": ["fitness", "exercise", "운동", "健身"],

    # ──── Auto ────
    "car fan": ["car", "vehicle", "dashboard", "12v", "24v", "fan", "cooling", "차량", "자동차", "车载", "汽车", "风扇"],
    "vehicle fan": ["car", "vehicle", "dashboard", "12v", "24v", "fan", "cooling", "차량", "자동차", "车载", "汽车", "风扇"],
    "dashboard fan": ["dashboard", "car", "vehicle", "fan", "차량", "자동차", "车载", "汽车", "风扇"],
    "car phone mount": ["car", "phone", "차량", "手机", "车载"],
    "car charger": ["car", "charger", "차량", "充电", "车载"],
}


# Reverse map: canonical kitchen markers we use to detect "kitchen domain"
# from a Korean reference title.
_DOMAIN_MARKERS: Dict[str, list[str]] = {
    "kitchen": [
        "주방", "조리", "야채", "채칼", "도마", "수세미", "스폰지", "스펀지",
        "식기", "양념", "조미", "마늘", "달걀", "계란", "냄비", "팬", "프라이팬",
        "밥", "쌀", "냉장고", "싱크", "씽크", "거름망", "배수구", "kitchen", "cook", "food",
    ],
    "phone": [
        "휴대폰", "핸드폰", "스마트폰", "폰", "아이폰", "갤럭시", "phone", "iphone",
        "galaxy", "magsafe",
    ],
    "beauty": [
        "스킨", "크림", "토너", "에센스", "세럼", "마스크팩", "팩", "립스틱", "립",
        "쿠션", "파운데이션", "샴푸", "린스", "비누", "향수", "skincare", "cream",
        "lipstick", "shampoo", "perfume",
    ],
    "fashion": [
        "티셔츠", "셔츠", "후드", "바지", "청바지", "원피스", "스커트", "양말",
        "신발", "운동화", "슬리퍼", "샌들", "가방", "백팩", "지갑", "벨트", "모자",
        "shirt", "pants", "shoes", "bag", "hat",
    ],
    "home": [
        "쿠션", "베개", "담요", "커튼", "러그", "카펫", "램프", "조명", "양초",
        "꽃병", "거울", "액자", "pillow", "blanket", "curtain", "rug", "lamp",
    ],
    "digital": [
        "이어폰", "헤드셋", "스피커", "충전기", "케이블", "보조배터리", "스마트워치",
        "태블릿", "earphone", "speaker", "charger", "cable", "watch",
    ],
    "auto": [
        "차량", "자동차", "차", "car", "vehicle", "dashboard", "车载", "汽车",
        "풍량", "선풍기", "fan", "风扇",
    ],
}

_DOMAIN_TOKENS: Dict[str, list[str]] = {
    "kitchen": [
        "kitchen", "주방", "厨", "cook", "조리", "요리", "food", "음식", "食",
    ],
    "phone": [
        "phone", "휴대폰", "핸드폰", "手机", "iphone", "galaxy", "smartphone",
    ],
    "beauty": [
        "beauty", "skin", "cream", "cosmet", "스킨", "크림", "美容", "护肤", "化妆",
    ],
    "fashion": [
        "fashion", "clothes", "wear", "옷", "의류", "服装", "服饰",
    ],
    "home": [
        "home", "decor", "interior", "인테리어", "家居", "装饰",
    ],
    "digital": [
        "digital", "electronic", "전자", "디지털", "数码", "电子",
    ],
    "auto": [
        "car", "vehicle", "dashboard", "차량", "자동차", "차", "车载", "汽车",
    ],
}


def _detect_domain(reference_name: str, keyword_en: str, keyword_cn: str) -> str:
    """Detect the high-level product domain (kitchen/phone/beauty/...) from
    a Korean Coupang reference name + the resolved EN/CN keywords.

    Returns the domain name with the strongest signal, or "" if undetectable.
    """
    haystack = f"{reference_name} {keyword_en} {keyword_cn}".lower()
    scores: Dict[str, int] = {}
    for domain, markers in _DOMAIN_MARKERS.items():
        scores[domain] = sum(1 for m in markers if m.lower() in haystack)
    best_domain = max(scores, key=lambda k: scores[k]) if scores else ""
    return best_domain if scores.get(best_domain, 0) > 0 else ""


def _guard_key_matches(guard_key: str, kw: str) -> bool:
    """Word-boundary match of a guard key against the search keyword.

    Plain substring matching (`guard_key in kw`) mis-fires: "pan" is inside
    "japanese", "pen" inside "dispenser", "pot" inside "potato". That silently
    swaps in the wrong category guard and then rejects every correct candidate.
    Anchoring on alphanumeric boundaries prevents the collisions while still
    allowing multi-word keys like "car fan".
    """
    if not guard_key or not kw:
        return False
    return re.search(
        r"(?<![a-z0-9])" + re.escape(guard_key) + r"(?![a-z0-9])", kw
    ) is not None


def _category_terms_for_keyword(
    keyword_en: str,
    *,
    reference_name: str = "",
    keyword_cn: str = "",
) -> List[str]:
    """Pick the strictest applicable guard list for a given search query.

    Algorithm:
        1. Longest matching dictionary guard wins (specific > generic).
        2. If none matches, infer the high-level domain (kitchen/phone/beauty/
           fashion/home/digital) from the reference and apply that domain's
           catch-all token list.
        3. If domain undetectable too, return [] (no guard — last resort).
    """
    kw = (keyword_en or "").lower()
    # 1) Longest specific guard wins
    matches = sorted(
        (g for g in _CATEGORY_GUARDS if _guard_key_matches(g, kw)),
        key=len,
        reverse=True,
    )
    if matches:
        return _CATEGORY_GUARDS[matches[0]]

    # 2) Domain-level fallback — phone domain rejects kitchen items, etc.
    domain = _detect_domain(reference_name, keyword_en, keyword_cn)
    if domain and domain in _DOMAIN_TOKENS:
        return list(_DOMAIN_TOKENS[domain])

    # 3) No guard
    return []


def _passes_category_guard(title: str, terms: List[str]) -> bool:
    """True if no terms specified, or title contains at least one term."""
    if not terms:
        return True
    t = (title or "").lower()
    return any(term.lower() in t for term in terms)


def _passes_reference_constraints(title: str, references: Optional[List[str]]) -> bool:
    """Reject candidates that match the broad category but contradict key attributes."""
    if not references:
        return True

    ref = " ".join(r for r in references if r).lower()
    title_l = (title or "").lower()
    if not title_l:
        return False

    metal_markers = ("스텐", "스테인", "stainless", "steel", "metal", "304")
    silicone_markers = ("silicone", "실리콘", "硅胶")
    title_metal_markers = ("stainless", "steel", "metal", "304", "스텐", "스테인", "不锈钢")
    if any(marker in ref for marker in metal_markers):
        if any(marker in title_l for marker in silicone_markers) and not any(
            marker in title_l for marker in title_metal_markers
        ):
            return False

    adhesive_markers = ("접착", "adhesive", "stick", "붙")
    title_adhesive_markers = ("adhesive", "stick", "wall", "mount", "mounted", "붙", "접착")
    if any(marker in ref for marker in adhesive_markers):
        soft_countertop_markers = ("soap dish", "silicone", "countertop", "tray")
        if any(marker in title_l for marker in soft_countertop_markers) and not any(
            marker in title_l for marker in title_adhesive_markers
        ):
            return False

    # Sink-strainer intent: reject basin/wash-sink fixtures unless the title
    # explicitly includes strainer/filter/drain basket markers.
    strainer_intent_markers = (
        "거름망", "배수", "음식물", "strainer", "filter", "drain", "水槽", "过滤", "沥水",
    )
    basin_fixture_markers = (
        "washbasin", "wash basin", "basin", "vanity", "lavabo", "undermount", "topmount",
        "wall-mounted", "wall mounted", "utility sink", "hand wash sink",
        "세면대", "洗手盆", "面盆", "台盆",
    )
    strainer_title_markers = (
        "strainer", "filter", "drain", "basket", "waste", "rack", "holder",
        "거름망", "배수", "음식물", "过滤", "沥水", "挂架",
    )
    if any(marker in ref for marker in strainer_intent_markers):
        if any(marker in title_l for marker in basin_fixture_markers) and not any(
            marker in title_l for marker in strainer_title_markers
        ):
            return False

    # Car-fan intent: require both "fan" semantics and "vehicle" semantics.
    # This blocks unrelated low-score candidates such as fuses (vehicle-only)
    # and hand fans (fan-only).
    car_fan_ref_markers = ("car fan", "vehicle fan", "차량용 선풍기", "车载风扇", "汽车风扇")
    fan_title_markers = ("fan", "cooling", "blower", "선풍기", "风扇", "散热")
    vehicle_title_markers = ("car", "vehicle", "auto", "dashboard", "12v", "24v", "차량", "자동차", "车载", "汽车")
    if any(marker in ref for marker in car_fan_ref_markers):
        has_fan = any(marker in title_l for marker in fan_title_markers)
        has_vehicle = any(marker in title_l for marker in vehicle_title_markers)
        if not (has_fan and has_vehicle):
            return False
        rv_roof_markers = (
            "caravan", "camper", "rv", "motorhome", "roof fan", "roof vent",
            "ventilator", "ventilation fan", "hatch fan",
        )
        # Allow clearly in-cabin product wording, otherwise reject RV/roof-vent class.
        cabin_markers = ("dashboard", "headrest", "seat", "clip", "usb", "12v", "24v", "cigarette")
        if any(marker in title_l for marker in rv_roof_markers) and not any(
            marker in title_l for marker in cabin_markers
        ):
            return False

    return True


def _has_minimum_overlap(
    title: str,
    references: List[str],
    min_overlap: int = 1,
) -> bool:
    """Return True if `title` shares at least `min_overlap` distinct non-stopword
    tokens with the union of all reference strings.

    Used as a safety net at threshold=0.0 so we never accept a candidate that
    has *literally zero* tokens in common with any reference. Without this,
    relaxing min_score to 0 means any video-having product could pass the score
    gate as long as it survived the category guard.
    """
    title_tokens = _tokenize(title)
    if not title_tokens:
        return False
    ref_tokens: set = set()
    for r in references:
        if r:
            ref_tokens.update(_tokenize(r))
    if not ref_tokens:
        return False
    return len(title_tokens & ref_tokens) >= min_overlap


_B2B_MARKERS = (
    # English B2B / wholesale wording
    "wholesale", "dropshipping", "drop shipping", "bulk", "oem", "odm",
    "manufacturer", "factory", "supplier", "distributor", "reseller",
    "minimum order", "moq", "trade assurance", "sample order",
    # Korean
    "도매", "대량", "대량구매", "공장", "제조사", "공급업체", "최소주문", "최소 주문",
    # Chinese
    "批发", "工厂", "厂家", "源头", "代发", "一件代发", "供货", "供应商", "经销",
    "起订", "最小起订量", "采购", "现货批发",
)


def _b2b_signal_score(text: str) -> int:
    """Return a coarse B2B likelihood score from textual markers."""
    haystack = str(text or "")
    if not haystack:
        return 0
    lowered = haystack.lower()
    score = sum(1 for marker in _B2B_MARKERS if marker in lowered or marker in haystack)

    # Quantity-per-lot patterns often indicate wholesale listing style.
    if re.search(r"\b\d+\s*(pcs?|pieces?)\s*/\s*lot\b", lowered):
        score += 2
    if re.search(r"\b\d+\s*(pcs?|pieces?)\s*lot\b", lowered):
        score += 1
    if re.search(r"\bmin(?:imum)?\s*order\b", lowered):
        score += 2
    return score


def _looks_b2b_candidate_title(title: str) -> bool:
    """Title-only gate: skip obvious wholesale/manufacturer listing titles."""
    score = _b2b_signal_score(title)
    return score >= 2


def _looks_b2b_detail_text(page_text: str, candidate_title: str = "") -> bool:
    """Detail-page gate: stronger threshold than title-only checks."""
    page_score = _b2b_signal_score(page_text)
    title_score = _b2b_signal_score(candidate_title)
    # Be conservative: require strong page signals, or medium page + title.
    return page_score >= 4 or (page_score >= 3 and title_score >= 1)


async def _extract_page_text_for_b2b_check(tab: Any) -> str:
    """Extract compact page text for B2B-vs-B2C classification."""
    text = await tab.evaluate(
        """
        (() => {
            const title = (document.title || '').trim();
            const body = (document.body && document.body.innerText) ? document.body.innerText : '';
            const metas = [...document.querySelectorAll('meta[name], meta[property]')]
                .map((m) => (m.getAttribute('content') || '').trim())
                .filter(Boolean)
                .slice(0, 12)
                .join(' ');
            return (title + '\\n' + metas + '\\n' + body).slice(0, 18000);
        })()
        """
    )
    return str(text or "")


async def find_products_with_video(
    browser: Any,
    candidates: List[Dict[str, Any]],
    output_dir: str,
    source_label: str,
    count: int = 1,
    max_try: int = 15,
    min_score: float = MIN_SIMILARITY_SCORE,
    category_terms: Optional[List[str]] = None,
    overlap_references: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Iterate candidates, visit detail pages, find the first *count* with downloadable video.

    Candidates with similarity < min_score are skipped — they're almost certainly
    a different product category (e.g. searching "sponge holder" returning
    a phone stand because both contain "stand"/"支架" generically).

    When `min_score` is 0 (relaxed-fallback mode), we apply an additional safety
    net via `overlap_references`: the candidate title must share at least one
    distinct non-stopword token with any reference (Korean original, English
    keyword, Chinese keyword). Without this, a 0.0 threshold accepts ANY video.

    Returns list of dicts: {source, product, video_url, video_file, size_mb}
    """
    found: List[Dict[str, Any]] = []
    tried = 0
    rejected_low_score = 0

    for cand in candidates[:max_try]:
        if len(found) >= count:
            break
        detail_url = cand.get("url", "")
        if not detail_url.startswith("http"):
            continue

        cand_score = float(cand.get("score") or 0.0)
        cand_title = str(cand.get("title") or "")
        # Some search results (notably the 1688 id-only HTML fallback) arrive
        # with no title. Title-based gates below would reject ALL of them before
        # we ever load the detail page — which DOES carry the title. So when the
        # title is missing we defer every title gate to after the page loads.
        has_title = bool(cand_title.strip())
        is_image_candidate = bool(cand.get("image_search"))
        # Image-search candidates are visually pre-filtered, so allow a lower
        # text-score gate. Keep category/reference guards active below.
        effective_min_score = min_score
        if is_image_candidate and min_score >= MIN_SIMILARITY_SCORE:
            effective_min_score = max(0.05, min_score - 0.10)

        if has_title and _looks_b2b_candidate_title(cand_title):
            logger.info(
                "[ProductSearcher] [%s] skip b2b-title %s",
                source_label, cand_title[:60],
            )
            continue

        if has_title and cand_score < effective_min_score:
            rejected_low_score += 1
            logger.info(
                "[ProductSearcher] [%s] skip low-score=%.3f (<%.2f) %s",
                source_label, cand_score, effective_min_score, (cand.get("title") or "")[:50],
            )
            continue

        # Safety net for the 0.0-threshold fallback: require token overlap with
        # at least one reference. Otherwise category guards become the sole
        # filter, and an uncovered category category would let anything through.
        if has_title and min_score < 0.05 and overlap_references:
            if not _has_minimum_overlap(cand.get("title", ""), overlap_references):
                logger.info(
                    "[ProductSearcher] [%s] skip zero-overlap %s",
                    source_label, (cand.get("title") or "")[:50],
                )
                continue

        # Category guard — HARD reject if the title doesn't even mention the
        # product family. This is the single biggest reason wrong-category videos
        # ever passed (e.g. "support" matched a phone stand).
        if has_title and not _passes_category_guard(cand.get("title"), category_terms or []):
            logger.info(
                "[ProductSearcher] [%s] skip category-guard %s",
                source_label, (cand.get("title") or "")[:50],
            )
            continue

        if has_title and not _passes_reference_constraints(cand.get("title", ""), overlap_references):
            logger.info(
                "[ProductSearcher] [%s] skip reference-constraint %s",
                source_label, (cand.get("title") or "")[:50],
            )
            continue

        tried += 1
        logger.info(
            "[ProductSearcher] [%s #%d] score=%.3f %s",
            source_label, tried, cand_score, (cand.get("title") or "")[:40],
        )

        try:
            tab = await browser.get(detail_url)
            if tab is None:
                logger.warning("[ProductSearcher]   tab open failed, skip")
                continue
            # Deferred gating: candidates that had no title in the search result
            # are judged here using the title resolved from the detail page, so
            # the same category / reference / overlap gates still apply — we just
            # apply them after the (cheap) navigation instead of dropping blind.
            if not has_title:
                resolved_title = ""
                try:
                    resolved_title = str(await tab.evaluate(
                        "((document.querySelector('h1,h2') || {}).textContent"
                        " || document.title || '').trim()"
                    ) or "").strip()
                except Exception:
                    resolved_title = ""
                if not resolved_title:
                    logger.info("[ProductSearcher]   [%s] no resolvable title, skip", source_label)
                    continue
                cand_title = resolved_title
                cand["title"] = resolved_title
                cand["score"] = _multi_reference_score(
                    resolved_title, [r for r in (overlap_references or []) if r]
                )
                if _looks_b2b_candidate_title(resolved_title):
                    logger.info("[ProductSearcher] [%s] skip b2b-title(resolved) %s", source_label, resolved_title[:60])
                    continue
                if not _passes_category_guard(resolved_title, category_terms or []):
                    logger.info("[ProductSearcher] [%s] skip category-guard(resolved) %s", source_label, resolved_title[:50])
                    continue
                if not _passes_reference_constraints(resolved_title, overlap_references):
                    logger.info("[ProductSearcher] [%s] skip reference-constraint(resolved) %s", source_label, resolved_title[:50])
                    continue
                if overlap_references and not _has_minimum_overlap(resolved_title, overlap_references):
                    logger.info("[ProductSearcher] [%s] skip zero-overlap(resolved) %s", source_label, resolved_title[:50])
                    continue
            # Early B2B screening on the detail page content before expensive
            # video extraction/downloading.
            try:
                page_text = await _extract_page_text_for_b2b_check(tab)
                if _looks_b2b_detail_text(page_text, cand_title):
                    logger.info(
                        "[ProductSearcher] [%s] skip b2b-detail %s",
                        source_label, cand_title[:60],
                    )
                    continue
            except Exception:
                pass
            # Wait + scroll + click play. AliExpress / 1688 lazy-load videos:
            #  - Initial render has only image carousel
            #  - Scrolling triggers IntersectionObserver on the video module
            #  - Tapping the play button XHRs the actual video URL into runParams
            # We do MULTIPLE passes — extracting after each because the video
            # URL might appear at different points in the lifecycle.
            try:
                await asyncio.wait_for(tab.sleep(5), timeout=12)
                # Pass 1: scroll through the page to trigger every IntersectionObserver
                for y in (300, 600, 1000, 1400, 600, 0):
                    await tab.evaluate(f"window.scrollTo(0, {y})")
                    await asyncio.wait_for(tab.sleep(1.2), timeout=5)

                # Pass 2: click every conceivable play / poster trigger.
                # Run multiple times because some sites need a click to load
                # the player module first, then a second click to actually
                # play (and only the second click populates the URL).
                click_js = """
                    (() => {
                        const sels = [
                            '[class*="play" i]',
                            '[class*="Play"]',
                            '[class*="video" i] button',
                            '[class*="video" i] [role="button"]',
                            'div[class*="poster" i]',
                            'div[class*="thumb" i][class*="video" i]',
                            '[data-spm*="video"]',
                            '[aria-label*="play" i]',
                            '[aria-label*="video" i]',
                            'video',
                        ];
                        let clicked = 0;
                        for (const sel of sels) {
                            document.querySelectorAll(sel).forEach(el => {
                                try {
                                    el.click();
                                    clicked++;
                                    if (el.play) el.play().catch(()=>{});
                                } catch(e) {}
                            });
                        }
                        return clicked;
                    })()
                """
                await tab.evaluate(click_js)
                await asyncio.wait_for(tab.sleep(2), timeout=6)
                await tab.evaluate(click_js)
                await asyncio.wait_for(tab.sleep(2), timeout=6)
            except asyncio.TimeoutError:
                pass

            video_urls = await _extract_video_urls(tab)
            # If still nothing, give it ONE more long wait + extraction pass
            if not video_urls:
                try:
                    await asyncio.wait_for(tab.sleep(3), timeout=8)
                    video_urls = await _extract_video_urls(tab)
                except asyncio.TimeoutError:
                    pass
            # Mobile fallback — m.aliexpress.com / m.1688.com pages embed
            # video URLs more directly than the desktop pages and bypass
            # most lazy-load gates. Build the mobile URL from the candidate
            # ID and retry there.
            if not video_urls:
                cand_id = cand.get("id") or ""
                if cand_id and source_label == "aliexpress":
                    mobile_url = f"https://m.aliexpress.com/item/{cand_id}.html"
                    try:
                        logger.info("[ProductSearcher]   trying mobile detail: %s", mobile_url)
                        print(f"[ProductSearcher]   mobile fallback: {mobile_url}")
                        m_tab = await browser.get(mobile_url)
                        if m_tab is not None:
                            await asyncio.wait_for(m_tab.sleep(5), timeout=12)
                            try:
                                mobile_page_text = await _extract_page_text_for_b2b_check(m_tab)
                                if _looks_b2b_detail_text(mobile_page_text, cand_title):
                                    logger.info(
                                        "[ProductSearcher] [%s] skip b2b-detail-mobile %s",
                                        source_label, cand_title[:60],
                                    )
                                    continue
                            except Exception:
                                pass
                            for y in (0, 400, 800, 0):
                                await m_tab.evaluate(f"window.scrollTo(0, {y})")
                                await asyncio.wait_for(m_tab.sleep(1), timeout=4)
                            video_urls = await _extract_video_urls(m_tab)
                            if video_urls:
                                # Use mobile_url as referer for the download
                                detail_url = mobile_url
                    except Exception as e:
                        logger.info("[ProductSearcher]   mobile fallback error: %s", e)
                elif cand_id and source_label == "1688":
                    mobile_url = f"https://m.1688.com/offer/{cand_id}.html"
                    try:
                        logger.info("[ProductSearcher]   trying 1688 mobile: %s", mobile_url)
                        print(f"[ProductSearcher]   1688 mobile fallback: {mobile_url}")
                        m_tab = await browser.get(mobile_url)
                        if m_tab is not None:
                            await asyncio.wait_for(m_tab.sleep(5), timeout=12)
                            try:
                                mobile_page_text = await _extract_page_text_for_b2b_check(m_tab)
                                if _looks_b2b_detail_text(mobile_page_text, cand_title):
                                    logger.info(
                                        "[ProductSearcher] [%s] skip b2b-detail-mobile %s",
                                        source_label, cand_title[:60],
                                    )
                                    continue
                            except Exception:
                                pass
                            for y in (0, 400, 800, 0):
                                await m_tab.evaluate(f"window.scrollTo(0, {y})")
                                await asyncio.wait_for(m_tab.sleep(1), timeout=4)
                            video_urls = await _extract_video_urls(m_tab)
                            if video_urls:
                                detail_url = mobile_url
                    except Exception as e:
                        logger.info("[ProductSearcher]   1688 mobile fallback error: %s", e)

            if not video_urls:
                logger.info("[ProductSearcher]   no video, skip")
                continue

            # Try downloading
            for vurl in video_urls[:3]:
                idx = len(found) + 1
                # Unique token guards against collisions when find_products_with_video
                # is invoked more than once for the same source_label in a run
                # (initial / expanded / relaxed / image passes all use "aliexpress").
                filepath = os.path.join(
                    output_dir,
                    f"sourcing_{source_label}_{idx}_{uuid.uuid4().hex[:8]}_video.mp4",
                )
                size = await asyncio.to_thread(_download_video, vurl, filepath, detail_url)
                if size:
                    logger.info("[ProductSearcher]   downloaded %.1fMB", size)
                    found.append({
                        "source": source_label,
                        "product": cand,
                        "video_url": vurl,
                        "video_file": filepath,
                        "size_mb": size,
                    })
                    break
        except asyncio.TimeoutError:
            logger.warning("[ProductSearcher]   page load timeout, skip")
        except Exception as e:
            logger.warning("[ProductSearcher]   error visiting %s: %s", source_label, e)

    return found
