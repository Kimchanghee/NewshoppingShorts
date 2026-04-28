# -*- coding: utf-8 -*-
"""
Standalone Linktree publisher for the 5-product kitchen batch.

The matching batch (run_batch_5_kitchen.command) sources videos and uploads
to YouTube but doesn't publish to Linktree — that step is handled here so the
publish counter increments [1] → [5] in run order.

Usage:
    cd ~/Documents/github/NewshoppingShorts
    source .venv/bin/activate
    python run_linktree_publish_5_kitchen.py

Reads URLs from run_batch_5_kitchen.command (so the source-of-truth list lives
in one place) and uses the same Coupang scraper to fetch product names for
the Linktree card titles.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def _load_urls_from_batch_command() -> list[str]:
    """Pull the URLs out of run_batch_5_kitchen.command so we don't duplicate them."""
    cmd = (ROOT / "run_batch_5_kitchen.command").read_text(encoding="utf-8")
    # Match anything between the URLs=( and the matching )
    m = re.search(r"URLs=\(\s*(.*?)\s*\)", cmd, re.DOTALL)
    if not m:
        raise SystemExit("Could not find URLs=( ... ) block in run_batch_5_kitchen.command")
    raw = m.group(1)
    urls = [line.strip().strip('"') for line in raw.splitlines() if line.strip()]
    return [u for u in urls if u.startswith("http")]


async def _scrape_name(coupang_url: str) -> str:
    """Reuse the same Coupang scraper the pipeline uses."""
    from core.sourcing.coupang_scraper import scrape_product
    from core.sourcing.pipeline import SourcingPipeline

    # Use SourcingPipeline._start_browser to share the same browser launch logic
    pipeline = SourcingPipeline(coupang_url=coupang_url, output_dir="/tmp")
    browser = await pipeline._start_browser()
    if browser is None:
        return ""
    try:
        info = await scrape_product(browser, coupang_url)
        return (info or {}).get("name", "") if info else ""
    finally:
        try:
            await browser.stop()
        except Exception:
            pass


def _try_generate_deep_link(coupang_url: str) -> str:
    """Use Coupang Partners API to generate a deep link, falling back to the raw URL."""
    try:
        from managers.coupang_manager import get_coupang_manager
        cm = get_coupang_manager()
        if cm.is_connected():
            dl = cm.generate_deep_link(coupang_url)
            if dl:
                return dl
    except Exception as e:
        print(f"  [!] deep link error: {e}")
    return coupang_url


async def main() -> int:
    from managers.linktree_manager import get_linktree_manager

    urls = _load_urls_from_batch_command()
    print(f"[+] Loaded {len(urls)} URLs from run_batch_5_kitchen.command")

    lm = get_linktree_manager()
    if not lm.is_connected():
        print("[!] Linktree webhook URL이 설정되지 않았습니다.")
        print("    설정 → 링크트리 탭에서 webhook URL을 입력해주세요.")
        return 1

    # Reset publish counter so this run starts at [1].
    lm.reset_publish_counter()
    print("[+] Linktree publish counter reset → next publish = [1]")

    results = []
    for idx, url in enumerate(urls, start=1):
        print()
        print("=" * 70)
        print(f"  [{idx}/{len(urls)}] Processing: {url}")
        print("=" * 70)

        # 1) Get product name via Coupang scrape
        name = await _scrape_name(url)
        if not name:
            print(f"  [!] Failed to scrape product name — skipping")
            results.append({"idx": idx, "url": url, "ok": False, "reason": "scrape_failed"})
            continue
        print(f"  [+] Product: {name[:80]}")

        # 2) Generate deep link (or fall back to raw URL)
        deep_link = _try_generate_deep_link(url)
        if deep_link == url:
            print(f"  [!] Coupang Partners not connected — using raw URL")
        else:
            print(f"  [+] Deep link: {deep_link[:80]}")

        # 3) Publish to Linktree
        ok = lm.publish_coupang_link(
            product_name=name,
            coupang_url=deep_link,
            source_url=url,
        )
        if ok:
            print(f"  [✓] Published to Linktree as [{idx}] {lm._build_concise_product_title(name)}")
        else:
            print(f"  [✗] Linktree publish failed")
        results.append({"idx": idx, "url": url, "name": name, "ok": ok})

        # Small delay so the webhook receiver doesn't see a thundering herd
        time.sleep(2)

    # Summary
    print()
    print("=" * 70)
    print("  Linktree publish summary")
    print("=" * 70)
    ok_count = sum(1 for r in results if r.get("ok"))
    for r in results:
        status = "OK " if r.get("ok") else "FAIL"
        print(f"  [{r['idx']}] {status} — {(r.get('name') or r['url'])[:70]}")
    print()
    print(f"  Result: {ok_count}/{len(results)} successful")

    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n[*] User interrupted")
        sys.exit(130)
