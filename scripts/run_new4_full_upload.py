from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SSMAKER_DISABLE_FASTER_WHISPER", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.api import ApiKeyManager
from core.sourcing.pipeline import SourcingPipeline
from managers.youtube_manager import (
    COUPANG_AFFILIATE_DISCLOSURE,
    YouTubeManager,
    get_youtube_manager,
)
from scripts import render_program_pipeline_upload as renderer


LINKTREE_URL = "https://linktr.ee/studio.idol"
MIN_SIMILARITY = 0.9
START_UPLOAD_NUMBER = 6
TARGET_COUNT = 4

CANDIDATES = [
    "https://www.coupang.com/vp/products/8978671713",
    "https://www.coupang.com/vp/products/9174331294",
    "https://www.coupang.com/vp/products/8315938536",
    "https://www.coupang.com/vp/products/7408622794",
    "https://www.coupang.com/vp/products/8898595595",
    "https://www.coupang.com/vp/products/5608129630",
    "https://www.coupang.com/vp/products/8356392355",
    "https://www.coupang.com/vp/products/9097019707",
    "https://www.coupang.com/vp/products/9217638642",
    "https://www.coupang.com/vp/products/9442943958",
    "https://www.coupang.com/vp/products/8587633170",
    "https://www.coupang.com/vp/products/8590529986",
]


def _get_gemini_client() -> Any:
    from google import genai

    manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)
    key = manager.get_available_key()
    if not key:
        raise RuntimeError("Gemini API key is not configured.")
    return genai.Client(api_key=key)


def _progress(label: str):
    def _inner(step_id: str, message: str, pct: float):
        print(f"[{label}] {step_id} {pct:.0%} {message}", flush=True)

    return _inner


def _is_safe_match(report: Dict[str, Any]) -> bool:
    if report.get("match_status") != "matched":
        return False
    try:
        if float(report.get("best_similarity") or 0) < MIN_SIMILARITY:
            return False
    except (TypeError, ValueError):
        return False
    for item in report.get("sourced_products") or []:
        if item.get("auto_publish_safe") and item.get("video_file"):
            return True
    return False


async def source_products(run_dir: Path) -> List[Dict[str, Any]]:
    client = _get_gemini_client()
    selected: List[Dict[str, Any]] = []
    source_root = run_dir / "sourcing"
    source_root.mkdir(parents=True, exist_ok=True)

    for ordinal, url in enumerate(CANDIDATES, start=1):
        if len(selected) >= TARGET_COUNT:
            break

        product_id = url.rstrip("/").rsplit("/", 1)[-1]
        out_dir = source_root / f"{ordinal:02d}_{product_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== SOURCING {ordinal}/{len(CANDIDATES)} {url} ===", flush=True)

        pipeline = SourcingPipeline(
            coupang_url=url,
            output_dir=str(out_dir),
            on_progress=_progress(f"SRC {ordinal}"),
            gemini_client=client,
            min_similarity_score=MIN_SIMILARITY,
            enforce_min_similarity=True,
        )
        try:
            success = await pipeline.run_sourcing()
        except Exception as exc:
            success = False
            pipeline.error = str(exc)

        report = pipeline.get_report()
        report["success"] = bool(success)
        report_path = out_dir / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        if not success or not _is_safe_match(report):
            print(
                "SKIP:",
                product_id,
                "status=",
                report.get("match_status"),
                "best=",
                report.get("best_similarity"),
                "error=",
                report.get("error") or report.get("match_error"),
                flush=True,
            )
            continue

        safe_item = next(
            item
            for item in report.get("sourced_products") or []
            if item.get("auto_publish_safe") and item.get("video_file")
        )
        product_name = (report.get("product_info") or {}).get("name") or safe_item.get("title") or product_id
        purchase_url = report.get("deep_link") or url
        upload_number = START_UPLOAD_NUMBER + len(selected)
        selected.append(
            {
                "index": upload_number,
                "upload_number": upload_number,
                "product_name": product_name,
                "product_url": url,
                "purchase_url": purchase_url,
                "video_file": Path(safe_item["video_file"]),
                "report_file": report_path,
                "best_similarity": report.get("best_similarity"),
                "source_title": safe_item.get("title"),
                "source_url": safe_item.get("url"),
            }
        )
        print(f"SELECTED [{upload_number:03d}] {product_name}", flush=True)

    if len(selected) < TARGET_COUNT:
        raise RuntimeError(f"Only {len(selected)} safe products found; need {TARGET_COUNT}.")
    return selected


def _build_upload_item(rendered: Dict[str, Any], job: Dict[str, Any], privacy: str) -> Dict[str, Any]:
    product_name = rendered["product_name"]
    purchase_url = job["purchase_url"]
    upload_number = job["upload_number"]
    title = f"[광고] {product_name[:70]} #shorts"
    title = YouTubeManager.apply_upload_number_to_title(
        YouTubeManager.ensure_coupang_title_compliance(title),
        upload_number,
    )
    description = "\n".join(
        [
            COUPANG_AFFILIATE_DISCLOSURE,
            "",
            f"상품: {product_name}",
            f"모든 상품 링크: {LINKTREE_URL}",
            f"원상품 링크: {purchase_url}",
        ]
    )
    description = YouTubeManager.apply_upload_number_to_description(
        YouTubeManager.ensure_coupang_affiliate_compliance(description, purchase_url),
        upload_number,
        product_text=product_name,
    )
    return {
        "video_path": rendered["final_video"],
        "title": title,
        "description": description,
        "tags": ["shorts", "쇼츠", "상품추천", "쿠팡", "생활용품"],
        "product_info": product_name,
        "source_url": job["product_url"],
        "coupang_deep_link": purchase_url,
        "linktree_url": LINKTREE_URL,
        "upload_number": upload_number,
        "privacy": privacy,
        "render_integrity": rendered.get("render_integrity") or {},
        "render_integrity_required": True,
    }


