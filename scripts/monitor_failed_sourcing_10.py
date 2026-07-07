from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Keep this diagnostic bounded. Environment must be set before importing the
# pipeline modules because they read these values at import time.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SSMAKER_DISABLE_FASTER_WHISPER", "1")
os.environ.setdefault("SSMAKER_MARKETPLACE_SEARCH_STAGE_TIMEOUT", "45")
os.environ.setdefault("SSMAKER_MARKETPLACE_VIDEO_SCAN_TIMEOUT", "90")
os.environ.setdefault("SSMAKER_DOWNLOAD_MAX_SECONDS", "45")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.api import ApiKeyManager
from core.sourcing.pipeline import SourcingPipeline


QUEUE_PATH = Path.home() / ".ssmaker" / "summer_coupang_autosourcing_queue_20260603.json"
RUN_LABEL = os.environ.get("SSMAKER_MONITOR_LABEL", "failed10_monitor").strip() or "failed10_monitor"
OUT_ROOT = Path.home() / ".ssmaker" / "sourcing_output" / (
    RUN_LABEL + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
)
REPORT_PATH = OUT_ROOT / "summary.json"
LOG_PATH = OUT_ROOT / "monitor.log"

DEFAULT_PLANNED_NUMBERS = [
    "[080]",
    "[082]",
    "[083]",
    "[096]",
    "[101]",
    "[102]",
    "[113]",
    "[114]",
    "[123]",
    "[126]",
]


def _planned_numbers() -> List[str]:
    raw = os.environ.get("SSMAKER_MONITOR_PLANNED_NUMBERS", "").strip()
    if not raw:
        return DEFAULT_PLANNED_NUMBERS
    return [part.strip() for part in raw.split(",") if part.strip()]


def _append_log(message: str) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _load_queue_items() -> List[Dict[str, Any]]:
    payload = json.loads(QUEUE_PATH.read_text(encoding="utf-8-sig"))
    by_number = {str(item.get("planned_number")): item for item in payload.get("items", [])}
    return [by_number[number] for number in _planned_numbers() if number in by_number]


def _gemini_client() -> Any:
    try:
        from google import genai

        key = ApiKeyManager.APIKeyManager(use_secrets_manager=True).get_available_key()
        return genai.Client(api_key=key) if key else None
    except Exception as exc:
        _append_log(f"gemini_client_unavailable: {exc}")
        return None


def _result_from_report(item: Dict[str, Any], report: Dict[str, Any], elapsed: float) -> Dict[str, Any]:
    sourced = report.get("sourced_products") or []
    diagnostics = report.get("search_diagnostics") or {}
    counts = diagnostics.get("counts") or {}
    videos = [
        {
            "source": row.get("source"),
            "title": (row.get("product") or {}).get("title") or row.get("title"),
            "video_file": row.get("video_file"),
            "score": (row.get("product") or {}).get("score") or row.get("score"),
            "size_mb": row.get("size_mb"),
        }
        for row in sourced
    ]
    return {
        "planned_number": item.get("planned_number"),
        "product_name": item.get("product_name"),
        "category": item.get("category"),
        "success": bool(report.get("success")),
        "match_status": report.get("match_status"),
        "error": report.get("error"),
        "elapsed_seconds": round(elapsed, 1),
        "candidate_counts": counts,
        "access_challenges": diagnostics.get("access_challenges") or [],
        "category_terms": diagnostics.get("category_terms") or [],
        "video_count": len(sourced),
        "videos": videos,
        "report_path": report.get("_report_path"),
    }


async def _run_one(item: Dict[str, Any], index: int, total: int, client: Any) -> Dict[str, Any]:
    planned = str(item.get("planned_number") or f"item{index}")
    safe_number = planned.strip("[]") or str(index)
    out_dir = OUT_ROOT / safe_number / "sourcing"
    out_dir.mkdir(parents=True, exist_ok=True)

    _append_log(f"START {index}/{total} {planned} {item.get('category')} {item.get('product_name')}")
    started = datetime.now()

    def progress(step: str, message: str, value: float) -> None:
        _append_log(f"{planned} {step} {int(value * 100)}% {message}")

    pipeline = SourcingPipeline(
        coupang_url=str(item.get("coupang_url") or ""),
        output_dir=str(out_dir),
        on_progress=progress,
        gemini_client=client,
        min_similarity_score=float(item.get("min_similarity_score") or 0.9),
        enforce_min_similarity=True,
        fallback_product_name=str(item.get("product_name") or ""),
        fallback_category=str(item.get("category") or ""),
    )
    success = False
    try:
        success = await asyncio.wait_for(pipeline.run_sourcing(), timeout=210)
    except asyncio.TimeoutError:
        pipeline.error = "monitor_timeout_210s"
    except Exception as exc:
        pipeline.error = f"{type(exc).__name__}: {exc}"

    report = pipeline.get_report()
    report["success"] = bool(success)
    report["planned_number"] = planned
    report["queue_product_name"] = item.get("product_name", "")
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["_report_path"] = str(report_path)

    elapsed = (datetime.now() - started).total_seconds()
    result = _result_from_report(item, report, elapsed)
    _append_log(
        "DONE "
        f"{planned} success={result['success']} match={result['match_status']} "
        f"videos={result['video_count']} counts={result['candidate_counts']} "
        f"error={result['error']}"
    )
    return result


async def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    items = _load_queue_items()
    client = _gemini_client()
    results: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        result = await _run_one(item, index, len(items), client)
        results.append(result)
        REPORT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    _append_log(f"SUMMARY {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
