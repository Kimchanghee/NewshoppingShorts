from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from managers.linktree_manager import COUPANG_AFFILIATE_DISCLOSURE, DEFAULT_LINKTREE_PROFILE_URL
from managers.youtube_manager import (
    COUPANG_PAID_PROMOTION_TITLE_MARKER,
    YouTubeManager,
    get_youtube_manager,
)
from scripts.run_summer_coupang_queue_once import (
    QUEUE_PATH,
    build_summer_upload_metadata,
    parse_upload_number,
)


TARGET_STATUSES = {"completed", "completed_linktree_blocked"}


def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def extract_video_id(item: Dict[str, Any]) -> str:
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    youtube = result.get("youtube") if isinstance(result.get("youtube"), dict) else {}
    for value in (
        youtube.get("video_id"),
        result.get("video_id"),
        result.get("youtube_url"),
        youtube.get("video_url"),
    ):
        text = str(value or "").strip()
        if not text:
            continue
        if re.fullmatch(r"[A-Za-z0-9_-]{8,}", text):
            return text
        match = re.search(r"(?:youtu\.be/|[?&]v=)([A-Za-z0-9_-]{8,})", text)
        if match:
            return match.group(1)
    return ""


def purchase_url_for_item(item: Dict[str, Any]) -> str:
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    for key in ("purchase_url", "affiliate_url", "coupang_url"):
        value = result.get(key) if key == "purchase_url" else item.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return str(item.get("coupang_url") or "").strip()


def strip_old_title(title: str, marker: str) -> str:
    text = " ".join(str(title or "").split())
    text = text.replace(COUPANG_PAID_PROMOTION_TITLE_MARKER, " ")
    text = text.replace(marker, " ")
    text = re.sub(r"#\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def build_desired_payload(
    item: Dict[str, Any],
    existing_video: Dict[str, Any],
) -> Dict[str, Any]:
    upload_number = parse_upload_number(item.get("planned_number"))
    if not upload_number:
        raise RuntimeError(f"Invalid planned_number: {item.get('planned_number')}")

    marker = YouTubeManager.format_upload_number(upload_number)
    metadata = build_summer_upload_metadata(item)
    purchase_url = purchase_url_for_item(item)
    snippet = existing_video.get("snippet", {}) if isinstance(existing_video, dict) else {}
    status = existing_video.get("status", {}) if isinstance(existing_video, dict) else {}
    old_title = str(snippet.get("title") or "")
    old_product_name = strip_old_title(old_title, marker)
    summary_line = str(metadata.get("line") or item.get("product_name") or old_product_name).strip()
    situation = str(metadata.get("situation") or "").strip()
    tags = [
        tag
        for tag in (
            YouTubeManager._normalize_hashtag_token(tag)
            for tag in (metadata.get("tags") or [])
        )
        if tag
    ]
    title = YouTubeManager.ensure_coupang_title_compliance(
        str(metadata.get("title") or summary_line or old_product_name),
        marker_position="suffix",
    )
    original_line = old_product_name or str(item.get("product_name") or "").strip() or summary_line
    numbered_summary = YouTubeManager.apply_upload_number_to_product_text(
        summary_line,
        upload_number,
        limit=220,
    )
    numbered_original = YouTubeManager.apply_upload_number_to_product_text(
        original_line,
        upload_number,
        limit=220,
    )
    desc_lines = [
        f"{marker} {summary_line}".strip(),
        f"상품: {numbered_summary}",
        f"구매 링크는 프로필 Linktree에서 {marker} 검색하면 바로 확인할 수 있습니다.",
        f"링크 모음: {DEFAULT_LINKTREE_PROFILE_URL}",
        f"구매 링크: {purchase_url}",
        COUPANG_AFFILIATE_DISCLOSURE,
    ]
    if situation:
        desc_lines.extend(["", situation])
    if original_line:
        desc_lines.append(f"원상품명: {numbered_original}")

    description = YouTubeManager.ensure_coupang_affiliate_compliance(
        "\n".join(desc_lines),
        purchase_url,
    )
    hashtags = " ".join(f"#{tag}" for tag in tags)
    if hashtags:
        description = f"{description}\n\n{hashtags}"
    description = YouTubeManager._sanitize_public_text(description, limit=5000)

    comment_lines = [
        COUPANG_AFFILIATE_DISCLOSURE,
        f"{marker} 영상에서 소개한 상품 안내입니다.",
        f"상품: {numbered_summary}",
        f"Linktree에서 {marker} 검색: {DEFAULT_LINKTREE_PROFILE_URL}",
        f"구매 링크: {purchase_url}",
    ]
    source_url = str(item.get("coupang_url") or "").strip()
    if source_url and source_url != purchase_url:
        comment_lines.append(f"원상품 링크: {source_url}")
    comment_lines.append("궁금한 점은 댓글로 남겨주세요.")
    comment_text = YouTubeManager._trim_comment_text(
        YouTubeManager._sanitize_comment_body("\n".join(comment_lines)),
        limit=10000,
    )

    return {
        "video_id": existing_video.get("id") or extract_video_id(item),
        "title": title,
        "description": description,
        "tags": tags,
        "privacy": "public",
        "category_id": str(snippet.get("categoryId") or "22"),
        "made_for_kids": bool(status.get("selfDeclaredMadeForKids", False)),
        "comment_text": comment_text,
        "purchase_url": purchase_url,
        "marker": marker,
        "metadata": metadata,
    }


