from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SSMAKER_DISABLE_FASTER_WHISPER", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.api import ApiKeyManager
from core.sourcing.pipeline import SourcingPipeline
from managers.linktree_manager import (
    COUPANG_AFFILIATE_DISCLOSURE,
    DEFAULT_LINKTREE_PROFILE_URL,
    LinktreeManager,
    get_linktree_manager,
)
from managers.youtube_manager import YouTubeManager, get_youtube_manager
from scripts import render_program_pipeline_upload as renderer


QUEUE_PATH = Path(r"C:\Users\HOME\.ssmaker\summer_coupang_autosourcing_queue_20260603.json")
DEFAULT_MIN_SIMILARITY = 0.9
AUTOMATION_LABEL = "summer_coupang_queue"
SUCCESS_FINAL_STATUSES = {
    "completed",
    "completed_linktree_blocked",
}
SKIP_STATUSES = {
    "skipped_low_similarity",
}


def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def now_datetime() -> datetime:
    return datetime.now().astimezone()


def parse_scheduled_datetime(raw: Any) -> Optional[datetime]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=now_datetime().tzinfo)
    return value


def is_item_due(item: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    scheduled_at = parse_scheduled_datetime(item.get("scheduled_at"))
    if scheduled_at is None:
        return True
    return scheduled_at <= (now or now_datetime())


def load_queue() -> Dict[str, Any]:
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8-sig"))


def save_queue(payload: Dict[str, Any]) -> None:
    QUEUE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_upload_number(raw: Any) -> Optional[int]:
    match = re.search(r"\d+", str(raw or ""))
    if not match:
        return None
    value = int(match.group(0))
    return value if value > 0 else None


def build_run_dir(item: Dict[str, Any]) -> Path:
    number = parse_upload_number(item.get("planned_number")) or 0
    product_id = str(item.get("coupang_url", "")).rstrip("/").rsplit("/", 1)[-1]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path.home() / ".ssmaker" / "sourcing_output" / f"{AUTOMATION_LABEL}_{number:03d}_{product_id}_{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_gemini_client() -> Any:
    from google import genai

    manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)
    key = manager.get_available_key()
    if not key:
        raise RuntimeError("Gemini API key is not configured.")
    return genai.Client(api_key=key)


def progress(label: str):
    def _inner(step_id: str, message: str, pct: float):
        print(f"[{label}] {step_id} {pct:.0%} {message}", flush=True)

    return _inner


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def select_safe_marketplace_item(report: Dict[str, Any], min_similarity: float) -> Optional[Dict[str, Any]]:
    if report.get("match_status") != "matched":
        return None
    try:
        best = float(report.get("best_similarity") or 0)
    except (TypeError, ValueError):
        return None
    if best < min_similarity:
        return None
    for item in report.get("sourced_products") or []:
        if item.get("auto_publish_safe") and item.get("video_file"):
            return item
    return None


async def run_sourcing(item: Dict[str, Any], run_dir: Path, min_similarity: float) -> Dict[str, Any]:
    out_dir = run_dir / "sourcing"
    out_dir.mkdir(parents=True, exist_ok=True)
    pipeline = SourcingPipeline(
        coupang_url=str(item["coupang_url"]),
        output_dir=str(out_dir),
        on_progress=progress(item.get("planned_number") or "SRC"),
        gemini_client=get_gemini_client(),
        min_similarity_score=min_similarity,
        enforce_min_similarity=True,
    )
    success = False
    try:
        success = await pipeline.run_sourcing()
    except Exception as exc:
        pipeline.error = str(exc)

    report = pipeline.get_report()
    report["success"] = bool(success)
    report["planned_number"] = item.get("planned_number", "")
    report["queue_product_name"] = item.get("product_name", "")
    report_path = out_dir / "report.json"
    write_json(report_path, report)
    report["_report_path"] = str(report_path)
    return report


def determine_purchase_url(item: Dict[str, Any], report: Dict[str, Any]) -> str:
    queue_affiliate = str(item.get("affiliate_url", "") or "").strip()
    if queue_affiliate:
        return queue_affiliate
    deep_link = str(report.get("deep_link", "") or "").strip()
    if deep_link:
        return deep_link
    return str(item.get("coupang_url", "") or "").strip()


