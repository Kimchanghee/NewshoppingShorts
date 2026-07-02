"""User-facing error message helpers.

Keep technical provider/API details in logs, but do not show raw HTTP payloads,
dicts, or exception strings in the app UI.
"""

from __future__ import annotations

import ast
import re
from typing import Any


RAW_DETAIL_TOKENS = (
    "blocking_reason",
    "invalid_aliases",
    "missing_aliases",
    "message_summary",
    "google_status",
    "google_code",
    "http_status",
    "PERMISSION_DENIED",
    "RESOURCE_EXHAUSTED",
    "INVALID_ARGUMENT",
    "All configured Gemini API keys",
    "Google Generative Language API",
    "Traceback",
    "Exception:",
    "WinError",
    "Errno",
    "FileNotFoundError",
    "ConnectionError",
    "TimeoutError",
    "HTTPError",
    "KeyError",
    "ValueError",
    "RuntimeError",
    "PermissionError",
    "SSLError",
    "Linktree publish failed",
    "leaving the YouTube upload",
    "Render upload quality gate failed",
    "No generated video",
    "Duplicate product family",
    "Duplicate product name",
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _parse_mappingish_text(text: str) -> dict[str, Any]:
    """Best-effort parse for strings like "{'alias': 'api_1', ...}"."""
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return {}
    try:
        parsed = ast.literal_eval(stripped)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def _looks_question_mark_mojibake(text: str) -> bool:
    compact = re.sub(r"[\s./,:;()\\[\]{}_-]+", "", text.strip())
    if len(compact) < 8:
        return False
    question_count = compact.count("?")
    return question_count >= 4 and question_count / max(len(compact), 1) >= 0.35


def classify_error(value: Any) -> str:
    """Return a stable category for common app/provider failures."""
    text = _stringify(value)
    mapping = value if isinstance(value, dict) else _parse_mappingish_text(text)
    combined = " ".join(
        _stringify(part)
        for part in (
            text,
            mapping.get("reason") if mapping else "",
            mapping.get("blocking_reason") if mapping else "",
            mapping.get("google_status") if mapping else "",
            mapping.get("message_summary") if mapping else "",
            mapping.get("http_status") if mapping else "",
            mapping.get("google_code") if mapping else "",
        )
    ).lower()

    if "gemini_api_keys_missing" in combined or "no gemini api keys" in combined:
        return "gemini_key_missing"
    if (
        "gemini_api_keys_rejected" in combined
        or "all configured gemini api keys" in combined
        or ("permission_denied" in combined and ("gemini" in combined or "generative language" in combined))
        or ("http_status" in combined and "403" in combined and "gemini" in combined)
    ):
        return "gemini_key_rejected"
    if "resource_exhausted" in combined or "quota" in combined or re.search(r"\b429\b", combined):
        return "quota_exhausted"
    if "api_key_invalid" in combined or "api key not valid" in combined or "api key expired" in combined:
        return "api_key_invalid"
    if "youtube_not_connected" in combined or "youtube" in combined and "not connected" in combined:
        return "youtube_not_connected"
    if "invalid_grant" in combined or "token has been expired or revoked" in combined:
        return "youtube_reconnect"
    if "linktree_not_connected" in combined:
        return "linktree_not_connected"
    if (
        "linktree publish failed after" in combined
        or "retry_exhausted" in combined and "linktree" in combined
        or "linktree publish did not verify" in combined
        or "linktree publish call failed" in combined
    ):
        return "linktree_publish_failed"
    if (
        "render upload quality gate failed" in combined
        or "duration_too_short" in combined
        or "no generated video" in combined
    ):
        return "render_quality_failed"
    if "duplicate product family" in combined or "duplicate product name" in combined:
        return "duplicate_product"
    if "permission_denied" in combined or re.search(r"\b403\b", combined):
        return "permission_denied"
    if "timeout" in combined or "timed out" in combined or "connectionerror" in combined:
        return "network"
    if "no_due_items" in combined:
        return "no_due_items"
    if "no_pending_items" in combined:
        return "no_pending_items"
    if "file not found" in combined or "no such file" in combined:
        return "file_missing"
    return "unknown"


def friendly_error_title(value: Any, fallback: str = "잠시 문제가 생겼어요") -> str:
    category = classify_error(value)
    return {
        "gemini_key_missing": "Gemini API 키가 필요해요",
        "gemini_key_rejected": "Gemini API 키를 사용할 수 없어요",
        "quota_exhausted": "API 사용량이 잠시 꽉 찼어요",
        "api_key_invalid": "API 키를 다시 확인해 주세요",
        "youtube_not_connected": "YouTube 연결이 필요해요",
        "youtube_reconnect": "YouTube를 다시 연결해 주세요",
        "linktree_not_connected": "Linktree 연결이 필요해요",
        "linktree_publish_failed": "Linktree 자동 등록을 확인해 주세요",
        "render_quality_failed": "영상 품질 확인이 필요해요",
        "duplicate_product": "중복 상품으로 보류됐어요",
        "permission_denied": "권한 확인이 필요해요",
        "network": "네트워크 연결을 확인해 주세요",
        "no_due_items": "아직 실행 시간이 아니에요",
        "no_pending_items": "대기 중인 작업이 없어요",
        "file_missing": "필요한 파일을 찾지 못했어요",
    }.get(category, fallback)


def friendly_error_message(value: Any, fallback: str = "잠시 후 다시 시도해 주세요.") -> str:
    category = classify_error(value)
    return {
        "gemini_key_missing": (
            "저장된 Gemini API 키가 없어서 작업을 시작할 수 없어요.\n"
            "설정 > API 키에서 새 키를 저장한 뒤 다시 실행해 주세요."
        ),
        "gemini_key_rejected": (
            "저장된 Gemini API 키는 있지만 Google에서 사용 권한을 거절했어요.\n"
            "Google AI Studio에서 새 API 키를 발급해 교체하거나, 현재 키의 API 제한/프로젝트 권한을 확인해 주세요."
        ),
        "quota_exhausted": (
            "현재 API 사용량이 한도에 도달했어요.\n"
            "잠시 후 다시 시도하거나 다른 Gemini API 키를 추가해 주세요."
        ),
        "api_key_invalid": (
            "저장된 API 키가 만료되었거나 형식이 맞지 않아요.\n"
            "설정 > API 키에서 새 Gemini API 키로 교체해 주세요."
        ),
        "youtube_not_connected": (
            "YouTube 채널 연결이 확인되지 않았어요.\n"
            "설정에서 YouTube 연결을 완료한 뒤 다시 실행해 주세요."
        ),
        "youtube_reconnect": (
            "YouTube 인증이 만료되었어요.\n"
            "설정에서 YouTube를 한 번 다시 연결해 주세요."
        ),
        "linktree_not_connected": (
            "Linktree 연결 정보가 아직 준비되지 않았어요.\n"
            "설정에서 Linktree 주소와 자동 등록 설정을 확인해 주세요."
        ),
        "linktree_publish_failed": (
            "Linktree 자동 등록을 완료하지 못했어요.\n"
            "YouTube 업로드 기록은 유지되어 있으니, Linktree 연결 상태를 확인한 뒤 다시 시도해 주세요."
        ),
        "render_quality_failed": (
            "생성된 영상이 자동 업로드 기준을 통과하지 못했어요.\n"
            "영상 파일이 만들어졌는지와 길이/형식을 확인한 뒤 다시 시도해 주세요."
        ),
        "duplicate_product": (
            "이미 처리한 상품과 너무 비슷해 자동 진행을 멈췄어요.\n"
            "다른 상품 링크로 다시 시도해 주세요."
        ),
        "permission_denied": (
            "현재 계정이나 키에 필요한 권한이 없어요.\n"
            "연결된 계정, API 키 권한, 공유 설정을 확인해 주세요."
        ),
        "network": (
            "외부 서비스와 연결이 원활하지 않아요.\n"
            "인터넷 연결을 확인한 뒤 잠시 후 다시 시도해 주세요."
        ),
        "no_due_items": "예약된 다음 실행 시간이 아직 오지 않았어요.",
        "no_pending_items": "지금 처리할 대기 작업이 없어요.",
        "file_missing": "작업에 필요한 파일을 찾지 못했어요. 파일 위치를 확인해 주세요.",
    }.get(category, fallback)


def looks_developer_facing(value: Any) -> bool:
    text = _stringify(value)
    if isinstance(value, (dict, list, tuple)):
        return True
    if _contains_any(text, RAW_DETAIL_TOKENS):
        return True
    if _parse_mappingish_text(text):
        return True
    if re.search(r"\b(?:http_status|google_code|status_code)\s*[:=]\s*\d{3}\b", text, re.IGNORECASE):
        return True
    return False


def _remove_technical_lines(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if _contains_any(stripped, RAW_DETAIL_TOKENS):
            continue
        if _parse_mappingish_text(stripped):
            continue
        if re.search(r"\b(?:http_status|google_code|status_code)\s*[:=]\s*\d{3}\b", stripped, re.IGNORECASE):
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def sanitize_user_message(value: Any, fallback: str = "잠시 후 다시 시도해 주세요.") -> str:
    """Return text safe for end-user UI surfaces."""
    text = _stringify(value)
    if not text:
        return fallback
    if _looks_question_mark_mojibake(text):
        return fallback

    category = classify_error(value)
    if category != "unknown" and looks_developer_facing(value):
        return friendly_error_message(value, fallback=fallback)

    if looks_developer_facing(value):
        cleaned = _remove_technical_lines(text)
        return cleaned or fallback

    text = re.sub(r"\n?\s*\((?:[A-Za-z_]+Error|Exception|HTTPError|TimeoutError)[^)]*\)\s*$", "", text)
    return text.strip() or fallback


def friendly_status(value: Any, fallback_title: str = "확인이 필요해요") -> tuple[str, str]:
    return friendly_error_title(value, fallback=fallback_title), friendly_error_message(value)