def load_queue() -> Dict[str, Any]:
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8-sig"))


def save_queue(payload: Dict[str, Any]) -> None:
    QUEUE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def backup_queue() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = QUEUE_PATH.with_name(
        f"{QUEUE_PATH.stem}.backup_before_existing_youtube_metadata_update_{stamp}{QUEUE_PATH.suffix}"
    )
    backup.write_text(QUEUE_PATH.read_text(encoding="utf-8-sig"), encoding="utf-8")
    return str(backup)


def chunked(values: List[str], size: int) -> List[List[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_existing_videos(yt: Any, video_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    for group in chunked(video_ids, 50):
        response = yt._youtube_service.videos().list(
            part="snippet,status",
            id=",".join(group),
        ).execute()
        for video in response.get("items", []):
            found[str(video.get("id") or "")] = video
    return found


def update_video(yt: Any, desired: Dict[str, Any]) -> None:
    yt._youtube_service.videos().update(
        part="snippet,status",
        body={
            "id": desired["video_id"],
            "snippet": {
                "title": desired["title"],
                "description": desired["description"],
                "tags": desired["tags"],
                "categoryId": desired["category_id"],
            },
            "status": {
                "privacyStatus": desired["privacy"],
                "selfDeclaredMadeForKids": desired["made_for_kids"],
            },
        },
    ).execute()


def find_existing_auto_comment(yt: Any, video_id: str, desired: Dict[str, Any]) -> Dict[str, str]:
    response = yt._youtube_service.commentThreads().list(
        part="snippet",
        videoId=video_id,
        textFormat="plainText",
        maxResults=50,
    ).execute()
    marker = desired["marker"]
    purchase_url = desired["purchase_url"]
    for row in response.get("items", []):
        top_level = row.get("snippet", {}).get("topLevelComment", {})
        comment_id = str(top_level.get("id") or "")
        snippet = top_level.get("snippet", {})
        text = str(snippet.get("textDisplay") or snippet.get("textOriginal") or "")
        if not comment_id:
            continue
        if (
            marker in text
            or purchase_url in text
            or DEFAULT_LINKTREE_PROFILE_URL in text
            or COUPANG_AFFILIATE_DISCLOSURE in text
        ):
            return {"id": comment_id, "text": text}
    return {}


def update_or_insert_comment(yt: Any, video_id: str, desired: Dict[str, Any]) -> Dict[str, Any]:
    existing = find_existing_auto_comment(yt, video_id, desired)
    if existing.get("id"):
        try:
            yt._youtube_service.comments().update(
                part="snippet",
                body={
                    "id": existing["id"],
                    "snippet": {
                        "textOriginal": desired["comment_text"],
                    },
                },
            ).execute()
            return {"method": "updated", "comment_id": existing["id"]}
        except Exception as exc:
            insert_result = yt._post_top_level_comment(video_id, desired["comment_text"])
            return {
                "method": "inserted_after_update_failed" if insert_result else "failed",
                "comment_id": existing["id"],
                "error": str(exc),
            }

    inserted = yt._post_top_level_comment(video_id, desired["comment_text"])
    return {"method": "inserted" if inserted else "failed", "comment_id": ""}


def verify_video_and_comment(yt: Any, video_id: str, desired: Dict[str, Any]) -> Dict[str, Any]:
    video_response = yt._youtube_service.videos().list(
        part="snippet,status",
        id=video_id,
    ).execute()
    video = (video_response.get("items") or [{}])[0]
    snippet = video.get("snippet", {})
    status = video.get("status", {})
    title = str(snippet.get("title") or "")
    desc = str(snippet.get("description") or "")
    comments_response = yt._youtube_service.commentThreads().list(
        part="snippet",
        videoId=video_id,
        textFormat="plainText",
        maxResults=50,
    ).execute()
    comments = [
        str(
            row.get("snippet", {})
            .get("topLevelComment", {})
            .get("snippet", {})
            .get("textDisplay", "")
        )
        for row in comments_response.get("items", [])
    ]
    comment_ok = any(
        desired["marker"] in text
        and DEFAULT_LINKTREE_PROFILE_URL in text
        and COUPANG_AFFILIATE_DISCLOSURE in text
        and desired["purchase_url"] in text
        for text in comments
    )
    metadata = {
        "title": title,
        "privacy": status.get("privacyStatus", ""),
        "has_problem_hook_title": not title.strip().startswith(COUPANG_PAID_PROMOTION_TITLE_MARKER),
        "has_paid_marker_title": COUPANG_PAID_PROMOTION_TITLE_MARKER in title,
        "has_number_description": desired["marker"] in desc,
        "has_linktree": DEFAULT_LINKTREE_PROFILE_URL in desc,
        "has_disclosure": COUPANG_AFFILIATE_DISCLOSURE in desc,
        "has_purchase_url": desired["purchase_url"] in desc,
    }
    ok = all(
        [
            metadata["privacy"] == "public",
            metadata["has_problem_hook_title"],
            metadata["has_paid_marker_title"],
            metadata["has_number_description"],
            metadata["has_linktree"],
            metadata["has_disclosure"],
            metadata["has_purchase_url"],
            comment_ok,
        ]
    )
    return {
        "ok": ok,
        "metadata": metadata,
        "comment": {
            "checked_comments": len(comments),
            "ok": comment_ok,
        },
    }


def completed_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = payload.get("items") or []
    return [
        item
        for item in items
        if str(item.get("status") or "").strip().lower() in TARGET_STATUSES
        and extract_video_id(item)
    ]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update already-uploaded Summer Coupang YouTube videos to the current metadata strategy."
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of completed videos to update.")
    parser.add_argument("--dry-run", action="store_true", help="Build payloads without writing to YouTube or queue.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    payload = load_queue()
    targets = completed_items(payload)
    if args.limit and args.limit > 0:
        targets = targets[: args.limit]
    if not targets:
        print(json.dumps({"processed": False, "reason": "no_completed_videos"}, ensure_ascii=False, indent=2))
        return 0

    yt = get_youtube_manager(gui=None)
    if not yt._ensure_youtube_service():
        print(json.dumps({"processed": False, "reason": "youtube_not_connected"}, ensure_ascii=False, indent=2))
        return 1

    video_ids = [extract_video_id(item) for item in targets]
    existing_videos = fetch_existing_videos(yt, video_ids)
    started_at = now_local()
    backup_path = "" if args.dry_run else backup_queue()
    results: List[Dict[str, Any]] = []

    for item in targets:
        planned_number = str(item.get("planned_number") or "")
        video_id = extract_video_id(item)
        existing_video = existing_videos.get(video_id)
        if not existing_video:
            results.append(
                {
                    "planned_number": planned_number,
                    "video_id": video_id,
                    "ok": False,
                    "error": "video_not_found",
                }
            )
            continue

        try:
            desired = build_desired_payload(item, existing_video)
            if args.dry_run:
                results.append(
                    {
                        "planned_number": planned_number,
                        "video_id": video_id,
                        "ok": True,
                        "dry_run": True,
                        "title": desired["title"],
                    }
                )
                continue

            update_video(yt, desired)
            comment_result = update_or_insert_comment(yt, video_id, desired)
            verification = verify_video_and_comment(yt, video_id, desired)

            item["upload_metadata"] = deepcopy(desired["metadata"])
            item["metadata_strategy"] = "problem_hook_title_number_in_description_linktree"
            item["paid_marker_position"] = "suffix"
            item["youtube_title_strategy"] = "problem_hook_title_with_paid_marker_suffix"
            item["updated_at"] = now_local()

            result = item.setdefault("result", {})
            youtube = result.setdefault("youtube", {})
            youtube.update(
                {
                    "video_id": video_id,
                    "video_url": f"https://youtu.be/{video_id}",
                    "title": desired["title"],
                    "description": desired["description"],
                    "privacy": desired["privacy"],
                    "upload_number": parse_upload_number(item.get("planned_number")),
                }
            )
            result["youtube_metadata_reworked_at"] = now_local()
            result["youtube_metadata_rework_strategy"] = "problem_hook_title_number_in_description_linktree"
            result["youtube_comment_rework"] = comment_result
            result["youtube_rework_verification"] = verification
            result["updated_at"] = now_local()

            save_queue(payload)
            results.append(
                {
                    "planned_number": planned_number,
                    "video_id": video_id,
                    "ok": bool(verification.get("ok")),
                    "title": desired["title"],
                    "comment_method": comment_result.get("method"),
                    "verification": verification,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "planned_number": planned_number,
                    "video_id": video_id,
                    "ok": False,
                    "error": str(exc),
                }
            )
            save_queue(payload)

    summary = {
        "processed": True,
        "started_at": started_at,
        "finished_at": now_local(),
        "target_count": len(targets),
        "ok_count": sum(1 for result in results if result.get("ok")),
        "failed_count": sum(1 for result in results if not result.get("ok")),
        "backup": backup_path,
        "items": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