def render_single_item(job: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
    renderer.JOBS = [job]
    rendered = renderer.render_jobs(run_dir / "rendered", limit=1)
    if not rendered:
        raise RuntimeError("Render pipeline did not produce a result.")
    result = dict(rendered[0])
    result_path = run_dir / "rendered" / "render_result.json"
    write_json(result_path, result)
    result["_render_result_path"] = str(result_path)
    return result


def build_upload_item(
    rendered: Dict[str, Any],
    item: Dict[str, Any],
    report: Dict[str, Any],
    purchase_url: str,
    privacy: str,
) -> Dict[str, Any]:
    upload_number = parse_upload_number(item.get("planned_number"))
    if not upload_number:
        raise RuntimeError(f"Invalid planned_number: {item.get('planned_number')}")

    product_name = str(rendered["product_name"])
    product_title = YouTubeManager.apply_upload_number_to_product_text(product_name, upload_number, limit=220)
    base_title = f"[광고] {product_name[:70]} #shorts"
    title = YouTubeManager.apply_upload_number_to_title(
        YouTubeManager.ensure_coupang_title_compliance(base_title),
        upload_number,
    )
    linktree_url = DEFAULT_LINKTREE_PROFILE_URL
    desc_lines = [
        COUPANG_AFFILIATE_DISCLOSURE,
        "",
        f"상품: {product_title}",
        f"링크 모음: {linktree_url}",
        f"구매 링크: {purchase_url}",
    ]
    description = YouTubeManager.apply_upload_number_to_description(
        YouTubeManager.ensure_coupang_affiliate_compliance("\n".join(desc_lines), purchase_url),
        upload_number,
        product_text=product_name,
    )

    return {
        "video_path": rendered["final_video"],
        "title": title,
        "description": description,
        "tags": ["shorts", "여름템", "쿠팡추천", "쇼핑쇼츠", "automation"],
        "product_info": product_name,
        "product_description": product_name,
        "product_name": product_name,
        "source_url": str(item.get("coupang_url") or ""),
        "coupang_deep_link": purchase_url,
        "linktree_url": linktree_url,
        "upload_number": upload_number,
        "privacy": privacy,
        "render_integrity": rendered.get("render_integrity") or {},
        "render_integrity_required": True,
        "report_path": report.get("_report_path", ""),
    }


def upload_verified_render(upload_item: Dict[str, Any], privacy: str) -> Dict[str, Any]:
    yt = get_youtube_manager(gui=None)
    if not yt.is_connected() or not yt._ensure_youtube_service():
        raise RuntimeError("YouTube channel is not connected.")
    yt._upload_settings.default_privacy = privacy
    ok = yt._upload_video(upload_item)
    if not ok or not upload_item.get("video_id"):
        raise RuntimeError("YouTube upload failed.")
    return {
        "video_id": upload_item["video_id"],
        "video_url": upload_item["video_url"],
        "title": upload_item["title"],
        "description": upload_item["description"],
        "privacy": privacy,
        "upload_number": upload_item["upload_number"],
    }


def verify_youtube(upload_item: Dict[str, Any], uploaded: Dict[str, Any]) -> Dict[str, Any]:
    yt = get_youtube_manager(gui=None)
    if not yt._ensure_youtube_service():
        raise RuntimeError("YouTube service unavailable for verification.")
    video_id = uploaded["video_id"]
    marker = YouTubeManager.format_upload_number(upload_item["upload_number"])
    response = yt._youtube_service.videos().list(part="snippet,status", id=video_id).execute()
    videos = response.get("items", [])
    if not videos:
        raise RuntimeError(f"YouTube video not found after upload: {video_id}")
    video = videos[0]
    snippet = video.get("snippet", {})
    status = video.get("status", {})
    title = str(snippet.get("title", ""))
    desc = str(snippet.get("description", ""))
    metadata = {
        "video_id": video_id,
        "video_url": uploaded["video_url"],
        "title": title,
        "privacy": status.get("privacyStatus", ""),
        "has_number_title": marker in title,
        "has_number_description": marker in desc,
        "has_linktree": DEFAULT_LINKTREE_PROFILE_URL in desc,
        "has_disclosure": COUPANG_AFFILIATE_DISCLOSURE in desc,
        "has_purchase_url": str(upload_item["coupang_deep_link"]) in desc,
    }

    comment_verification: Dict[str, Any] = {}
    for attempt in range(1, 7):
        comments_response = yt._youtube_service.commentThreads().list(
            part="snippet",
            videoId=video_id,
            textFormat="plainText",
            maxResults=20,
        ).execute()
        comments = [
            row.get("snippet", {})
            .get("topLevelComment", {})
            .get("snippet", {})
            .get("textDisplay", "")
            for row in comments_response.get("items", [])
        ]
        comment_verification = {
            "checked_comments": len(comments),
            "has_number": any(marker in text for text in comments),
            "has_linktree": any(DEFAULT_LINKTREE_PROFILE_URL in text for text in comments),
            "has_disclosure": any(COUPANG_AFFILIATE_DISCLOSURE in text for text in comments),
            "has_purchase_url": any(str(upload_item["coupang_deep_link"]) in text for text in comments),
            "sample": comments[0] if comments else "",
            "attempts": attempt,
        }
        if all(
            [
                comment_verification["has_number"],
                comment_verification["has_linktree"],
                comment_verification["has_disclosure"],
                comment_verification["has_purchase_url"],
            ]
        ):
            break
        if attempt < 6:
            time.sleep(10)
    return {
        "metadata": metadata,
        "comment": comment_verification,
        "ok": all(
            [
                metadata["has_number_title"],
                metadata["has_number_description"],
                metadata["has_linktree"],
                metadata["has_disclosure"],
                metadata["has_purchase_url"],
                comment_verification["has_number"],
                comment_verification["has_linktree"],
                comment_verification["has_disclosure"],
                comment_verification["has_purchase_url"],
            ]
        ),
    }


def publish_linktree_if_possible(item: Dict[str, Any], product_name: str, purchase_url: str) -> Dict[str, Any]:
    manager = get_linktree_manager()
    upload_number = parse_upload_number(item.get("planned_number"))
    marker = manager.format_publish_index(upload_number)
    title = manager._build_numbered_product_title(product_name, upload_number)
    source_url = str(item.get("coupang_url") or "")

    settings = manager.get_settings()
    webhook_url = str(settings.get("webhook_url", "") or "").strip()
    if webhook_url:
        ok = manager.publish_link(
            title=title,
            url=purchase_url,
            description=COUPANG_AFFILIATE_DISCLOSURE,
            source_url=source_url,
            extra={
                "channel": "shopping_shorts_maker",
                "publish_index": upload_number,
                "display_number": marker,
            },
        )
        public_check = verify_linktree_public_card(marker, purchase_url)
        return {
            "ok": bool(ok and public_check.get("ok")),
            "method": "webhook",
            "title": title,
            "number": marker,
            "purchase_url": purchase_url,
            "profile_url": manager.get_profile_url(),
            "public_verification": public_check,
            "blocking_reason": "" if ok and public_check.get("ok") else "Linktree webhook publish did not verify on the public page.",
        }

    return {
        "ok": False,
        "method": "blocked",
        "title": title,
        "number": marker,
        "purchase_url": purchase_url,
        "profile_url": manager.get_profile_url(),
        "public_verification": {},
        "blocking_reason": (
            "Linktree webhook URL is not configured, and this session has no callable authenticated "
            "Linktree browser/computer-use editing path. Public-page Playwright access is available, "
            "but it cannot create or update cards without an authenticated editor session."
        ),
    }


def verify_linktree_public_card(number: str, purchase_url: str) -> Dict[str, Any]:
    import requests

    profile_url = DEFAULT_LINKTREE_PROFILE_URL
    try:
        response = requests.get(
            profile_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
                ),
            },
            timeout=30,
        )
    except Exception as exc:
        return {
            "ok": False,
            "url": profile_url,
            "status_code": 0,
            "has_number": False,
            "has_purchase_url": False,
            "error": str(exc),
        }
    text = response.text
    return {
        "ok": response.status_code == 200 and number in text and purchase_url in text,
        "url": profile_url,
        "status_code": response.status_code,
        "has_number": number in text,
        "has_purchase_url": purchase_url in text,
    }


