"""
AliExpress / 1688 product searcher using zendriver (CDP).
Searches by keyword, finds products with videos, downloads them.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, List, Optional

import requests

from utils.logging_config import get_logger

logger = get_logger(__name__)


def _similarity_score(name1: str, name2: str) -> float:
    """Token-based Jaccard similarity supporting CJK + Latin."""
    if not name1 or not name2:
        return 0.0

    def _tokenize(s: str):
        s = s.lower()
        tokens = set(re.findall(r'[\u4e00-\u9fff]+|[\uac00-\ud7af]+|[a-z]+|\d+', s))
        chars = set()
        for t in list(tokens):
            if re.match(r'[\u4e00-\u9fff]', t):
                chars.update(t)
        tokens.update(chars)
        return tokens

    t1, t2 = _tokenize(name1), _tokenize(name2)
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


async def _extract_video_urls(tab: Any) -> List[str]:
    """Extract video URLs from a product detail page."""
    return await tab.evaluate("""
        (() => {
            const urls = new Set();
            document.querySelectorAll('video').forEach(v => {
                if (v.src) urls.add(v.src);
                if (v.currentSrc) urls.add(v.currentSrc);
                v.querySelectorAll('source').forEach(s => { if (s.src) urls.add(s.src); });
            });
            const html = document.documentElement.innerHTML;
            [
                /"(https?:\\/\\/[^"]*?\\.mp4[^"]*?)"/g,
                /"videoUrl"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"video_url"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"contentUrl"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /(https?:\\/\\/cloud\\.video\\.taobao\\.com[^\\s"']+)/g,
            ].forEach(p => { let m; while ((m = p.exec(html)) !== null) urls.add(m[1]); });
            document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                try {
                    const d = JSON.parse(s.textContent);
                    if (d['@type'] === 'VideoObject' && d.contentUrl) urls.add(d.contentUrl);
                } catch(e) {}
            });
            return [...urls].slice(0, 10);
        })()
    """) or []


def _download_video(url: str, filepath: str, referer: str, max_retries: int = 2) -> Optional[float]:
    """Download video file with retry. Returns size in MB or None on failure."""
    import time

    for attempt in range(1, max_retries + 1):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": referer,
            }
            r = requests.get(url, headers=headers, timeout=60, stream=True)
            if r.status_code != 200:
                logger.warning("[ProductSearcher] Download HTTP %d (attempt %d/%d): %s",
                               r.status_code, attempt, max_retries, url[:80])
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None

            total = 0
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    total += len(chunk)

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


async def search_aliexpress(
    browser: Any,
    keyword_en: str,
    reference_name: str,
    keyword_cn: str = "",
) -> List[Dict[str, Any]]:
    """
    Search AliExpress and return product candidates sorted by similarity.
    """
    import urllib.parse
    url = f"https://www.aliexpress.com/wholesale?SearchText={urllib.parse.quote(keyword_en)}"
    logger.info("[ProductSearcher] AliExpress search: %s", keyword_en)

    tab = await browser.get(url)
    await tab.sleep(7)

    raw = await tab.evaluate("""
        (() => {
            const seen = new Set();
            const items = [];
            document.querySelectorAll('a[href*="/item/"]').forEach(a => {
                if (items.length >= 20) return;
                const match = a.href.match(/item\\/(\\d+)/);
                if (!match || seen.has(match[1])) return;
                seen.add(match[1]);
                const card = a.closest('[class*="card"], [class*="Card"], [class*="product"], [class*="snippet"]') || a.parentElement;
                const img = card ? card.querySelector('img') : null;
                const priceEl = card ? card.querySelector('[class*="price"], [class*="Price"]') : null;
                const titleEl = card ? (card.querySelector('h1, h2, h3, [class*="title"], [class*="Title"]') || a) : a;
                items.push({
                    id: match[1],
                    title: titleEl ? titleEl.textContent.trim().substring(0, 120) : null,
                    price: priceEl ? priceEl.textContent.trim() : null,
                    image: img ? img.src : null,
                    url: 'https://ko.aliexpress.com/item/' + match[1] + '.html'
                });
            });
            return items;
        })()
    """) or []

    # Score and sort
    candidates = []
    for p in raw:
        score = max(
            _similarity_score(reference_name, p.get("title", "")),
            _similarity_score(keyword_en, p.get("title", "")),
        )
        candidates.append({**p, "score": score, "source": "aliexpress"})
    candidates.sort(key=lambda x: x["score"], reverse=True)

    logger.info("[ProductSearcher] AliExpress: %d candidates", len(candidates))
    return candidates


async def search_1688(
    browser: Any,
    keyword_cn: str,
    reference_name: str,
) -> List[Dict[str, Any]]:
    """
    Search 1688. Returns empty list if login is required.
    """
    import urllib.parse
    url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={urllib.parse.quote(keyword_cn)}"
    logger.info("[ProductSearcher] 1688 search: %s", keyword_cn)

    tab = await browser.get(url)
    await tab.sleep(5)

    # Check login redirect
    current_url = await tab.evaluate("window.location.href") or ""
    if "login.taobao.com" in current_url or "login.1688.com" in current_url:
        logger.info("[ProductSearcher] 1688 requires login – skipping")
        return []

    # Scroll for more results
    await tab.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    await tab.sleep(2)
    await tab.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await tab.sleep(2)

    raw = await tab.evaluate("""
        (() => {
            const results = [];
            const seen = new Set();
            document.querySelectorAll('a[href*="detail.1688.com"], a[href*="offer/"], a[href*="offerId"]').forEach(a => {
                if (results.length >= 30) return;
                const href = a.href || '';
                let oid = null;
                let m = href.match(/offer\\/(\\d{10,})/);
                if (m) oid = m[1];
                if (!oid) { m = href.match(/offerId[=:](\\d{10,})/); if (m) oid = m[1]; }
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
            return results;
        })()
    """) or []

    candidates = []
    for p in raw:
        score = max(
            _similarity_score(reference_name, p.get("title", "")),
            _similarity_score(keyword_cn, p.get("title", "")),
        )
        candidates.append({**p, "score": score, "source": "1688"})
    candidates.sort(key=lambda x: x["score"], reverse=True)

    logger.info("[ProductSearcher] 1688: %d candidates", len(candidates))
    return candidates


async def find_products_with_video(
    browser: Any,
    candidates: List[Dict[str, Any]],
    output_dir: str,
    source_label: str,
    count: int = 1,
    max_try: int = 10,
) -> List[Dict[str, Any]]:
    """
    Iterate candidates, visit detail pages, find the first *count* with downloadable video.

    Returns list of dicts: {source, product, video_url, video_file, size_mb}
    """
    found: List[Dict[str, Any]] = []
    tried = 0

    for cand in candidates[:max_try]:
        if len(found) >= count:
            break
        detail_url = cand.get("url", "")
        if not detail_url.startswith("http"):
            continue

        tried += 1
        logger.info(
            "[ProductSearcher] [%s #%d] score=%.3f %s",
            source_label, tried, cand["score"], (cand.get("title") or "")[:40],
        )

        try:
            tab = await browser.get(detail_url)
            if tab is None:
                logger.warning("[ProductSearcher]   tab open failed, skip")
                continue
            await asyncio.wait_for(tab.sleep(5), timeout=15)

            video_urls = await _extract_video_urls(tab)
            if not video_urls:
                logger.info("[ProductSearcher]   no video, skip")
                continue

            # Try downloading
            for vurl in video_urls[:3]:
                idx = len(found) + 1
                filepath = os.path.join(output_dir, f"sourcing_{source_label}_{idx}_video.mp4")
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