def upload_verified(rendered: List[Dict[str, Any]], jobs: List[Dict[str, Any]], privacy: str) -> List[Dict[str, Any]]:
    yt = get_youtube_manager(gui=None)
    if not yt.is_connected() or not yt._ensure_youtube_service():
        raise RuntimeError("YouTube channel is not connected.")
    yt._upload_settings.default_privacy = privacy
    jobs_by_number = {job["upload_number"]: job for job in jobs}
    uploaded: List[Dict[str, Any]] = []
    for item in rendered:
        if not item.get("render_ok"):
            raise RuntimeError(f"Render verification failed: {item['final_video']}")
        job = jobs_by_number[item["index"]]
        upload_item = _build_upload_item(item, job, privacy)
        ok = yt._upload_video(upload_item)
        if not ok or not upload_item.get("video_id"):
            raise RuntimeError(f"YouTube upload failed: {item['final_video']}")
        uploaded.append(
            {
                "upload_number": job["upload_number"],
                "number": f"[{job['upload_number']:03d}]",
                "product_name": item["product_name"],
                "product_url": job["product_url"],
                "purchase_url": job["purchase_url"],
                "video_id": upload_item["video_id"],
                "video_url": upload_item["video_url"],
                "title": upload_item["title"],
                "privacy": privacy,
            }
        )
    return uploaded


def verify_youtube(uploaded: List[Dict[str, Any]]) -> Dict[str, Any]:
    yt = get_youtube_manager(gui=None)
    if not yt._ensure_youtube_service():
        raise RuntimeError("YouTube service unavailable for verification.")
    ids = ",".join(item["video_id"] for item in uploaded)
    response = yt._youtube_service.videos().list(part="snippet,status", id=ids).execute()
    found = {item["id"]: item for item in response.get("items", [])}
    checked = []
    for item in uploaded:
        video = found.get(item["video_id"], {})
        snippet = video.get("snippet", {})
        status = video.get("status", {})
        desc = snippet.get("description", "")
        title = snippet.get("title", "")
        checked.append(
            {
                "video_id": item["video_id"],
                "title": title,
                "privacy": status.get("privacyStatus", ""),
                "has_number_title": item["number"] in title,
                "has_number_description": item["number"] in desc,
                "has_linktree": LINKTREE_URL in desc,
                "has_disclosure": COUPANG_AFFILIATE_DISCLOSURE in desc,
                "has_purchase_url": item["purchase_url"] in desc,
            }
        )
    return {"checked": len(checked), "ok": all(all(v for k, v in row.items() if k not in {"video_id", "title", "privacy"}) for row in checked), "items": checked}


def verify_comments(uploaded: List[Dict[str, Any]]) -> Dict[str, Any]:
    yt = get_youtube_manager(gui=None)
    if not yt._ensure_youtube_service():
        raise RuntimeError("YouTube service unavailable for comment verification.")
    checked = []
    for item in uploaded:
        response = yt._youtube_service.commentThreads().list(
            part="snippet",
            videoId=item["video_id"],
            textFormat="plainText",
            maxResults=20,
        ).execute()
        comments = [
            row.get("snippet", {}).get("topLevelComment", {}).get("snippet", {}).get("textDisplay", "")
            for row in response.get("items", [])
        ]
        checked.append(
            {
                "video_id": item["video_id"],
                "checked_comments": len(comments),
                "has_number": any(item["number"] in text for text in comments),
                "has_linktree": any(LINKTREE_URL in text for text in comments),
                "has_disclosure": any(COUPANG_AFFILIATE_DISCLOSURE in text for text in comments),
                "has_purchase_url": any(item["purchase_url"] in text for text in comments),
            }
        )
    return {"checked": len(checked), "ok": all(row["has_number"] and row["has_linktree"] and row["has_disclosure"] and row["has_purchase_url"] for row in checked), "items": checked}


def main() -> int:
    privacy = os.getenv("SSMAKER_NEW4_PRIVACY", "unlisted")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path.home() / ".ssmaker" / "sourcing_output" / f"new4_full_upload_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    jobs = asyncio.run(source_products(run_dir))
    renderer.JOBS = jobs
    rendered = renderer.render_jobs(run_dir / "rendered")
    uploaded = upload_verified(rendered, jobs, privacy=privacy)
    summary = {
        "run_dir": str(run_dir),
        "jobs": [
            {
                **{k: str(v) if isinstance(v, Path) else v for k, v in job.items()},
                "number": f"[{job['upload_number']:03d}]",
            }
            for job in jobs
        ],
        "rendered": rendered,
        "render_ok": all(item.get("render_ok") for item in rendered),
        "uploaded": uploaded,
        "youtube_verification": verify_youtube(uploaded),
        "youtube_comments": verify_comments(uploaded),
        "linktree_cards_to_add": [
            {
                "number": item["number"],
                "title": f"{item['number']} {item['product_name']}",
                "url": item["purchase_url"],
            }
            for item in uploaded
        ],
    }
    summary_path = run_dir / "new4_full_upload_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSUMMARY={summary_path}", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if summary["render_ok"] and summary["youtube_verification"]["ok"] and summary["youtube_comments"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