def update_item_attempt(item: Dict[str, Any]) -> None:
    item["attempts"] = int(item.get("attempts", 0) or 0) + 1
    item["last_attempt_at"] = now_local()


def pending_item_count(queue_payload: Dict[str, Any]) -> int:
    items: List[Dict[str, Any]] = queue_payload.get("items") or []
    return sum(1 for item in items if str(item.get("status")) == "pending")


def youtube_upload_ready() -> Dict[str, Any]:
    try:
        from managers.settings_manager import get_settings_manager

        yt = get_youtube_manager(gui=None)
        if not yt._ensure_youtube_service():
            return {
                "ok": False,
                "reason": "youtube_not_connected",
                "blocking_reason": "YouTube OAuth token is missing or invalid. Reconnect the YouTube channel before consuming pending queue items.",
            }

        verification = get_settings_manager().get_youtube_account_verification() or {}
        if verification.get("required") and not verification.get("ok"):
            return {
                "ok": False,
                "reason": "youtube_account_verification_failed",
                "blocking_reason": str(verification.get("message") or "YouTube account verification failed."),
                "expected": verification.get("expected", ""),
                "actual": verification.get("actual", ""),
            }

        return {"ok": True}
    except Exception as exc:
        return {
            "ok": False,
            "reason": "youtube_preflight_error",
            "blocking_reason": str(exc),
        }


