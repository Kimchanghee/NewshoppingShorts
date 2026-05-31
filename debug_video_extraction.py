# -*- coding: utf-8 -*-
"""
Debug script: open AliExpress detail pages for the 양념통 search and dump
everything that could contain a video URL. Lets us see *exactly* what video
encoding pattern the page uses so we can teach the extractor.

Usage:
    cd ~/Documents/github/NewshoppingShorts
    source .venv/bin/activate
    python debug_video_extraction.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# These are the exact 양념통 AliExpress candidates v5.1 hit but couldn't
# extract videos from. We'll dump each one's DOM/inline-JSON/data-attrs.
TARGETS = [
    # 양념통 candidates from v5.1 mobile fallback log
    "https://m.aliexpress.com/item/1005012018086415.html",
    "https://m.aliexpress.com/item/1005011810375225.html",
    "https://m.aliexpress.com/item/1005008690678888.html",
    # Plus a known-good case (sponge holder) for comparison
    "https://m.aliexpress.com/item/1005012047176301.html",
]

OUT_DIR = ROOT / "logs" / f"debug_dump_{datetime.now():%H%M%S}"
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def dump_one(browser, url: str):
    name = url.split("/")[-1].replace(".html", "")
    print(f"[+] Visiting: {url}")
    tab = await browser.get(url)
    if tab is None:
        print(f"  [!] tab open failed")
        return

    # Initial render
    await tab.sleep(5)

    # Scroll through the page to trigger lazy loads
    for y in (0, 400, 800, 1200, 1800, 2400, 1200, 0):
        try: await tab.evaluate(f"window.scrollTo(0, {y})")
        except Exception: pass
        await tab.sleep(0.8)

    # Click any play / video / poster button several times (each click might
    # advance the player state and load more)
    click_js = """
        (() => {
            const sels = [
                '[class*="play" i]', '[class*="Play"]',
                '[class*="video" i] button',
                '[class*="video" i] [role="button"]',
                'div[class*="poster" i]', 'video',
                '[aria-label*="play" i]', '[aria-label*="video" i]',
            ];
            let c = 0;
            for (const sel of sels) {
                document.querySelectorAll(sel).forEach(el => {
                    try {
                        el.click(); c++;
                        if (el.play) el.play().catch(()=>{});
                    } catch(e) {}
                });
            }
            return c;
        })()
    """
    for _ in range(3):
        try:
            n = await tab.evaluate(click_js)
            print(f"  click pass: {n} elements")
        except Exception as e:
            print(f"  click error: {e}")
        await tab.sleep(2)

    # Capture EVERYTHING that could contain video
    capture_js = r"""
        (() => {
            const out = {};
            // 1. <video> elements
            out.video_tags = [];
            document.querySelectorAll('video').forEach(v => {
                out.video_tags.push({
                    src: v.src || null,
                    currentSrc: v.currentSrc || null,
                    poster: v.poster || null,
                    sources: [...v.querySelectorAll('source')].map(s => s.src),
                    classes: v.className,
                    parentClasses: v.parentElement ? v.parentElement.className : null,
                });
            });
            // 2. data-* attrs containing video/mp4/m3u8
            out.data_attrs = [];
            document.querySelectorAll('*').forEach(el => {
                for (const a of el.attributes) {
                    const v = a.value || '';
                    if (/video|\.mp4|\.m3u8|\.webm|playUrl|videoUrl/i.test(v) && v.length < 1000) {
                        out.data_attrs.push({tag: el.tagName, attr: a.name, val: v.substring(0, 300)});
                        if (out.data_attrs.length > 100) break;
                    }
                }
            });
            // 3. iframes (sometimes player is in iframe)
            out.iframes = [];
            document.querySelectorAll('iframe').forEach(f => {
                out.iframes.push(f.src || f.getAttribute('data-src') || '');
            });
            // 4. URL bar / final URL after redirects
            out.final_url = window.location.href;
            // 5. Scrape window-level JS variables that AliExpress is known to
            //    populate
            try {
                const probe = (obj, path, depth) => {
                    if (depth > 5 || !obj || typeof obj !== 'object') return;
                    for (const k in obj) {
                        try {
                            const v = obj[k];
                            const p = path + '.' + k;
                            if (typeof v === 'string' && v.length > 4
                                && /\.mp4|\.m3u8|videoPath|videoUrl|playUrl/i.test(v)) {
                                out._js_strings = out._js_strings || [];
                                out._js_strings.push({path: p.substring(0,100), val: v.substring(0, 300)});
                            } else if (typeof v === 'object' && v !== null) {
                                if (out._js_strings && out._js_strings.length > 50) return;
                                probe(v, p, depth + 1);
                            }
                        } catch(e) {}
                    }
                };
                if (window.runParams) probe(window.runParams, 'runParams', 0);
                if (window.detailData) probe(window.detailData, 'detailData', 0);
                if (window.__INIT_DATA__) probe(window.__INIT_DATA__, '__INIT_DATA__', 0);
                if (window._dida_config) probe(window._dida_config, '_dida_config', 0);
            } catch(e) { out._probe_error = String(e); }

            // 6. Search inline <script> tags for video-like strings
            out.inline_script_hits = [];
            document.querySelectorAll('script').forEach((s, i) => {
                if (!s.textContent) return;
                if (s.textContent.length > 300000) return; // skip huge libs
                const re = /(https?:[^"'\s\\]{15,300}\.(mp4|m3u8|webm)[^"'\s\\]*)/g;
                let m;
                while ((m = re.exec(s.textContent)) !== null) {
                    out.inline_script_hits.push({script_idx: i, url: m[1].substring(0, 300)});
                    if (out.inline_script_hits.length > 50) break;
                }
                // Also any "videoUrl" / "playUrl" string
                const re2 = /"(?:videoUrl|videoPath|playUrl|playerUrl|video_url|mp4Url|videoUri|videoSrc)"\s*:\s*"([^"]{5,300})"/g;
                while ((m = re2.exec(s.textContent)) !== null) {
                    out.inline_script_hits.push({script_idx: i, kind: 'json_key', val: m[1].substring(0, 300)});
                    if (out.inline_script_hits.length > 80) break;
                }
            });

            return out;
        })()
    """
    try:
        result = await tab.evaluate(capture_js)
    except Exception as e:
        print(f"  [!] capture error: {e}")
        return

    # Save full HTML too
    try:
        html = await tab.evaluate("document.documentElement.outerHTML")
    except Exception:
        html = ""

    out_path = OUT_DIR / f"{name}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"  saved: {out_path}")

    if html:
        html_path = OUT_DIR / f"{name}.html"
        html_path.write_text(html)
        print(f"  saved: {html_path} ({len(html):,} bytes)")


async def main():
    from core.sourcing.pipeline import SourcingPipeline

    pipeline = SourcingPipeline(coupang_url="x", output_dir="/tmp")
    browser = await pipeline._start_browser()
    if browser is None:
        print("[!] browser start failed")
        return 1
    try:
        for url in TARGETS:
            try:
                await dump_one(browser, url)
            except Exception as e:
                print(f"  [!] dump failed for {url}: {e}")
            print()
    finally:
        try: await browser.stop()
        except Exception: pass

    print(f"\n[+] Dumps in: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
