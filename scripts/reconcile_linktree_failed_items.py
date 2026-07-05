"""Reconcile Linktree publish statuses against the live public page.

Items marked ``failed_linktree_publish`` (or still in a retry state) whose card
actually exists on the public Linktree page are corrected to ``completed``.
Items whose card is genuinely missing are re-armed as ``linktree_retry_pending``
with their retry budget reset, so the runner re-publishes just the Linktree
card (the YouTube upload is kept).

The queue file is backed up next to the original before any change.

Usage:
    python scripts/reconcile_linktree_failed_items.py            # apply
    python scripts/reconcile_linktree_failed_items.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

QUEUE_PATH = Path.home() / ".ssmaker" / "summer_coupang_autosourcing_queue_20260603.json"
PROFILE_URL = "https://linktr.ee/studio.idol"
FIXABLE_STATUSES = {
    "failed_linktree_publish",
    "completed_linktree_blocked",
    "linktree_retry_pending",
}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)


def fetch_profile_html() -> str:
    request = urllib.request.Request(PROFILE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def item_marker(item: Dict[str, Any]) -> str:
    match = re.search(r"\d+", str(item.get("planned_number") or ""))
    return f"[{match.group().zfill(3)}]" if match else ""


def item_purchase_url(item: Dict[str, Any]) -> str:
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    linktree_result = (
        result.get("linktree_result")
        if isinstance(result.get("linktree_result"), dict)
        else {}
    )
    return str(
        linktree_result.get("purchase_url")
        or result.get("purchase_url")
        or item.get("affiliate_url")
        or ""
    ).strip()


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    payload = json.loads(QUEUE_PATH.read_text(encoding="utf-8-sig"))
    html = fetch_profile_html()
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    corrected: List[str] = []
    rearmed: List[str] = []
    unresolved: List[str] = []

    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status not in FIXABLE_STATUSES:
            continue
        marker = item_marker(item)
        purchase_url = item_purchase_url(item)
        if not purchase_url:
            unresolved.append(f"{marker} (no purchase_url)")
            continue

        result = dict(item.get("result") or {})
        linktree_result = dict(result.get("linktree_result") or {})
        if (not marker or marker in html) and purchase_url in html:
            item["status"] = "completed"
            linktree_result.update(
                {
                    "ok": True,
                    "method": "public_existing_reconciled",
                    "blocking_reason": "",
                    "reconciled_at": now,
                }
            )
            result.update(
                {
                    "linktree_result": linktree_result,
                    "blocking_reason": "",
                    "updated_at": now,
                }
            )
            item["result"] = result
            corrected.append(marker)
        else:
            item["status"] = "linktree_retry_pending"
            item["attempts"] = 1  # original run only; grants one fresh retry
            linktree_result.update(
                {
                    "ok": False,
                    "blocking_reason": (
                        "Card not found on the public page during reconcile; "
                        "re-armed for one Linktree-only retry."
                    ),
                    "reconciled_at": now,
                }
            )
            result.update({"linktree_result": linktree_result, "updated_at": now})
            item["result"] = result
            rearmed.append(marker)

    summary = {
        "dry_run": args.dry_run,
        "corrected_to_completed": corrected,
        "rearmed_for_retry": rearmed,
        "unresolved": unresolved,
    }
    if not args.dry_run and (corrected or rearmed):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = QUEUE_PATH.with_name(
            QUEUE_PATH.name + f".backup_before_linktree_reconcile_{stamp}"
        )
        shutil.copy2(QUEUE_PATH, backup)
        QUEUE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summary["backup"] = str(backup)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
