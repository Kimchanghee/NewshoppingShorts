# -*- coding: utf-8 -*-
"""Debug: search 1688 for 양념통 candidates and dump their detail pages.
1688 is a Chinese site so it's NOT subject to the AliExpress ko redirect."""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "logs" / f"debug_1688_{datetime.now():%H%M%S}"
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def main():
    from core.sourcing.pipeline import SourcingPipeline
    from core.sourcing.product_searcher import _do_1688_search

    pipeline = SourcingPipeline(coupang_url="x", output_dir="/tmp")
    browser = await pipeline._start_browser()
    if browser is None:
        return 1

    try:
        # Search 1688 for 양념통 — try with AND without video filter so we
        # see whether 1688 itself has any items in this category at all.
        print("[+] Searching 1688 with VIDEO filter...")
        results_v = await _do_1688_search(browser, "调味料盒", "head-noun", video_filter=True)
        print(f"[+] VIDEO filter: {len(results_v)} candidates")

        print("[+] Searching 1688 WITHOUT filter...")
        results = await _do_1688_search(browser, "调味料盒", "head-noun", video_filter=False)
        print(f"[+] No filter: {len(results)} candidates")

        # If video filter returned >0, prefer those; else use unfiltered
        if results_v:
            results = results_v

        # Take top 5 and dump their detail pages
        for i, cand in enumerate(results[:5], start=1):
            cid = cand.get("id", "")
            curl = cand.get("url", "")
            title = (cand.get("title") or "")[:60]
            print(f"\n[{i}/5] {cid}: {title}")
            print(f"      {curl}")

            try:
                tab = await browser.get(curl)
                if tab is None:
                    print(f"      tab open failed")
                    continue
                await tab.sleep(6)
                # Scroll
                for y in (0, 500, 1200, 2000, 0):
                    try: await tab.evaluate(f"window.scrollTo(0, {y})")
                    except Exception: pass
                    await tab.sleep(0.7)
                # Try clicks
                try:
                    await tab.evaluate("""
                        document.querySelectorAll(
                            'video, [class*="play" i], [class*="video" i], [class*="poster" i]'
                        ).forEach(el => { try { el.click(); } catch(e) {} });
                    """)
                except Exception: pass
                await tab.sleep(3)

                result = await tab.evaluate(r"""
                    (() => {
                        const out = {};
                        out.final_url = location.href;
                        const html = document.documentElement.outerHTML;
                        out.html_size = html.length;
                        out.mp4_count = (html.match(/\.mp4/g) || []).length;
                        out.m3u8_count = (html.match(/\.m3u8/g) || []).length;
                        out.video_tags = document.querySelectorAll('video').length;
                        out.title = (document.querySelector('title') || {}).textContent || '';
                        // Extract any video URLs found
                        const re = /(https?:[^"'\s\\<>]+\.(?:mp4|m3u8)[^"'\s\\<>]*)/g;
                        const urls = new Set();
                        let m;
                        while ((m = re.exec(html)) !== null) urls.add(m[1].substring(0, 250));
                        out.video_urls = [...urls].slice(0, 10);
                        // Check for login wall
                        out.is_login = /login\.taobao\.com|login\.1688\.com|login\.alibaba/i.test(location.href);
                        // Look for 1688-specific video markers
                        out.video_pic_count = (html.match(/videoPic/g) || []).length;
                        out.cdn_video_count = (html.match(/cloud\.video\.taobao\.com/g) || []).length;
                        return out;
                    })()
                """)
                print(f"      final={result.get('final_url', '')[:100]}")
                print(f"      title={result.get('title', '')[:80]}")
                print(f"      mp4={result.get('mp4_count')} m3u8={result.get('m3u8_count')} <video={result.get('video_tags')}")
                print(f"      videoPic={result.get('video_pic_count')} taoCDN={result.get('cdn_video_count')} login={result.get('is_login')}")
                if result.get("video_urls"):
                    for u in result["video_urls"][:3]:
                        print(f"      URL: {u}")

                # Save HTML
                html = await tab.evaluate("document.documentElement.outerHTML")
                if html:
                    (OUT_DIR / f"{cid}.html").write_text(html)
                (OUT_DIR / f"{cid}.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2)
                )
            except Exception as e:
                print(f"      error: {e}")

        print(f"\n[+] dumps in: {OUT_DIR}")
    finally:
        try: await browser.stop()
        except Exception: pass
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
