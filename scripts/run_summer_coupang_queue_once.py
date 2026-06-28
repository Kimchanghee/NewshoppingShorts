from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime, timedelta
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
from managers.youtube_manager import (
    COUPANG_PAID_PROMOTION_TITLE_MARKER,
    YouTubeManager,
    get_youtube_manager,
)
from scripts import render_program_pipeline_upload as renderer


QUEUE_PATH = Path(r"C:\Users\HOME\.ssmaker\summer_coupang_autosourcing_queue_20260603.json")
DEFAULT_MIN_SIMILARITY = 0.9
DEFAULT_MAX_CANDIDATE_ITEMS_PER_RUN = 50
DEFAULT_CONTINUE_AFTER_SKIP_UNTIL_COMPLETED = True
DEFAULT_SCHEDULE_INTERVAL_MINUTES = 240
MIN_FINAL_VIDEO_SECONDS = 8.0
MAX_FINAL_VIDEO_SECONDS = 60.0
MIN_FINAL_VIDEO_BYTES = 1_000_000
FORCE_RUN_NOW_ENV = "SSMAKER_SUMMER_COUPANG_RUN_NOW"
SUMMER_COUPANG_TASK_NAME = "SSMaker Summer Coupang Queue"
AUTOMATION_LABEL = "summer_coupang_queue"
GEMINI_KEY_PREFLIGHT_ENV = "SSMAKER_GEMINI_KEY_PREFLIGHT"
GEMINI_KEY_ALERT_THROTTLE_SECONDS_ENV = "SSMAKER_GEMINI_KEY_ALERT_THROTTLE_SECONDS"
GEMINI_KEY_ALERT_PATH = Path.home() / ".ssmaker" / "alerts" / "summer_coupang_gemini_api_key_alert.json"
GEMINI_KEY_ALERT_DIALOG_SCRIPT = ROOT / "scripts" / "show_summer_coupang_gemini_alert.py"
GEMINI_MODELS_PROBE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
LINKTREE_PUBLIC_VERIFY_ATTEMPTS_ENV = "SSMAKER_LINKTREE_PUBLIC_VERIFY_ATTEMPTS"
LINKTREE_PUBLIC_VERIFY_INTERVAL_ENV = "SSMAKER_LINKTREE_PUBLIC_VERIFY_INTERVAL_SECONDS"
DEFAULT_LINKTREE_PUBLIC_VERIFY_ATTEMPTS = 6
DEFAULT_LINKTREE_PUBLIC_VERIFY_INTERVAL_SECONDS = 10.0
LINKTREE_RETRY_STATUS = "linktree_retry_pending"
SUCCESS_FINAL_STATUSES = {
    "completed",
}
LINKTREE_RETRY_STATUSES = {
    "completed_linktree_blocked",
    LINKTREE_RETRY_STATUS,
}
SKIP_STATUSES = {
    "skipped_low_similarity",
    "skipped_quality_gate",
    "skipped_duplicate_product",
}
PRODUCT_FAMILY_BY_CATEGORY = {
    "cooling_handheld_fan": "fan",
    "portable_cooling_fan": "fan",
    "mist_fan": "fan",
    "neck_fan": "fan",
    "desk_camping_fan": "fan",
    "camping_fan": "fan",
    "clip_fan": "fan",
}
DEFAULT_DUPLICATE_FAMILY_LIMITS = {
    "fan": 1,
}
SYSTEM_BLOCKER_MARKERS = (
    "api key expired",
    "api key not valid",
    "api_key_invalid",
    "gemini api key",
    "gemini api 키",
    "invalid_argument",
    "marketplace_access_challenge",
    "manual verification",
    "logged-in session",
    "키워드 변환에 실패",
    "api 키를 설정",
)
SUMMER_UPLOAD_METADATA: Dict[str, Dict[str, Any]] = {
    "mini_air_cooler": {
        "title": "에어컨 틀기 전 10초 쿨링템, 미니냉풍기 체감 #shorts",
        "line": "방 안 더울 때 바로 쓰는 미니냉풍기",
        "situation": "방 안이 답답하게 더울 때 에어컨을 바로 틀기 전 보조 쿨링템으로 확인하기 좋습니다.",
        "tags": ["냉풍기", "미니냉풍기", "여름가전", "자취템", "쿠팡추천"],
    },
    "cooling_handheld_fan": {
        "title": "출근길 땀 식히는 손풍기, 이 정도면 충분함 #shorts",
        "line": "차 안/출근길 더위 버티는 손풍기",
        "situation": "출근길, 차 안, 야외 대기처럼 잠깐씩 더위를 버텨야 하는 순간에 쓰기 좋은 여름템입니다.",
        "tags": ["손풍기", "휴대용선풍기", "여름꿀템", "출근템", "쿠팡추천"],
    },
    "portable_cooling_fan": {
        "title": "밖에서 바로 식히는 휴대용 냉각팬, 더운 날 필수템 #shorts",
        "line": "더운 날 가방에 넣는 휴대용 냉각팬",
        "situation": "야외 이동이 많은 날 가방에 넣어 두고 바로 꺼내 쓰는 쿨링 아이템입니다.",
        "tags": ["휴대용선풍기", "냉각팬", "여름필수템", "야외템", "쿠팡추천"],
    },
    "mist_fan": {
        "title": "분사까지 되는 손풍기, 야외 더위 체감이 다름 #shorts",
        "line": "물분사로 더 시원한 휴대용 선풍기",
        "situation": "그냥 바람만으로 부족한 야외 더위에 분사 기능까지 같이 쓰는 제품군입니다.",
        "tags": ["미스트선풍기", "손풍기", "여름꿀템", "야외템", "쿠팡추천"],
    },
    "neck_fan": {
        "title": "목에 걸면 양손이 비는 넥팬, 더운 날 이게 편함 #shorts",
        "line": "하이킹/출근길에 쓰는 넥밴드 선풍기",
        "situation": "손에 들 필요 없이 목에 걸어 쓰는 방식이라 이동 중 더위 대응에 편합니다.",
        "tags": ["넥팬", "목선풍기", "휴대용선풍기", "여름꿀템", "쿠팡추천"],
    },
    "desk_camping_fan": {
        "title": "캠핑장에서 조용하게 쓰는 무선 선풍기 #여름꿀템",
        "line": "캠핑/책상 위에 두는 저소음 선풍기",
        "situation": "캠핑장, 책상, 침대 옆처럼 가까운 곳에 두고 쓰는 무선 선풍기입니다.",
        "tags": ["캠핑선풍기", "탁상용선풍기", "무선선풍기", "여름캠핑", "쿠팡추천"],
    },
    "camping_fan": {
        "title": "캠핑 더위 버티는 무선 선풍기, 텐트 안 필수템 #shorts",
        "line": "텐트 안 더위 줄이는 캠핑 선풍기",
        "situation": "텐트 안, 차박, 야외 테이블에서 더운 공기를 식히는 캠핑용 여름템입니다.",
        "tags": ["캠핑선풍기", "무선선풍기", "차박템", "여름캠핑", "쿠팡추천"],
    },
    "clip_fan": {
        "title": "유모차부터 책상까지 집는 클립 선풍기 #여름꿀템",
        "line": "어디든 집어서 쓰는 클립 선풍기",
        "situation": "유모차, 책상, 선반처럼 세워두기 애매한 곳에 고정해서 쓰는 선풍기입니다.",
        "tags": ["클립선풍기", "휴대용선풍기", "여름꿀템", "육아템", "쿠팡추천"],
    },
    "uv_umbrella": {
        "title": "햇빛 강한 날 얼굴 온도 줄이는 초경량 양산 #shorts",
        "line": "출근길 햇빛 막는 UV 차단 양산",
        "situation": "한낮 햇빛이 강할 때 가방에 넣어 두고 바로 꺼내 쓰는 UV 차단 아이템입니다.",
        "tags": ["양산추천", "자외선차단", "여름필수템", "출근템", "쿠팡추천"],
    },
    "uv_parasol": {
        "title": "한낮 햇빛 피하려면 양산 하나는 있어야 함 #shorts",
        "line": "강한 햇빛 막는 UV 차단 파라솔",
        "situation": "야외 이동이 많은 날 직사광선과 체감 더위를 줄이는 용도입니다.",
        "tags": ["양산추천", "UV차단", "여름필수템", "야외템", "쿠팡추천"],
    },
    "cooling_towel": {
        "title": "목에 두르면 바로 시원한 여름 쿨타올 #shorts",
        "line": "운동/캠핑 때 바로 식히는 쿨타올",
        "situation": "운동, 캠핑, 산책처럼 땀이 빨리 나는 순간에 목 주변을 식히기 좋습니다.",
        "tags": ["쿨타올", "쿨스카프", "캠핑템", "운동템", "여름필수템"],
    },
    "cooling_arm_sleeves": {
        "title": "운전할 때 팔 타는 사람, 냉감 쿨토시 써야 하는 이유 #shorts",
        "line": "운전/자전거 탈 때 쓰는 냉감 쿨토시",
        "situation": "운전, 자전거, 야외 작업처럼 팔이 햇빛에 오래 노출될 때 쓰는 여름템입니다.",
        "tags": ["쿨토시", "냉감토시", "운전템", "자외선차단", "여름꿀템"],
    },
    "cooling_arm_sleeve": {
        "title": "운전할 때 팔 타는 사람, 냉감 쿨토시 써야 하는 이유 #shorts",
        "line": "운전/자전거 탈 때 쓰는 냉감 쿨토시",
        "situation": "운전, 자전거, 야외 작업처럼 팔이 햇빛에 오래 노출될 때 쓰는 여름템입니다.",
        "tags": ["쿨토시", "냉감토시", "운전템", "자외선차단", "여름꿀템"],
    },
    "cooling_clothing": {
        "title": "땀 많은 날 옷부터 시원해야 버팀, 냉감 의류 체크 #shorts",
        "line": "더운 날 입는 냉감 여름 의류",
        "situation": "땀이 많은 날 출근, 운동, 야외 활동 전에 먼저 확인할 냉감 의류입니다.",
        "tags": ["냉감의류", "여름옷", "쿨링템", "출근템", "쿠팡추천"],
    },
    "waterproof_phone_pouch": {
        "title": "물놀이 갈 때 폰 살리는 방수팩 체크포인트 #shorts",
        "line": "물놀이 전에 폰 방수부터 챙기는 방수팩",
        "situation": "워터파크, 바다, 계곡처럼 휴대폰 침수가 걱정되는 날 먼저 챙길 제품군입니다.",
        "tags": ["방수팩", "물놀이", "여름휴가", "여름필수템", "쿠팡추천"],
    },
    "cooling_bedding": {
        "title": "밤새 뒤척이면 침대부터 시원하게, 여름 냉감침구 #shorts",
        "line": "열대야에 쓰는 냉감 침구",
        "situation": "밤새 덥고 뒤척이는 열대야에는 침대부터 시원하게 바꾸는 것이 체감이 큽니다.",
        "tags": ["냉감침구", "쿨매트", "열대야", "여름침구", "쿠팡추천"],
    },
    "mosquito_trap": {
        "title": "모기랑 전쟁하는 사람, 여름 벌레템 하나는 필요함 #shorts",
        "line": "여름밤 모기 줄이는 모기트랩",
        "situation": "잠들기 전 모기 소리나 캠핑장 벌레가 신경 쓰이는 사람에게 맞는 제품군입니다.",
        "tags": ["모기퇴치", "모기트랩", "여름꿀템", "캠핑템", "쿠팡추천"],
    },
    "mosquito_repellent_band": {
        "title": "야외에서 모기 물리기 싫으면 팔찌부터 챙김 #shorts",
        "line": "캠핑/산책 때 쓰는 모기 기피 밴드",
        "situation": "산책, 캠핑, 야외 놀이처럼 오래 밖에 있을 때 챙기는 모기 기피 아이템입니다.",
        "tags": ["모기팔찌", "모기퇴치", "캠핑템", "여름필수템", "쿠팡추천"],
    },
    "mosquito_swatter": {
        "title": "모기 보이면 바로 끝내는 전기 모기채 #shorts",
        "line": "여름밤 바로 쓰는 전기 모기채",
        "situation": "자취방이나 침실에서 모기가 보일 때 바로 대응하기 좋은 여름 방충템입니다.",
        "tags": ["전기모기채", "모기퇴치", "여름꿀템", "자취템", "쿠팡추천"],
    },
}
DEFAULT_SUMMER_UPLOAD_METADATA = {
    "title": "더운 날 바로 쓰는 여름 생활꿀템 #shorts",
    "line": "여름 불편을 줄이는 생활 꿀템",
    "situation": "더운 날 반복되는 생활 불편을 줄이는 여름 추천템입니다.",
    "tags": ["생활꿀템", "여름꿀템", "쿠팡추천", "가성비템", "shorts"],
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


def force_run_now_enabled() -> bool:
    return str(os.environ.get(FORCE_RUN_NOW_ENV, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def is_system_sourcing_blocker(report: Dict[str, Any], reason: str = "") -> bool:
    text = " ".join(
        str(part or "")
        for part in (
            reason,
            report.get("error"),
            report.get("match_error"),
            report.get("match_status"),
        )
    ).lower()
    return any(marker in text for marker in SYSTEM_BLOCKER_MARKERS)


def is_retriable_system_skip(item: Dict[str, Any]) -> bool:
    status = str(item.get("status") or "").strip().lower()
    if status not in SKIP_STATUSES or status == "skipped_duplicate_product":
        return False
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    reason = str(result.get("blocking_reason") or result.get("error") or "").strip()
    return is_system_sourcing_blocker(result, reason)


def is_linktree_retry_item(item: Dict[str, Any]) -> bool:
    status = str(item.get("status") or "").strip().lower()
    return status in LINKTREE_RETRY_STATUSES


def is_processable_queue_item(item: Dict[str, Any]) -> bool:
    status = str(item.get("status") or "").strip().lower()
    return status == "pending" or is_linktree_retry_item(item) or is_retriable_system_skip(item)


def youtube_upload_required_item_count(queue_payload: Dict[str, Any]) -> int:
    items: List[Dict[str, Any]] = queue_payload.get("items") or []
    return sum(
        1
        for item in items
        if is_processable_queue_item(item) and not is_linktree_retry_item(item)
    )


def queue_interval_minutes(queue_payload: Dict[str, Any]) -> int:
    policy = queue_payload.get("automation_policy") if isinstance(queue_payload.get("automation_policy"), dict) else {}
    candidates: List[Any] = [policy.get("interval_minutes"), policy.get("scheduled_interval_minutes")]
    items = queue_payload.get("items") if isinstance(queue_payload.get("items"), list) else []
    candidates.extend(item.get("scheduled_interval_minutes") for item in items if isinstance(item, dict))
    for raw in candidates:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return DEFAULT_SCHEDULE_INTERVAL_MINUTES


def scheduled_task_next_run_time(task_name: str = SUMMER_COUPANG_TASK_NAME) -> Optional[datetime]:
    if os.name != "nt":
        return None
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-ScheduledTaskInfo -TaskName {task_name!r}).NextRunTime.ToString('o')",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    lines = completed.stdout.strip().splitlines()
    if not lines:
        return None
    try:
        return datetime.fromisoformat(lines[-1].replace("Z", "+00:00"))
    except ValueError:
        return None


def realign_pending_schedule_after_run_now(
    queue_payload: Dict[str, Any],
    *,
    base_time: Optional[datetime] = None,
    first_scheduled_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    items = queue_payload.get("items") if isinstance(queue_payload.get("items"), list) else []
    pending = [item for item in items if isinstance(item, dict) and is_processable_queue_item(item)]
    if not pending:
        return {"rescheduled_count": 0, "next_scheduled_at": ""}

    interval = queue_interval_minutes(queue_payload)
    now = base_time or now_datetime()
    first_at = first_scheduled_at or (now + timedelta(minutes=interval))
    pending.sort(
        key=lambda item: (
            parse_scheduled_datetime(item.get("scheduled_at")) or datetime.max.replace(tzinfo=now.tzinfo),
            int(item.get("scheduled_order") or 999999),
        )
    )
    for offset, item in enumerate(pending):
        scheduled_at = first_at + timedelta(minutes=interval * offset)
        item["scheduled_at"] = scheduled_at.isoformat(timespec="seconds")
        item["scheduled_interval_minutes"] = interval
    return {
        "rescheduled_count": len(pending),
        "next_scheduled_at": str(pending[0].get("scheduled_at") or ""),
        "interval_minutes": interval,
    }


def extract_result_youtube_url(result: Dict[str, Any]) -> str:
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


def linktree_retry_context(item: Dict[str, Any]) -> Dict[str, str]:
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    youtube = result.get("youtube") if isinstance(result.get("youtube"), dict) else {}
    product_name = str(
        item.get("product_title")
        or youtube.get("product_title")
        or result.get("product_title")
        or youtube.get("product_name")
        or result.get("product_name")
        or item.get("product_name")
        or item.get("title")
        or "Coupang product"
    ).strip()
    purchase_url = str(
        result.get("purchase_url")
        or item.get("affiliate_url")
        or item.get("purchase_url")
        or item.get("coupang_url")
        or ""
    ).strip()
    return {
        "product_name": product_name,
        "purchase_url": purchase_url,
        "render_path": str(result.get("render_path") or "").strip(),
        "youtube_url": extract_result_youtube_url(result),
    }


def linktree_failure_status(linktree_result: Dict[str, Any]) -> str:
    return "completed" if linktree_result.get("ok") else LINKTREE_RETRY_STATUS


def linktree_retry_summary(
    item: Dict[str, Any],
    linktree_result: Dict[str, Any],
    *,
    run_now: bool,
) -> Dict[str, Any]:
    summary = {
        "processed": True,
        "status": linktree_failure_status(linktree_result),
        "planned_number": item.get("planned_number"),
        "linktree_ok": linktree_result.get("ok", False),
        "linktree_retry": not bool(linktree_result.get("ok")),
    }
    if run_now:
        summary["run_now"] = True
    if not linktree_result.get("ok"):
        summary["blocking_type"] = "linktree_publish_pending"
        summary["blocking_reason"] = str(linktree_result.get("blocking_reason") or "")
    return summary


def normalize_duplicate_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^0-9a-z가-힣]+", " ", text)
    tokens = [
        token
        for token in text.split()
        if len(token) > 1 and token not in {"usb", "with", "and", "for", "the"}
    ]
    return " ".join(tokens)


def coupang_product_id(value: Any) -> str:
    match = re.search(r"/products/(\d+)", str(value or ""))
    return match.group(1) if match else ""


def product_family(item: Dict[str, Any]) -> str:
    return PRODUCT_FAMILY_BY_CATEGORY.get(str(item.get("category") or "").strip(), "")


def duplicate_policy(queue_payload: Dict[str, Any]) -> Dict[str, Any]:
    policy = queue_payload.get("automation_policy") if isinstance(queue_payload.get("automation_policy"), dict) else {}
    raw_limits = policy.get("duplicate_product_family_limits")
    limits = dict(DEFAULT_DUPLICATE_FAMILY_LIMITS)
    if isinstance(raw_limits, dict):
        for key, value in raw_limits.items():
            try:
                limits[str(key)] = max(0, int(value))
            except (TypeError, ValueError):
                continue
    return {
        "family_limits": limits,
        "skip_same_normalized_product_name": bool(
            policy.get("skip_same_normalized_product_name", True)
        ),
    }


def completed_duplicate_index(
    queue_payload: Dict[str, Any],
    *,
    current_item: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    index: Dict[str, Any] = {
        "coupang_ids": {},
        "product_names": {},
        "family_counts": {},
    }
    for item in queue_payload.get("items") or []:
        if item is current_item:
            continue
        if str(item.get("status") or "").strip().lower() not in SUCCESS_FINAL_STATUSES:
            continue
        planned = str(item.get("planned_number") or "").strip()
        product_id = coupang_product_id(item.get("coupang_url") or item.get("purchase_url"))
        if product_id:
            index["coupang_ids"][product_id] = planned

        name_key = normalize_duplicate_text(item.get("product_name"))
        if name_key:
            index["product_names"][name_key] = planned

        family = product_family(item)
        if family:
            index["family_counts"][family] = int(index["family_counts"].get(family, 0)) + 1
    return index


def duplicate_upload_reason(
    item: Dict[str, Any],
    queue_payload: Dict[str, Any],
    *,
    product_name: str = "",
) -> str:
    policy = duplicate_policy(queue_payload)
    index = completed_duplicate_index(queue_payload, current_item=item)

    product_id = coupang_product_id(item.get("coupang_url") or item.get("purchase_url"))
    if product_id and product_id in index["coupang_ids"]:
        return f"Duplicate Coupang product id {product_id} already uploaded as {index['coupang_ids'][product_id]}."

    if policy["skip_same_normalized_product_name"]:
        for raw_name in (product_name, item.get("product_name")):
            name_key = normalize_duplicate_text(raw_name)
            if name_key and name_key in index["product_names"]:
                return f"Duplicate product name already uploaded as {index['product_names'][name_key]}."

    family = product_family(item)
    if family:
        limit = int(policy["family_limits"].get(family, 999999))
        existing_count = int(index["family_counts"].get(family, 0))
        if existing_count >= limit:
            return f"Duplicate product family '{family}' already has {existing_count} completed upload(s)."

    return ""


def load_queue() -> Dict[str, Any]:
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8-sig"))


def save_queue(payload: Dict[str, Any]) -> None:
    QUEUE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def due_upload_required_items(
    queue_payload: Dict[str, Any],
    *,
    force_run_now: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = queue_payload.get("items") or []
    pending = [
        item
        for item in items
        if is_processable_queue_item(item) and not is_linktree_retry_item(item)
    ]
    if not pending:
        return []

    run_now = force_run_now_enabled() if force_run_now is None else bool(force_run_now)
    if run_now:
        return [pending[0]]

    now = now_datetime()
    return [item for item in pending if is_item_due(item, now=now)]


def gemini_key_preflight_enabled() -> bool:
    raw = str(os.environ.get(GEMINI_KEY_PREFLIGHT_ENV, "1")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _google_error_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    details = error.get("details") if isinstance(error.get("details"), list) else []
    reasons = []
    for detail in details:
        if not isinstance(detail, dict):
            continue
        reason = str(detail.get("reason") or "").strip()
        domain = str(detail.get("domain") or "").strip()
        if reason or domain:
            reasons.append({"reason": reason, "domain": domain})
    return {
        "google_status": str(error.get("status") or "").strip(),
        "google_code": error.get("code"),
        "message_summary": str(error.get("message") or "").strip()[:180],
        "details": reasons,
    }


def probe_configured_gemini_api_keys(timeout_seconds: float = 15.0) -> Dict[str, Any]:
    try:
        import requests
    except Exception as exc:
        return {
            "ok": False,
            "reason": "gemini_preflight_unavailable",
            "blocking_reason": f"Cannot import requests for Gemini API key preflight: {exc}",
            "valid_aliases": [],
            "invalid_aliases": [],
            "missing_aliases": [],
        }

    try:
        manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)
        api_keys = dict(getattr(manager, "api_keys", {}) or {})
    except Exception as exc:
        return {
            "ok": False,
            "reason": "gemini_preflight_unavailable",
            "blocking_reason": f"Cannot load Gemini API keys: {exc}",
            "valid_aliases": [],
            "invalid_aliases": [],
            "missing_aliases": [],
        }

    valid_aliases: List[str] = []
    invalid_aliases: List[Dict[str, Any]] = []
    missing_aliases = [
        f"api_{idx}"
        for idx in range(1, ApiKeyManager.APIKeyManager.MAX_KEYS + 1)
        if f"api_{idx}" not in api_keys
    ]

    for alias, key_value in sorted(api_keys.items()):
        if not str(key_value or "").strip():
            missing_aliases.append(alias)
            continue
        try:
            response = requests.get(
                GEMINI_MODELS_PROBE_URL,
                params={"key": key_value},
                timeout=timeout_seconds,
            )
            if response.status_code == 200:
                valid_aliases.append(alias)
                continue
            try:
                payload = response.json()
            except Exception:
                payload = {}
            invalid_aliases.append(
                {
                    "alias": alias,
                    "http_status": response.status_code,
                    **_google_error_summary(payload),
                }
            )
        except Exception as exc:
            invalid_aliases.append(
                {
                    "alias": alias,
                    "http_status": 0,
                    "google_status": "probe_error",
                    "message_summary": f"{type(exc).__name__}: {exc}"[:180],
                    "details": [],
                }
            )

    if valid_aliases:
        return {
            "ok": True,
            "reason": "gemini_api_key_available",
            "valid_aliases": valid_aliases,
            "invalid_aliases": invalid_aliases,
            "missing_aliases": sorted(set(missing_aliases)),
        }

    reason = "gemini_api_keys_missing" if not api_keys else "gemini_api_keys_rejected"
    blocking_reason = (
        "No Gemini API keys are configured."
        if not api_keys
        else "All configured Gemini API keys were rejected by Google Generative Language API."
    )
    return {
        "ok": False,
        "reason": reason,
        "blocking_reason": blocking_reason,
        "valid_aliases": valid_aliases,
        "invalid_aliases": invalid_aliases,
        "missing_aliases": sorted(set(missing_aliases)),
    }


def _gemini_key_alert_signature(preflight: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "reason": preflight.get("reason"),
            "invalid_aliases": preflight.get("invalid_aliases", []),
            "missing_aliases": preflight.get("missing_aliases", []),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _gemini_key_alert_message(
    preflight: Dict[str, Any],
    *,
    pending_count: int,
    next_item: Optional[Dict[str, Any]] = None,
) -> str:
    invalid = preflight.get("invalid_aliases") if isinstance(preflight.get("invalid_aliases"), list) else []
    invalid_parts = []
    for item in invalid:
        if not isinstance(item, dict):
            continue
        alias = str(item.get("alias") or "unknown")
        status = str(item.get("google_status") or item.get("http_status") or "rejected")
        message = str(item.get("message_summary") or "").strip()
        invalid_parts.append(f"{alias}: {status} {message}".strip())
    invalid_text = "\n".join(invalid_parts) if invalid_parts else "(no configured key was rejected)"
    missing = preflight.get("missing_aliases") if isinstance(preflight.get("missing_aliases"), list) else []
    configured_count = len(preflight.get("valid_aliases") or []) + len(invalid_parts)
    if configured_count <= 0:
        key_section_title = "Configured Gemini keys:"
        key_section = "No Gemini API keys are stored. Add at least one key in Settings, then run the queue again."
    else:
        key_section_title = "Rejected configured Gemini keys:"
        key_section = invalid_text
        if missing:
            key_section += "\n\nEmpty key slots are unused capacity, not a failure."
    next_number = str((next_item or {}).get("planned_number") or "").strip() or "(unknown)"
    next_name = str((next_item or {}).get("product_name") or "").strip()
    next_line = f"{next_number} {next_name}".strip()
    return (
        "Summer Coupang automation stopped before consuming the next queue item.\n\n"
        f"Reason: {preflight.get('blocking_reason') or preflight.get('reason')}\n"
        f"Next item: {next_line}\n"
        f"Pending items: {pending_count}\n\n"
        f"{key_section_title}\n"
        f"{key_section}\n\n"
        "Open Settings > Gemini API keys, add or replace the configured key(s), then run the queue again."
    )


def _launch_windows_message_box(title: str, message: str) -> bool:
    if os.name != "nt":
        return False
    try:
        ps_title = title.replace("'", "''")
        ps_message = message.replace("'", "''")
        command = (
            "Add-Type -AssemblyName PresentationFramework; "
            f"[System.Windows.MessageBox]::Show('{ps_message}', '{ps_title}', 'OK', 'Warning') | Out-Null"
        )
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-Command",
                command,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def _launch_branded_gemini_key_alert(alert_path: Path) -> bool:
    if os.name != "nt":
        return False
    if not GEMINI_KEY_ALERT_DIALOG_SCRIPT.exists():
        return False
    if importlib.util.find_spec("PyQt6") is None:
        return False
    try:
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "windows"
        subprocess.Popen(
            [
                sys.executable,
                str(GEMINI_KEY_ALERT_DIALOG_SCRIPT),
                "--alert-json",
                str(alert_path),
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def _launch_gemini_key_alert(alert_path: Path, title: str, message: str) -> bool:
    return _launch_branded_gemini_key_alert(alert_path) or _launch_windows_message_box(title, message)


def maybe_show_gemini_key_alert(
    preflight: Dict[str, Any],
    *,
    pending_count: int,
    next_item: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now_ts = time.time()
    try:
        throttle_seconds = int(os.environ.get(GEMINI_KEY_ALERT_THROTTLE_SECONDS_ENV, "43200"))
    except ValueError:
        throttle_seconds = 43200
    signature = _gemini_key_alert_signature(preflight)
    previous: Dict[str, Any] = {}
    if GEMINI_KEY_ALERT_PATH.exists():
        try:
            previous = json.loads(GEMINI_KEY_ALERT_PATH.read_text(encoding="utf-8"))
        except Exception:
            previous = {}

    last_popup_at = float(previous.get("last_popup_at") or 0)
    popup_throttled = (
        previous.get("signature") == signature
        and throttle_seconds > 0
        and now_ts - last_popup_at < throttle_seconds
    )
    message = _gemini_key_alert_message(
        preflight,
        pending_count=pending_count,
        next_item=next_item,
    )
    popup_launched = False

    payload = {
        "updated_at": now_local(),
        "signature": signature,
        "last_popup_at": last_popup_at,
        "popup_launched": popup_launched,
        "popup_throttled": popup_throttled,
        "pending_count": pending_count,
        "next_planned_number": str((next_item or {}).get("planned_number") or ""),
        "next_product_name": str((next_item or {}).get("product_name") or ""),
        "preflight": preflight,
        "message": message,
    }
    GEMINI_KEY_ALERT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEMINI_KEY_ALERT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not popup_throttled:
        popup_launched = _launch_gemini_key_alert(
            GEMINI_KEY_ALERT_PATH,
            "SSMaker Gemini API key error",
            message,
        )
        last_popup_at = now_ts if popup_launched else last_popup_at
        payload["popup_launched"] = popup_launched
        payload["last_popup_at"] = last_popup_at
        GEMINI_KEY_ALERT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return payload


def mark_gemini_key_alert_resolved(preflight: Dict[str, Any]) -> None:
    if not GEMINI_KEY_ALERT_PATH.exists():
        return
    payload = {
        "updated_at": now_local(),
        "resolved_at": now_local(),
        "reason": "gemini_api_key_available",
        "valid_aliases": preflight.get("valid_aliases", []),
        "missing_aliases": preflight.get("missing_aliases", []),
        "message": "Gemini API key preflight is now passing.",
    }
    GEMINI_KEY_ALERT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def gemini_api_key_preflight_ready(
    *,
    pending_count: int,
    next_item: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not gemini_key_preflight_enabled():
        return {"ok": True, "reason": "gemini_preflight_disabled"}
    preflight = probe_configured_gemini_api_keys()
    if preflight.get("ok"):
        mark_gemini_key_alert_resolved(preflight)
        return preflight
    alert = maybe_show_gemini_key_alert(
        preflight,
        pending_count=pending_count,
        next_item=next_item,
    )
    return {
        **preflight,
        "alert_path": str(GEMINI_KEY_ALERT_PATH),
        "popup_launched": bool(alert.get("popup_launched")),
        "popup_throttled": bool(alert.get("popup_throttled")),
    }


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


def _item_similarity(item: Dict[str, Any]) -> Optional[float]:
    raw = (item.get("product") or {}).get("score")
    if raw is None:
        raw = item.get("similarity")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _source_label(item: Dict[str, Any]) -> str:
    source = str(item.get("source") or (item.get("product") or {}).get("source") or "").lower()
    return source.strip()


def is_verified_marketplace_demo_item(item: Dict[str, Any], min_similarity: float) -> bool:
    source = _source_label(item)
    if source in {"", "coupang", "coupang_image"}:
        return False
    if not item.get("video_file"):
        return False
    similarity = _item_similarity(item)
    if similarity is None or similarity < min_similarity:
        return False
    if str(item.get("fallback_reason") or "").strip():
        return False
    if item.get("requires_review"):
        return False
    return bool(item.get("auto_publish_safe"))


def select_safe_marketplace_item(report: Dict[str, Any], min_similarity: float) -> Optional[Dict[str, Any]]:
    sourced_items = report.get("sourced_products") or []
    if report.get("match_status") == "matched":
        for item in sourced_items:
            if is_verified_marketplace_demo_item(item, min_similarity):
                return item

    return None


def validate_render_upload_quality(rendered: Dict[str, Any]) -> Dict[str, Any]:
    final_video = str(rendered.get("final_video") or "")
    probe = dict(rendered.get("video_probe") or {})
    reasons: List[str] = []

    if not final_video or not Path(final_video).exists():
        reasons.append("final_video_missing")
        file_size = 0
    else:
        file_size = Path(final_video).stat().st_size
        if file_size < MIN_FINAL_VIDEO_BYTES:
            reasons.append("final_video_too_small")

    if not rendered.get("render_ok"):
        reasons.append("render_ok_false")

    if not probe and final_video and Path(final_video).exists():
        try:
            probe = renderer.verify_video(final_video)
        except Exception as exc:
            probe = {"error": str(exc)}
            reasons.append("video_probe_failed")

    duration = 0.0
    try:
        duration = float(probe.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration < MIN_FINAL_VIDEO_SECONDS:
        reasons.append("duration_too_short")
    if duration > MAX_FINAL_VIDEO_SECONDS:
        reasons.append("duration_too_long")
    if not probe.get("has_audio"):
        reasons.append("missing_audio")
    if not probe.get("is_vertical_1080x1920"):
        reasons.append("not_vertical_1080x1920")
    if int(rendered.get("tts_segment_count") or 0) <= 0:
        reasons.append("missing_tts_segments")

    integrity = rendered.get("render_integrity") if isinstance(rendered.get("render_integrity"), dict) else {}
    if integrity and not integrity.get("ok"):
        reasons.append("render_integrity_failed")

    return {
        "ok": not reasons,
        "reasons": reasons,
        "probe": probe,
        "file_size_bytes": file_size,
        "min_duration_seconds": MIN_FINAL_VIDEO_SECONDS,
        "max_duration_seconds": MAX_FINAL_VIDEO_SECONDS,
        "min_file_size_bytes": MIN_FINAL_VIDEO_BYTES,
    }


def is_render_quality_gate_exception(exc: Exception) -> bool:
    text = str(exc or "").strip().lower()
    markers = (
        "no generated video for job",
        "render pipeline did not produce a result",
        "render verification failed",
        "duration_too_short",
        "video too short",
        "too short",
        "minimum duration",
    )
    return any(marker in text for marker in markers)


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
        fallback_product_name=str(item.get("product_name") or ""),
        fallback_category=str(item.get("category") or ""),
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
    result["upload_quality"] = validate_render_upload_quality(result)
    result_path = run_dir / "rendered" / "render_result.json"
    write_json(result_path, result)
    result["_render_result_path"] = str(result_path)
    return result


def _metadata_from_queue_item(item: Dict[str, Any]) -> Dict[str, Any]:
    metadata = item.get("upload_metadata")
    if isinstance(metadata, dict):
        return {key: deepcopy(value) for key, value in metadata.items()}
    return {}


def build_summer_upload_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    category = str(item.get("category") or "").strip()
    base = deepcopy(SUMMER_UPLOAD_METADATA.get(category) or DEFAULT_SUMMER_UPLOAD_METADATA)
    base.update({key: value for key, value in _metadata_from_queue_item(item).items() if value})
    tags = base.get("tags") or DEFAULT_SUMMER_UPLOAD_METADATA["tags"]
    base["tags"] = [str(tag).strip().lstrip("#") for tag in tags if str(tag).strip()]
    return base


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
    marker = YouTubeManager.format_upload_number(upload_number)
    metadata = build_summer_upload_metadata(item)
    title = YouTubeManager.ensure_coupang_title_compliance(
        str(metadata.get("title") or DEFAULT_SUMMER_UPLOAD_METADATA["title"]),
        marker_position="suffix",
    )
    linktree_url = DEFAULT_LINKTREE_PROFILE_URL
    summary_line = str(metadata.get("line") or DEFAULT_SUMMER_UPLOAD_METADATA["line"]).strip()
    situation = str(metadata.get("situation") or DEFAULT_SUMMER_UPLOAD_METADATA["situation"]).strip()
    summary_product_line = "상품: " + YouTubeManager.apply_upload_number_to_product_text(
        summary_line or product_name,
        upload_number,
        limit=220,
    )
    desc_lines = [
        f"{marker} {summary_line}".strip(),
        summary_product_line,
        f"구매 링크는 프로필 Linktree에서 {marker} 검색하면 바로 확인할 수 있습니다.",
        f"링크 모음: {linktree_url}",
        f"구매 링크: {purchase_url}",
        COUPANG_AFFILIATE_DISCLOSURE,
        "",
        situation,
        f"원상품명: {product_title}",
    ]
    description = YouTubeManager.apply_upload_number_to_description(
        YouTubeManager.ensure_coupang_affiliate_compliance("\n".join(desc_lines), purchase_url),
        upload_number,
        product_text=summary_line or product_name,
    )
    tags = metadata.get("tags") or DEFAULT_SUMMER_UPLOAD_METADATA["tags"]

    return {
        "video_path": rendered["final_video"],
        "title": title,
        "description": description,
        "tags": tags,
        "product_info": product_name,
        "product_description": summary_line or product_name,
        "product_name": product_name,
        "source_url": str(item.get("coupang_url") or ""),
        "coupang_deep_link": purchase_url,
        "linktree_url": linktree_url,
        "upload_number": upload_number,
        "paid_marker_position": "suffix",
        "summer_upload_metadata": metadata,
        "privacy": privacy,
        "render_integrity": rendered.get("render_integrity") or {},
        "render_integrity_required": True,
        "upload_quality": rendered.get("upload_quality") or {},
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
        "has_problem_hook_title": not title.strip().startswith(COUPANG_PAID_PROMOTION_TITLE_MARKER),
        "has_paid_marker_title": COUPANG_PAID_PROMOTION_TITLE_MARKER in title,
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
                metadata["has_problem_hook_title"],
                metadata["has_paid_marker_title"],
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


def env_int(name: str, default: int, *, min_value: int = 1) -> int:
    try:
        return max(min_value, int(str(os.environ.get(name, default)).strip()))
    except (TypeError, ValueError):
        return default


def env_float(name: str, default: float, *, min_value: float = 0.0) -> float:
    try:
        return max(min_value, float(str(os.environ.get(name, default)).strip()))
    except (TypeError, ValueError):
        return default


def publish_linktree_if_possible(item: Dict[str, Any], product_name: str, purchase_url: str) -> Dict[str, Any]:
    manager = get_linktree_manager()
    upload_number = parse_upload_number(item.get("planned_number"))
    marker = manager.format_publish_index(upload_number)
    title = manager._build_numbered_product_title(product_name, upload_number)
    source_url = str(item.get("coupang_url") or "")

    settings = manager.get_settings()
    webhook_url = str(settings.get("webhook_url", "") or "").strip()
    public_check = verify_linktree_public_card(marker, purchase_url)
    if public_check.get("ok"):
        return {
            "ok": True,
            "method": "public_existing",
            "title": title,
            "number": marker,
            "purchase_url": purchase_url,
            "profile_url": manager.get_profile_url(),
            "public_verification": public_check,
            "blocking_reason": "",
        }

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
    public_check = verify_linktree_public_card(
        marker,
        purchase_url,
        attempts=env_int(
            LINKTREE_PUBLIC_VERIFY_ATTEMPTS_ENV,
            DEFAULT_LINKTREE_PUBLIC_VERIFY_ATTEMPTS,
        ),
        delay_seconds=env_float(
            LINKTREE_PUBLIC_VERIFY_INTERVAL_ENV,
            DEFAULT_LINKTREE_PUBLIC_VERIFY_INTERVAL_SECONDS,
        ),
    )
    method = "webhook" if webhook_url else "browser"
    blocking_reason = ""
    if not ok:
        blocking_reason = "Linktree publish call failed."
    elif not public_check.get("ok"):
        blocking_reason = "Linktree publish did not verify on the public page."
    return {
        "ok": bool(ok and public_check.get("ok")),
        "method": method,
        "webhook_sent": bool(ok and webhook_url),
        "title": title,
        "number": marker,
        "purchase_url": purchase_url,
        "profile_url": manager.get_profile_url(),
        "public_verification": public_check,
        "blocking_reason": blocking_reason,
    }


def verify_linktree_public_card(
    number: str,
    purchase_url: str,
    *,
    attempts: int = 1,
    delay_seconds: float = 0.0,
) -> Dict[str, Any]:
    import requests

    profile_url = DEFAULT_LINKTREE_PROFILE_URL
    attempts = max(1, int(attempts or 1))
    delay_seconds = max(0.0, float(delay_seconds or 0.0))
    last_result: Dict[str, Any] = {
        "ok": False,
        "url": profile_url,
        "status_code": 0,
        "has_number": False,
        "has_purchase_url": False,
        "attempts": 0,
    }
    for attempt in range(1, attempts + 1):
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
            text = response.text
            last_result = {
                "ok": response.status_code == 200 and number in text and purchase_url in text,
                "url": profile_url,
                "status_code": response.status_code,
                "has_number": number in text,
                "has_purchase_url": purchase_url in text,
                "attempts": attempt,
            }
        except Exception as exc:
            last_result = {
                "ok": False,
                "url": profile_url,
                "status_code": 0,
                "has_number": False,
                "has_purchase_url": False,
                "error": str(exc),
                "attempts": attempt,
            }
        if last_result.get("ok"):
            return last_result
        if attempt < attempts and delay_seconds:
            time.sleep(delay_seconds)
    return last_result


def update_item_attempt(item: Dict[str, Any]) -> None:
    item["attempts"] = int(item.get("attempts", 0) or 0) + 1
    item["last_attempt_at"] = now_local()


def pending_item_count(queue_payload: Dict[str, Any]) -> int:
    items: List[Dict[str, Any]] = queue_payload.get("items") or []
    return sum(1 for item in items if is_processable_queue_item(item))


def due_linktree_retry_item_count(
    queue_payload: Dict[str, Any],
    *,
    force_run_now: Optional[bool] = None,
) -> int:
    items: List[Dict[str, Any]] = queue_payload.get("items") or []
    retry_items = [item for item in items if is_linktree_retry_item(item)]
    run_now = force_run_now_enabled() if force_run_now is None else bool(force_run_now)
    if run_now:
        return len(retry_items)
    now = now_datetime()
    return sum(1 for item in retry_items if is_item_due(item, now=now))


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


def linktree_publish_ready() -> Dict[str, Any]:
    try:
        manager = get_linktree_manager()
        if hasattr(manager, "require_connected_for_publish"):
            ok, issue = manager.require_connected_for_publish()
            if ok:
                return {"ok": True}
            return {
                "ok": False,
                "reason": "linktree_not_connected",
                "blocking_reason": str(issue or "Linktree publish path is not connected."),
            }
        if hasattr(manager, "is_connected") and manager.is_connected():
            return {"ok": True}
        return {
            "ok": False,
            "reason": "linktree_not_connected",
            "blocking_reason": "Linktree publish path is not connected.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "reason": "linktree_preflight_error",
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


async def process_pending_items(
    queue_payload: Dict[str, Any],
    *,
    force_run_now: Optional[bool] = None,
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = queue_payload.get("items") or []
    pending = [item for item in items if is_processable_queue_item(item)]
    if not pending:
        return {"processed": False, "reason": "no_pending_items"}

    run_now = force_run_now_enabled() if force_run_now is None else bool(force_run_now)
    now = now_datetime()
    due_pending = [item for item in pending if is_item_due(item, now=now)]
    if not due_pending and run_now:
        due_pending = [pending[0]]
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
    policy = queue_payload.get("automation_policy") or {}
    continue_after_skip = bool(
        policy.get(
            "continue_after_skip_until_completed",
            DEFAULT_CONTINUE_AFTER_SKIP_UNTIL_COMPLETED,
        )
    )
    try:
        max_candidates = int(
            policy.get(
                "max_candidate_items_per_run",
                DEFAULT_MAX_CANDIDATE_ITEMS_PER_RUN,
            )
            or DEFAULT_MAX_CANDIDATE_ITEMS_PER_RUN
        )
    except (TypeError, ValueError):
        max_candidates = DEFAULT_MAX_CANDIDATE_ITEMS_PER_RUN
    first_due_item = due_pending[0]
    first_due_index = next(
        (idx for idx, item in enumerate(pending) if item is first_due_item),
        0,
    )
    if continue_after_skip:
        max_candidates = max(1, len(pending) - first_due_index)
    else:
        max_candidates = max(1, max_candidates)
    candidate_items = pending[first_due_index : first_due_index + max_candidates]
    skipped_items: List[Dict[str, Any]] = []

    for item in candidate_items:
        if is_linktree_retry_item(item):
            retry_context = linktree_retry_context(item)
            update_item_attempt(item)
            save_queue(queue_payload)
            if not retry_context["purchase_url"]:
                linktree_result = {
                    "ok": False,
                    "method": "blocked",
                    "title": "",
                    "number": get_linktree_manager().format_publish_index(
                        parse_upload_number(item.get("planned_number"))
                    ),
                    "purchase_url": "",
                    "profile_url": get_linktree_manager().get_profile_url(),
                    "public_verification": {},
                    "blocking_reason": "Cannot retry Linktree publish because the queue item has no purchase URL.",
                }
            else:
                linktree_result = publish_linktree_if_possible(
                    item,
                    retry_context["product_name"],
                    retry_context["purchase_url"],
                )
            attach_result(
                item,
                status=linktree_failure_status(linktree_result),
                render_path=retry_context["render_path"],
                youtube_url=retry_context["youtube_url"],
                linktree_result=linktree_result,
                blocking_reason=str(linktree_result.get("blocking_reason") or ""),
                extra={
                    "purchase_url": retry_context["purchase_url"],
                    "linktree_retry_only": True,
                },
            )
            save_queue(queue_payload)
            return linktree_retry_summary(item, linktree_result, run_now=run_now)

        duplicate_reason = duplicate_upload_reason(item, queue_payload)
        if duplicate_reason:
            attach_result(
                item,
                status="skipped_duplicate_product",
                blocking_reason=duplicate_reason,
                extra={
                    "duplicate_policy": duplicate_policy(queue_payload),
                    "purchase_url": determine_purchase_url(item, {}),
                },
            )
            save_queue(queue_payload)
            skipped_items.append(
                {
                    "planned_number": item.get("planned_number"),
                    "status": "skipped_duplicate_product",
                    "reason": duplicate_reason,
                }
            )
            continue

        update_item_attempt(item)
        save_queue(queue_payload)

        run_dir = build_run_dir(item)
        report = await run_sourcing(item, run_dir, min_similarity)
        safe_item = select_safe_marketplace_item(report, min_similarity)
        similarity = report.get("best_similarity")
        product_name = str((report.get("product_info") or {}).get("name") or item.get("product_name") or "").strip()

        duplicate_reason = duplicate_upload_reason(item, queue_payload, product_name=product_name)
        if duplicate_reason:
            attach_result(
                item,
                status="skipped_duplicate_product",
                similarity=similarity,
                blocking_reason=duplicate_reason,
                extra={
                    "match_status": report.get("match_status"),
                    "report_path": report.get("_report_path", ""),
                    "purchase_url": determine_purchase_url(item, report),
                    "run_dir": str(run_dir),
                    "duplicate_policy": duplicate_policy(queue_payload),
                },
            )
            save_queue(queue_payload)
            skipped_items.append(
                {
                    "planned_number": item.get("planned_number"),
                    "status": "skipped_duplicate_product",
                    "reason": duplicate_reason,
                }
            )
            continue

        if not safe_item:
            reason = str(report.get("match_error") or report.get("error") or "No safe marketplace video matched the threshold.")
            if is_system_sourcing_blocker(report, reason):
                attach_result(
                    item,
                    status="failed",
                    similarity=similarity,
                    blocking_reason=reason,
                    extra={
                        "match_status": report.get("match_status"),
                        "report_path": report.get("_report_path", ""),
                        "purchase_url": determine_purchase_url(item, report),
                        "run_dir": str(run_dir),
                    },
                )
                save_queue(queue_payload)
                summary = {
                    "processed": True,
                    "status": "failed",
                    "planned_number": item.get("planned_number"),
                    "error": reason,
                    "blocking_type": "sourcing_system_blocker",
                }
                if skipped_items:
                    summary["skipped_before"] = skipped_items
                    summary["skip_count"] = len(skipped_items)
                if run_now:
                    summary["run_now"] = True
                return summary
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
            skipped_items.append(
                {
                    "planned_number": item.get("planned_number"),
                    "status": "skipped_low_similarity",
                    "reason": reason,
                }
            )
            continue

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
            upload_quality = rendered.get("upload_quality") or validate_render_upload_quality(rendered)
            if not rendered.get("render_ok") or not upload_quality.get("ok"):
                reason = "Render upload quality gate failed: " + ", ".join(
                    upload_quality.get("reasons") or ["render_ok_false"]
                )
                attach_result(
                    item,
                    status="skipped_quality_gate",
                    similarity=similarity,
                    render_path=str(rendered.get("final_video") or ""),
                    blocking_reason=reason,
                    extra={
                        "match_status": report.get("match_status"),
                        "report_path": report.get("_report_path", ""),
                        "render_result_path": rendered.get("_render_result_path", ""),
                        "purchase_url": purchase_url,
                        "upload_quality": upload_quality,
                        "run_dir": str(run_dir),
                    },
                )
                save_queue(queue_payload)
                skipped_items.append(
                    {
                        "planned_number": item.get("planned_number"),
                        "status": "skipped_quality_gate",
                        "reason": reason,
                    }
                )
                continue

            upload_item = build_upload_item(rendered, item, report, purchase_url, privacy)
            uploaded = upload_verified_render(upload_item, privacy)
            youtube_verification = verify_youtube(upload_item, uploaded)
            if not youtube_verification.get("ok"):
                raise RuntimeError("YouTube metadata/comment verification failed.")

            linktree_result = publish_linktree_if_possible(item, product_name, purchase_url)
            final_status = linktree_failure_status(linktree_result)
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
                    "upload_quality": upload_quality,
                    "run_dir": str(run_dir),
                },
            )
            save_queue(queue_payload)
            summary = {
                "processed": True,
                "status": final_status,
                "planned_number": item.get("planned_number"),
                "youtube_url": uploaded.get("video_url", ""),
                "linktree_ok": linktree_result.get("ok", False),
            }
            if final_status == LINKTREE_RETRY_STATUS:
                summary["linktree_retry"] = True
                summary["blocking_type"] = "linktree_publish_pending"
                summary["blocking_reason"] = str(linktree_result.get("blocking_reason") or "")
            if run_now:
                summary["run_now"] = True
            if skipped_items:
                summary["skipped_before"] = skipped_items
                summary["skip_count"] = len(skipped_items)
            return summary
        except Exception as exc:
            if is_render_quality_gate_exception(exc):
                upload_quality = locals().get("upload_quality")
                if not isinstance(upload_quality, dict):
                    upload_quality = {
                        "ok": False,
                        "reasons": ["render_exception"],
                    }
                reason = "Render upload quality gate failed: " + str(exc)
                attach_result(
                    item,
                    status="skipped_quality_gate",
                    similarity=similarity,
                    render_path=str((run_dir / "rendered").resolve()),
                    blocking_reason=reason,
                    extra={
                        "match_status": report.get("match_status"),
                        "report_path": report.get("_report_path", ""),
                        "purchase_url": purchase_url,
                        "upload_quality": upload_quality,
                        "run_dir": str(run_dir),
                    },
                )
                save_queue(queue_payload)
                skipped_items.append(
                    {
                        "planned_number": item.get("planned_number"),
                        "status": "skipped_quality_gate",
                        "reason": reason,
                    }
                )
                continue

            attach_result(
                item,
                status="failed",
                similarity=similarity,
                render_path=str((run_dir / "rendered").resolve()),
                blocking_reason=str(exc),
                extra={
                    "report_path": report.get("_report_path", ""),
                    "purchase_url": purchase_url,
                    "upload_quality": locals().get("upload_quality", {}),
                    "run_dir": str(run_dir),
                },
            )
            save_queue(queue_payload)
            return {
                "processed": True,
                "status": "failed",
                "planned_number": item.get("planned_number"),
                "error": str(exc),
                **({"run_now": True} if run_now else {}),
            }

    if skipped_items:
        skipped_statuses = {
            str(item.get("status") or "skipped_low_similarity")
            for item in skipped_items
        }
        final_skip_status = (
            "skipped_duplicate_product"
            if skipped_statuses == {"skipped_duplicate_product"}
            else "skipped_low_similarity"
        )
        return {
            "processed": True,
            "status": final_skip_status,
            "reason": "all_candidate_items_skipped",
            "skip_count": len(skipped_items),
            "skipped_items": skipped_items,
            **({"run_now": True} if run_now else {}),
        }

    return {"processed": False, "reason": "all_pending_items_skipped_low_similarity"}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Summer Coupang queue cycle.")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Process the first pending item immediately, even if its scheduled_at is in the future.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args([] if argv is None else argv)
    queue_payload = load_queue()
    pending_count = pending_item_count(queue_payload)
    upload_required_count = youtube_upload_required_item_count(queue_payload)
    linktree_retry_due_count = due_linktree_retry_item_count(
        queue_payload,
        force_run_now=args.run_now or None,
    )
    if pending_count and upload_required_count and not linktree_retry_due_count:
        linktree_state = linktree_publish_ready()
        if not linktree_state.get("ok"):
            print(
                json.dumps(
                    {
                        "processed": False,
                        "reason": linktree_state.get("reason", "linktree_not_ready"),
                        "pending_count": pending_count,
                        "upload_required_count": upload_required_count,
                        "linktree_retry_due_count": linktree_retry_due_count,
                        "blocking_reason": linktree_state.get("blocking_reason", ""),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                flush=True,
            )
            return 1

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
            return 1

        due_upload_items = due_upload_required_items(
            queue_payload,
            force_run_now=args.run_now or None,
        )
        if due_upload_items:
            gemini_state = gemini_api_key_preflight_ready(
                pending_count=pending_count,
                next_item=due_upload_items[0],
            )
            if not gemini_state.get("ok"):
                print(
                    json.dumps(
                        {
                            "processed": False,
                            "reason": gemini_state.get("reason", "gemini_api_keys_rejected"),
                            "pending_count": pending_count,
                            "next_planned_number": due_upload_items[0].get("planned_number", ""),
                            "blocking_reason": gemini_state.get("blocking_reason", ""),
                            "alert_path": gemini_state.get("alert_path", ""),
                            "popup_launched": gemini_state.get("popup_launched", False),
                            "popup_throttled": gemini_state.get("popup_throttled", False),
                            "valid_aliases": gemini_state.get("valid_aliases", []),
                            "invalid_aliases": gemini_state.get("invalid_aliases", []),
                            "missing_aliases": gemini_state.get("missing_aliases", []),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    flush=True,
                )
                return 1

    summary = asyncio.run(process_pending_items(queue_payload, force_run_now=args.run_now or None))
    if args.run_now and summary.get("processed"):
        scheduler_next_run = scheduled_task_next_run_time()
        schedule_update = realign_pending_schedule_after_run_now(
            queue_payload,
            first_scheduled_at=scheduler_next_run,
        )
        if schedule_update.get("rescheduled_count"):
            save_queue(queue_payload)
            summary["rescheduled_pending_count"] = schedule_update["rescheduled_count"]
            summary["next_scheduled_at"] = schedule_update["next_scheduled_at"]
            summary["interval_minutes"] = schedule_update["interval_minutes"]
            if scheduler_next_run is not None:
                summary["scheduler_next_run"] = scheduler_next_run.isoformat(timespec="seconds")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    if summary.get("status") in SUCCESS_FINAL_STATUSES:
        return 0
    if summary.get("status") == LINKTREE_RETRY_STATUS:
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
    raise SystemExit(main(sys.argv[1:]))
