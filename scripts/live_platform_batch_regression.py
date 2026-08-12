# -*- coding: utf-8 -*-
"""Run download-only platform sourcing for a JSON list of Coupang products.

This is a live regression utility: it searches and downloads source video but
never edits, renders, uploads, publishes, or consumes a source reservation.
The summary is rewritten after every case so a browser/network failure cannot
erase evidence from already completed cases.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from utils.utf8_boot import force_utf8

    force_utf8()
except Exception:
    pass


def _gemini_client() -> Any:
    try:
        from google import genai
        from core.api import ApiKeyManager

        key = ApiKeyManager.APIKeyManager(use_secrets_manager=True).get_available_key()
        return genai.Client(api_key=key) if key else None
    except Exception:
        return None


def _probe_video(path: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "exists": False,
        "size_mb": 0.0,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "duration_sec": 0.0,
        "decode_ok": False,
    }
    if not path or not os.path.isfile(path):
        return result
    result["exists"] = True
    result["size_mb"] = round(os.path.getsize(path) / 1_000_000, 3)
    try:
        import cv2

        cap = cv2.VideoCapture(path)
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            ok, _ = cap.read()
            result.update(
                width=width,
                height=height,
                fps=round(fps, 3),
                duration_sec=round(frames / fps, 3) if fps > 0 else 0.0,
                decode_ok=bool(ok),
            )
        finally:
            cap.release()
    except Exception as exc:
        result["probe_error"] = str(exc)
    return result


def _required_relevance_score(value: Any) -> float:
    try:
        required = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "required relevance score must be finite and within 0.70..1.0"
        ) from exc
    if not math.isfinite(required) or not 0.70 <= required <= 1.0:
        raise ValueError(
            "required relevance score must be finite and within 0.70..1.0"
        )
    return required


def _safe_case_slug(value: Any) -> str:
    safe = re.sub(r"[^\w-]+", "_", str(value or "product"), flags=re.UNICODE)
    return safe.strip("_-")[:80] or "product"


def _meets_relevance_threshold(score: Any, required_score: float) -> bool:
    """Fail closed when a live result does not meet the requested QA gate."""
    try:
        score_value = float(score)
        required_value = _required_relevance_score(required_score)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(score_value) or not 0.0 <= score_value <= 1.0:
        return False
    return score_value >= required_value


def _write_summary(path: Path, started_at: str, results: list[dict[str, Any]]) -> None:
    succeeded = sum(
        1
        for item in results
        if item.get("ok") and (item.get("media") or {}).get("decode_ok")
    )
    payload = {
        "started_at": started_at,
        "updated_at": datetime.now().astimezone().isoformat(),
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def _run(args: argparse.Namespace) -> int:
    from core.sourcing.platform_pipeline import run_platform_sourcing
    from core.sourcing.platform_shorts_searcher import start_browser

    cases = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("input JSON must contain a non-empty list")

    started_at = datetime.now().astimezone().isoformat()
    required_relevance_score = _required_relevance_score(args.min_similarity)
    run_dir = Path(args.output) / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "live_platform_summary.json"
    try:
        from utils.logging_config import AppLogger

        AppLogger.setup(log_dir=run_dir, level="INFO", console_level="INFO")
    except Exception:
        pass
    platforms = [part.strip() for part in args.platforms.split(",") if part.strip()]
    gemini = None if args.no_gemini else _gemini_client()
    browser = await start_browser()
    results: list[dict[str, Any]] = []

    try:
        for index, case in enumerate(cases, 1):
            safe_slug = _safe_case_slug(case.get("slug"))
            resolved_run_dir = run_dir.resolve()
            case_dir = (resolved_run_dir / f"{index:02d}_{safe_slug}").resolve()
            if resolved_run_dir not in case_dir.parents:
                raise ValueError("case output escaped run directory")
            case_dir.mkdir(parents=True, exist_ok=True)

            def progress(step: str, message: str, pct: float) -> None:
                print(f"[{index:02d}/{len(cases):02d}] {step} {pct:.0%} {message}", flush=True)

            try:
                report = await run_platform_sourcing(
                    str(case.get("url") or ""),
                    output_dir=str(case_dir),
                    progress=progress,
                    platforms=platforms,
                    browser=browser,
                    gemini_client=gemini,
                    product_name_hint=str(case.get("title") or ""),
                    min_similarity_score=float(args.min_similarity),
                    download_only=True,
                    platform_min_relevance_score=required_relevance_score,
                )
            except Exception as exc:
                report = {"ok": False, "error": f"unhandled: {exc}"}

            video_path = str(
                report.get("downloaded_video")
                or report.get("final_video")
                or ((report.get("hit") or {}).get("video_file"))
                or ""
            )
            hit = report.get("hit") or {}
            relevance_score = hit.get("relevance_score")
            threshold_passed = _meets_relevance_threshold(
                relevance_score, required_relevance_score
            )
            report_ok = bool(report.get("ok"))
            error = str(report.get("error") or "")
            if report_ok and not threshold_passed:
                error = (
                    f"relevance score {relevance_score!r} is below requested "
                    f"threshold {required_relevance_score:.6f}"
                )
            item = {
                "index": index,
                "slug": case.get("slug", ""),
                "affiliate_url": case.get("url", ""),
                "title_hint": case.get("title", ""),
                "product_name": (report.get("product_info") or {}).get("name", ""),
                "ok": report_ok and threshold_passed,
                "error": error,
                "keywords": report.get("keywords") or {},
                "queries": report.get("queries") or [],
                "platform": hit.get("platform", ""),
                "source_url": hit.get("video_url", ""),
                "source_title": hit.get("title", ""),
                "relevance_score": relevance_score,
                "required_relevance_score": required_relevance_score,
                "relevance_threshold_passed": threshold_passed,
                "via": hit.get("via", ""),
                "video_path": video_path,
                "media": _probe_video(video_path),
            }
            results.append(item)
            _write_summary(summary_path, started_at, results)
            print(
                json.dumps(
                    {key: item[key] for key in ("index", "ok", "platform", "source_url", "error")},
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        try:
            await browser.stop()
        except Exception:
            pass

    _write_summary(summary_path, started_at, results)
    succeeded = sum(1 for item in results if item["ok"] and item["media"]["decode_ok"])
    print(f"LIVE_BATCH_RESULT {succeeded}/{len(results)} summary={summary_path}", flush=True)
    return 0 if succeeded == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--platforms", default="douyin,xiaohongshu,kuaishou")
    parser.add_argument("--min-similarity", type=float, default=0.75)
    parser.add_argument(
        "--no-gemini",
        action="store_true",
        help="exercise the deterministic production fallback without API calls",
    )
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
