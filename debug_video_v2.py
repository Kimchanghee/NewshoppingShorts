# -*- coding: utf-8 -*-
"""Debug v2: Try alternate AliExpress URLs (not ko./not m.) to bypass the
gatewayAdapt=glo2kor redirect that strips the video player."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Test SAME items but via DIFFERENT URL forms
ITEMS = [
    "1005012018086415",  # 양념통 candidate 1
    "1005011810375225",  # 양념통 candidate 2
    "1005008690678888",  # 양념통 candidate 3
]

URL_FORMS = [
    "https://www.aliexpress.com/item/{id}.html",   # canonical .com
    "https://www.aliexpress.us/item/{id}.html",    # US-specific
    "https://m.aliexpress.com/item/{id}.html",     # mobile (was redirecting to ko)
    "https://aliexpress.com/item/{id}.html?gatewayAdapt=fr2glo",  # try forced English
]

OUT_DIR = ROOT / "logs" / f"debug_dump_v2_{datetime.now():%H%M%S}"
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def probe_url(browser, url: str, label: str):
    print(f"  [{label}] {url}")
    try:
        tab = await browser.get(url)
        if tab is None:
            return None
        await tab.sleep(5)
        # Spoof user-agent + Accept-Language to en
        await tab.evaluate("""
            try {
                Object.defineProperty(navigator, 'userAgent', { get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' });
                Object.defineProperty(navigator, 'language', { get: () => 'en-US' });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            } catch(e) {}
        """)
        # Scroll
        for y in (0, 500, 1200, 2000, 0):
            try: await tab.evaluate(f"window.scrollTo(0, {y})")
            except Exception: pass
            await tab.sleep(0.7)

        result = await tab.evaluate(r"""
            (() => {
                const out = {};
                out.final_url = location.href;
                out.video_tags = document.querySelectorAll('video').length;
                const html = document.documentElement.outerHTML;
                out.html_size = html.length;
                out.mp4_count = (html.match(/\.mp4/g) || []).length;
                out.m3u8_count = (html.match(/\.m3u8/g) || []).length;
                out.video_tag_str_count = (html.match(/<video/gi) || []).length;
                // Find every URL ending in .mp4 / .m3u8 with at least one slash before
                const re = /(https?:[^"'\s\\<>]+\.(?:mp4|m3u8)[^"'\s\\<>]*)/g;
                const urls = new Set();
                let m;
                while ((m = re.exec(html)) !== null) urls.add(m[1].substring(0, 250));
                out.video_urls = [...urls].slice(0, 5);
                // First 200 chars of <title> for sanity
                const t = document.querySelector('title');
                out.title = t ? t.textContent.substring(0, 100) : '';
                return out;
            })()
        """)
        return result
    except Exception as e:
        return {"error": str(e)}


async def main():
    from core.sourcing.pipeline import SourcingPipeline

    pipeline = SourcingPipeline(coupang_url="x", output_dir="/tmp")
    browser = await pipeline._start_browser()
    if browser is None:
        print("[!] browser start failed")
        return 1
    try:
        full_result = {}
        for item_id in ITEMS:
            print(f"\n=== {item_id} ===")
            full_result[item_id] = {}
            for form in URL_FORMS:
                url = form.format(id=item_id)
                label = url.split("//")[1].split("/")[0]
                r = await probe_url(browser, url, label)
                full_result[item_id][label] = r
                if r:
                    print(f"    final={str(r.get('final_url',''))[:80]}")
                    print(f"    title={str(r.get('title',''))[:80]}")
                    print(f"    mp4={r.get('mp4_count')}  m3u8={r.get('m3u8_count')}  <video={r.get('video_tag_str_count')}")
                    if r.get("video_urls"):
                        for u in r["video_urls"]:
                            print(f"    URL: {u[:120]}")
        out_path = OUT_DIR / "summary.json"
        out_path.write_text(json.dumps(full_result, ensure_ascii=False, indent=2))
        print(f"\n[+] saved {out_path}")
    finally:
        try: await browser.stop()
        except Exception: pass
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
