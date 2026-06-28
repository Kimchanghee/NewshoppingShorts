"""
Read-only status helpers for the Summer Coupang scheduled automation queue.

The scheduled runner owns the queue file. UI code should only read and display it.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_QUEUE_PATH = (
    Path.home() / ".ssmaker" / "summer_coupang_autosourcing_queue_20260603.json"
)

SUCCESS_STATUSES = {"completed"}
LINKTREE_RETRY_STATUSES = {"completed_linktree_blocked", "linktree_retry_pending"}
SKIPPED_STATUSES = {
    "skipped_low_similarity",
    "skipped_quality_gate",
    "skipped_duplicate_product",
    "failed_linktree_publish",
    "skipped",
}
SYSTEM_BLOCKER_MARKERS = (
    "api key expired",
    "api key not valid",
    "api_key_invalid",
    "gemini api key",
    "gemini api 키",
    "invalid_argument",
    "키워드 변환에 실패",
    "api 키를 설정",
)

STATUS_LABELS = {
    "pending": "예약 대기",
    "processing": "진행 중",
    "completed": "완료",
    "completed_linktree_blocked": "Linktree 재시도 대기",
    "linktree_retry_pending": "Linktree 재시도 대기",
    "failed_linktree_publish": "Linktree 실패",
    "skipped_low_similarity": "건너뜀",
    "skipped_quality_gate": "품질보류",
    "skipped_duplicate_product": "중복보류",
    "skipped": "건너뜀",
    "failed": "실패",
}


def load_summer_coupang_queue(
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load the scheduled queue payload, accepting UTF-8 BOM files."""
    queue_path = path or DEFAULT_QUEUE_PATH
    if not queue_path.exists():
        return {}
    try:
        return json.loads(queue_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def parse_datetime(raw: Any) -> Optional[datetime]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def format_datetime(raw: Any) -> str:
    value = parse_datetime(raw)
    if value is None:
        return str(raw or "").strip()
    return value.strftime("%m-%d %H:%M")


def _extract_youtube_url(result: Dict[str, Any]) -> str:
    direct = str(result.get("youtube_url") or "").strip()
    if direct:
        return direct
    youtube = result.get("youtube") if isinstance(result.get("youtube"), dict) else {}
    url = str(youtube.get("video_url") or "").strip()
    if url:
        return url
    verification = (
        result.get("youtube_verification")
        if isinstance(result.get("youtube_verification"), dict)
        else {}
    )
    metadata = verification.get("metadata") if isinstance(verification.get("metadata"), dict) else {}
    return str(metadata.get("video_url") or "").strip()


def _status_bucket(status: str) -> str:
    normalized = str(status or "pending").strip().lower()
    if normalized in SUCCESS_STATUSES:
        return "completed"
    if normalized in LINKTREE_RETRY_STATUSES:
        return "waiting"
    if normalized in SKIPPED_STATUSES:
        return "skipped"
    if normalized in {"failed", "error"}:
        return "failed"
    if normalized in {"processing", "running"}:
        return "processing"
    return "waiting"


def _is_system_sourcing_blocker(result: Dict[str, Any]) -> bool:
    text = " ".join(
        str(part or "")
        for part in (
            result.get("blocking_reason"),
            result.get("error"),
            result.get("match_error"),
            result.get("match_status"),
        )
    ).lower()
    return any(marker in text for marker in SYSTEM_BLOCKER_MARKERS)


def _is_retriable_system_skip(item: Dict[str, Any]) -> bool:
    status = str(item.get("status") or "").strip().lower()
    if status not in SKIPPED_STATUSES:
        return False
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    return _is_system_sourcing_blocker(result)


def _status_bucket_for_item(item: Dict[str, Any]) -> str:
    if _is_retriable_system_skip(item):
        return "waiting"
    return _status_bucket(str(item.get("status") or "pending"))


def _row_for_item(item: Dict[str, Any]) -> Dict[str, str]:
    status = str(item.get("status") or "pending").strip().lower()
    retriable_system_skip = _is_retriable_system_skip(item)
    planned = str(item.get("planned_number") or "").strip()
    scheduled_at = format_datetime(item.get("scheduled_at"))
    attempts = int(item.get("attempts") or 0)
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    youtube_url = _extract_youtube_url(result)
    blocking_reason = str(result.get("blocking_reason") or "").strip()
    linktree_result = (
        result.get("linktree_result")
        if isinstance(result.get("linktree_result"), dict)
        else {}
    )
    linktree_ok = bool(linktree_result.get("ok"))
    linktree_reason = str(linktree_result.get("blocking_reason") or blocking_reason).strip()

    if youtube_url:
        upload_text = f"YouTube 완료: {youtube_url}"
    elif retriable_system_skip:
        upload_text = "재시도 대기"
    elif status == "pending":
        upload_text = "예약됨"
    elif status == "failed":
        upload_text = "업로드 실패"
    else:
        upload_text = "-"

    remarks_parts: List[str] = []
    if scheduled_at:
        remarks_parts.append(f"예약 {scheduled_at}")
    remarks_parts.append(f"시도 {attempts}회")
    if status in LINKTREE_RETRY_STATUSES:
        remarks_parts.append("Linktree 재시도 대기")
        if linktree_reason:
            remarks_parts.append(linktree_reason)
    elif linktree_ok:
        remarks_parts.append("Linktree 완료")
    elif blocking_reason:
        remarks_parts.append(blocking_reason)

    status_label = "재시도 대기" if retriable_system_skip else STATUS_LABELS.get(status, status or "대기")
    return {
        "order": planned or status_label,
        "url": str(item.get("coupang_url") or item.get("purchase_url") or "").strip(),
        "status": status_label,
        "upload": upload_text,
        "remarks": " / ".join(part for part in remarks_parts if part),
        "raw_status": status,
        "retriable_system_skip": "true" if retriable_system_skip else "",
        "planned_number": planned,
        "scheduled_at": scheduled_at,
        "youtube_url": youtube_url,
    }


def build_summer_coupang_queue_snapshot(
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    payload = load_summer_coupang_queue(path)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    rows = [_row_for_item(item) for item in items if isinstance(item, dict)]

    counts = {
        "waiting": 0,
        "processing": 0,
        "completed": 0,
        "skipped": 0,
        "failed": 0,
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        bucket = _status_bucket_for_item(item)
        counts[bucket] = counts.get(bucket, 0) + 1

    pending_items = [
        item
        for item in items
        if isinstance(item, dict)
        and _status_bucket_for_item(item) == "waiting"
    ]
    pending_items.sort(
        key=lambda item: (
            parse_datetime(item.get("scheduled_at")) or datetime.max,
            int(item.get("scheduled_order") or 999999),
        )
    )
    next_pending = pending_items[0] if pending_items else {}

    interval = (
        payload.get("automation_policy", {}).get("interval_minutes")
        if isinstance(payload.get("automation_policy"), dict)
        else None
    )
    if interval is None:
        intervals = [
            int(item.get("scheduled_interval_minutes") or 0)
            for item in items
            if isinstance(item, dict) and item.get("scheduled_interval_minutes")
        ]
        interval = intervals[0] if intervals else 0

    return {
        "path": str(path or DEFAULT_QUEUE_PATH),
        "exists": bool(payload),
        "total": len(rows),
        "counts": counts,
        "rows": rows,
        "interval_minutes": int(interval or 0),
        "next_planned_number": str(next_pending.get("planned_number") or "").strip(),
        "next_scheduled_at": str(next_pending.get("scheduled_at") or "").strip(),
        "next_scheduled_display": format_datetime(next_pending.get("scheduled_at")),
    }