def attach_result(
    item: Dict[str, Any],
    *,
    status: str,
    similarity: Optional[float] = None,
    render_path: str = "",
    youtube_url: str = "",
    linktree_result: Optional[Dict[str, Any]] = None,
    blocking_reason: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    item["status"] = status
    result = dict(item.get("result") or {})
    result["updated_at"] = now_local()
    result["similarity"] = similarity
    result["render_path"] = render_path
    result["youtube_url"] = youtube_url
    result["linktree_result"] = linktree_result or {}
    result["blocking_reason"] = blocking_reason
    if extra:
        result.update(extra)
    item["result"] = result


async def process_pending_items(queue_payload: Dict[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = queue_payload.get("items") or []
    pending = [item for item in items if str(item.get("status")) == "pending"]
    if not pending:
        return {"processed": False, "reason": "no_pending_items"}

    now = now_datetime()
    due_pending = [item for item in pending if is_item_due(item, now=now)]
    if not due_pending:
        next_scheduled_at = min(
            (
                str(item.get("scheduled_at") or "")
                for item in pending
                if str(item.get("scheduled_at") or "").strip()
            ),
            default="",
        )
        return {
            "processed": False,
            "reason": "no_due_items",
            "pending_count": len(pending),
            "next_scheduled_at": next_scheduled_at,
        }

    min_similarity = float(
        (queue_payload.get("automation_policy") or {}).get("min_similarity_score", DEFAULT_MIN_SIMILARITY)
    )
    privacy = str(
        (queue_payload.get("automation_policy") or {}).get("youtube_privacy", "unlisted")
    ).strip() or "unlisted"

    for item in due_pending:
        update_item_attempt(item)
        save_queue(queue_payload)

        run_dir = build_run_dir(item)
        report = await run_sourcing(item, run_dir, min_similarity)
        safe_item = select_safe_marketplace_item(report, min_similarity)
        similarity = report.get("best_similarity")
        product_name = str((report.get("product_info") or {}).get("name") or item.get("product_name") or "").strip()

        if not safe_item:
            reason = str(report.get("match_error") or report.get("error") or "No safe marketplace video matched the threshold.")
            attach_result(
                item,
                status="skipped_low_similarity",
                similarity=similarity,
                blocking_reason=reason,
                extra={
                    "match_status": report.get("match_status"),
                    "report_path": report.get("_report_path", ""),
                    "purchase_url": determine_purchase_url(item, report),
                },
            )
            save_queue(queue_payload)
            return {
                "processed": True,
                "status": "skipped_low_similarity",
                "planned_number": item.get("planned_number"),
                "reason": reason,
            }

        purchase_url = determine_purchase_url(item, report)
        job = {
            "index": parse_upload_number(item.get("planned_number")) or 0,
            "upload_number": parse_upload_number(item.get("planned_number")) or 0,
            "product_name": product_name,
            "product_url": str(item.get("coupang_url") or ""),
            "purchase_url": purchase_url,
            "video_file": Path(str(safe_item["video_file"])),
            "report_file": Path(str(report["_report_path"])),
            "best_similarity": similarity,
            "source_title": safe_item.get("title") or (safe_item.get("product") or {}).get("title", ""),
            "source_url": safe_item.get("url") or (safe_item.get("product") or {}).get("url", ""),
        }

        try:
            rendered = render_single_item(job, run_dir)
            if not rendered.get("render_ok"):
                raise RuntimeError("Render verification failed.")

            upload_item = build_upload_item(rendered, item, report, purchase_url, privacy)
            uploaded = upload_verified_render(upload_item, privacy)
            youtube_verification = verify_youtube(upload_item, uploaded)
            if not youtube_verification.get("ok"):
                raise RuntimeError("YouTube metadata/comment verification failed.")

            linktree_result = publish_linktree_if_possible(item, product_name, purchase_url)
            final_status = "completed" if linktree_result.get("ok") else "completed_linktree_blocked"
            attach_result(
                item,
                status=final_status,
                similarity=similarity,
                render_path=str(rendered.get("final_video") or ""),
                youtube_url=str(uploaded.get("video_url") or ""),
                linktree_result=linktree_result,
                blocking_reason=str(linktree_result.get("blocking_reason") or ""),
                extra={
                    "report_path": report.get("_report_path", ""),
                    "render_result_path": rendered.get("_render_result_path", ""),
                    "purchase_url": purchase_url,
                    "youtube": uploaded,
                    "youtube_verification": youtube_verification,
                    "run_dir": str(run_dir),
                },
            )
            save_queue(queue_payload)
            return {
                "processed": True,
                "status": final_status,
                "planned_number": item.get("planned_number"),
                "youtube_url": uploaded.get("video_url", ""),
                "linktree_ok": linktree_result.get("ok", False),
            }
        except Exception as exc:
            attach_result(
                item,
                status="failed",
                similarity=similarity,
                render_path=str((run_dir / "rendered").resolve()),
                blocking_reason=str(exc),
                extra={
                    "report_path": report.get("_report_path", ""),
                    "purchase_url": purchase_url,
                    "run_dir": str(run_dir),
                },
            )
            save_queue(queue_payload)
            return {
                "processed": True,
                "status": "failed",
                "planned_number": item.get("planned_number"),
                "error": str(exc),
            }

    return {"processed": False, "reason": "all_pending_items_skipped_low_similarity"}


def main() -> int:
    queue_payload = load_queue()
    pending_count = pending_item_count(queue_payload)
    if pending_count:
        youtube_state = youtube_upload_ready()
        if not youtube_state.get("ok"):
            print(
                json.dumps(
                    {
                        "processed": False,
                        "reason": youtube_state.get("reason", "youtube_not_ready"),
                        "pending_count": pending_count,
                        "blocking_reason": youtube_state.get("blocking_reason", ""),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                flush=True,
            )
            return 0

    summary = asyncio.run(process_pending_items(queue_payload))
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    if summary.get("status") in SUCCESS_FINAL_STATUSES:
        return 0
    if summary.get("status") in SKIP_STATUSES:
        return 0
    if summary.get("reason") == "no_pending_items":
        return 0
    if summary.get("reason") == "no_due_items":
        return 0
    if summary.get("reason") == "all_pending_items_skipped_low_similarity":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
