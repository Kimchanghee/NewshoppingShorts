"""Report-only audit: are Linktree cards in sync with live YouTube videos?

Checks three sources and reports mismatches (never modifies anything):
  1. Public Linktree page cards (number markers + URLs)
  2. Queue file items (planned number -> youtube_url / affiliate URL)
  3. The YouTube channel's uploads playlist (which videos actually exist)

Rules reported:
  - card_without_video : numbered card whose number has no live video -> archive it
  - video_without_card : live video whose number has no card -> publish it
  - card_raw_url       : kept card that links a raw coupang URL (no commission)
  - non_numbered       : cards without [NNN] marker (never touched by automation)

Usage:
    python scripts/audit_linktree_youtube_sync.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

PROFILE_URL = "https://linktr.ee/studio.idol"
CHANNEL_HANDLE = "@todayshopping-u2c"
QUEUE_PATH = Path.home() / ".ssmaker" / "summer_coupang_autosourcing_queue_20260603.json"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
    )
}


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={**UA, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def linktree_cards() -> list:
    html = fetch(f"{PROFILE_URL}?ssmaker_ts={int(time.time() * 1000)}")
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
        html,
        re.S,
    )
    if not match:
        return []
    data = json.loads(match.group(1))

    def find_links(obj, depth=0):
        if depth > 8:
            return None
        if isinstance(obj, list):
            for value in obj:
                result = find_links(value, depth + 1)
                if result:
                    return result
            return None
        if isinstance(obj, dict):
            links = obj.get("links")
            if isinstance(links, list) and links and isinstance(links[0], dict) and "title" in links[0]:
                return links
            for value in obj.values():
                result = find_links(value, depth + 1)
                if result:
                    return result
        return None

    cards = []
    for link in find_links(data.get("props", {})) or []:
        title = str(link.get("title") or "")
        number = re.search(r"\[(\d{1,3})\]", title)
        cards.append(
            {
                "id": link.get("id"),
                "title": title[:60],
                "url": str(link.get("url") or ""),
                "num": number.group(1).zfill(3) if number else "",
            }
        )
    return cards


def queue_map() -> dict:
    payload = json.loads(QUEUE_PATH.read_text(encoding="utf-8-sig"))
    items = {}
    for item in payload.get("items", []):
        match = re.search(r"\d+", str(item.get("planned_number") or ""))
        if not match:
            continue
        result = item.get("result") or {}
        youtube_url = str(result.get("youtube_url") or "") or str(
            (result.get("youtube") or {}).get("video_url") or ""
        )
        items[match.group().zfill(3)] = {
            "status": item.get("status"),
            "yt": youtube_url,
            "urls": {
                str(item.get("affiliate_url") or "").strip(),
                str(result.get("purchase_url") or "").strip(),
                str(item.get("coupang_url") or "").strip(),
            }
            - {""},
        }
    return items


def channel_video_ids() -> set:
    html = fetch(f"https://www.youtube.com/{CHANNEL_HANDLE}/shorts")
    match = re.search(r'"externalId":"(UC[^"]+)"', html) or re.search(
        r'"browseId":"(UC[A-Za-z0-9_-]+)"', html
    )
    ids = set(re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html))
    if match:
        playlist = fetch(f"https://www.youtube.com/playlist?list=UU{match.group(1)[2:]}")
        ids.update(re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', playlist))
    return ids


def video_id(url: str) -> str:
    match = re.search(r"(?:youtu\.be/|v=|shorts/)([A-Za-z0-9_-]{11})", url or "")
    return match.group(1) if match else ""


def main() -> int:
    cards = linktree_cards()
    items = queue_map()
    channel = channel_video_ids()

    live_nums = {n for n, v in items.items() if v["yt"] and video_id(v["yt"]) in channel}
    report = {
        "cards_total": len(cards),
        "channel_videos": len(channel),
        "live_numbered_videos": len(live_nums),
        "card_without_video": [],
        "video_without_card": [],
        "card_raw_url": [],
        "non_numbered": [],
    }
    for card in cards:
        if not card["num"]:
            report["non_numbered"].append(card["title"])
            continue
        if card["num"] not in live_nums:
            report["card_without_video"].append(f"[{card['num']}] {card['title'][:30]}")
        elif "link.coupang.com" not in card["url"]:
            report["card_raw_url"].append(f"[{card['num']}] {card['url'][:60]}")
    card_nums = {card["num"] for card in cards if card["num"]}
    report["video_without_card"] = sorted(n for n in live_nums if n not in card_nums)
    report["in_sync"] = not report["card_without_video"] and not report["video_without_card"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
