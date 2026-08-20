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
    "OAuth token",
    "KeyError",
    "ValueError",
    "RuntimeError",
    "PermissionError",
    "ModuleNotFoundError",
    "ImportError",
    "JSONDecodeError",
    "UnicodeDecodeError",
    "CalledProcessError",
    "requests.exceptions",
    "urllib3",
    "Trace ID",
    "request_id",
    "stack trace",
    "During handling of the above exception",
    "The above exception was the direct cause",
    "No module named",
    "Max retries exceeded",
    "Failed to establish a new connection",
    "Only one active job is allowed",
    "Finish or clear the current",
    "SSLError",
    "Linktree publish failed",
    "Reconnect the YouTube channel",
    "pending queue items",
    "leaving the YouTube upload",
    "Render upload quality gate failed",
    "No generated video",
    "Duplicate product family",
    "Duplicate product name",
)


_INTERNAL_CODE_LINE = re.compile(
    r"^\s*\[(?:[A-Za-z0-9_.\\/-]+/)?[A-Z][A-Z0-9_-]{2,}\]\s*$"
)
_INTERNAL_CODE = re.compile(
    r"\b(?:ST-[A-Z]\d{3}|EU\d{3}|LOGIN_[A-Z0-9_]+|[A-Z][A-Z0-9]+_[A-Z0-9_]{2,})\b"
)
_EXCEPTION_NAME = re.compile(
    r"\b(?:[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)|Traceback)\b"
)
_HTTP_DETAIL = re.compile(
    r"\b(?:HTTP(?:/\d(?:\.\d)?)?|status(?:_code)?)\s*[:=]?\s*[45]\d{2}\b",
    re.IGNORECASE,
)
_TRACEBACK_DETAIL = re.compile(
    r"(?:^|\s)File\s+[\"'][^\"']+[\"'],\s+line\s+\d+|"
    r"\bat\s+0x[0-9a-f]+\b|\bline\s+\d+,\s+in\s+\w+",
    re.IGNORECASE,
)
_ENGLISH_ERROR_WORDS = re.compile(
    r"\b(?:error|exception|failed|failure|invalid|denied|forbidden|"
    r"not\s+found|timed?\s*out|unavailable|unexpected|cannot|could\s+not|"
    r"only\s+one\s+active\s+job|finish\s+or\s+clear)\b",
    re.IGNORECASE,
)

_SAFE_TITLE_MAP = {
    "done": "완료",
    "success": "완료",
    "error": "오류",
    "warning": "경고",
    "info": "안내",
    "confirm": "확인",
    "confirmation": "확인",
    "connection error": "연결 오류",
    "login failed": "로그인 실패",
    "registration failed": "회원가입 실패",
    "update error": "업데이트 오류",
}

_SIMPLE_STATUS_MAP = {
    "waiting": "대기 중",
    "processing": "진행 중",
    "completed": "완료",
    "done": "완료",
    "failed": "실패",
    "cancelled": "취소됨",
    "canceled": "취소됨",
    "enabled": "사용 중",
    "disabled": "사용 안 함",
    "connected": "연결됨",
    "disconnected": "연결 안 됨",
}


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
    if "\ufffd" in text:
        return True
    compact = re.sub(r"[\s./,:;()\\[\]{}_-]+", "", text.strip())
    question_count = compact.count("?")
    if question_count >= 3 and len(compact) <= 12:
        return True
    if len(compact) < 8:
        return False
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

    sourcing_failure_codes = (
        "browser_start_failed",
        "browser_session_failed",
        "platform_access_blocked",
        "platform_search_unavailable",
        "platform_search_failed",
        "no_search_results",
        "no_relevant_video",
        "candidate_download_failed",
        "all_sources_already_used",
        "unexpected_search_error",
    )
    if (
        "상품 영상 검색에 실패" in combined
        or "상품 영상을 찾지 못" in combined
        or "검색 내역:" in combined
        or any(code in combined for code in sourcing_failure_codes)
    ):
        return "sourcing_video_not_found"

    if (
        "only one active job is allowed" in combined
        or "finish or clear the current" in combined
        or "active_job_exists" in combined
    ):
        return "active_job"
    if (
        "pending approval" in combined
        or "registration_pending" in combined
        or "awaiting approval" in combined
    ):
        return "registration_pending"
    if (
        "invalid credentials" in combined
        or "login_invalid_credentials" in combined
        or "incorrect username or password" in combined
        or "eu001" in combined
    ):
        return "invalid_credentials"
    if (
        "login_already_active" in combined
        or "duplicate login" in combined
        or "eu003" in combined
    ):
        return "duplicate_login"
    if (
        "login_rate_limited" in combined
        or "too many login attempts" in combined
        or "eu005" in combined
    ):
        return "login_rate_limited"

    if "gemini_api_keys_missing" in combined or "no gemini api keys" in combined:
        return "gemini_key_missing"
    if (
        "gemini_api_keys_rejected" in combined
        or "all configured gemini api keys" in combined
        or "your project has been denied access" in combined
        or "dunning decision is deny for project" in combined
        or ("permission_denied" in combined and ("gemini" in combined or "generative language" in combined))
        or ("http_status" in combined and "403" in combined and "gemini" in combined)
    ):
        return "gemini_key_rejected"
    if "resource_exhausted" in combined or "quota" in combined or re.search(r"\b429\b", combined):
        return "quota_exhausted"
    if "api_key_invalid" in combined or "api key not valid" in combined or "api key expired" in combined:
        return "api_key_invalid"
    if "invalid_grant" in combined or "token has been expired or revoked" in combined:
        return "youtube_reconnect"
    if (
        "youtube_not_connected" in combined
        or "oauth token is missing or invalid" in combined
        or "reconnect the youtube channel" in combined
        or ("youtube" in combined and "not connected" in combined)
    ):
        return "youtube_not_connected"
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
    if (
        "timeout" in combined
        or "timed out" in combined
        or "connectionerror" in combined
        or "max retries exceeded" in combined
        or "failed to establish a new connection" in combined
        or "name resolution" in combined
        or "connection refused" in combined
        or "sslerror" in combined
    ):
        return "network"
    if "no_due_items" in combined:
        return "no_due_items"
    if "no_pending_items" in combined:
        return "no_pending_items"
    if "file not found" in combined or "no such file" in combined:
        return "file_missing"
    if "no module named" in combined or "modulenotfounderror" in combined:
        return "feature_missing"
    if "no space left" in combined or "disk full" in combined:
        return "disk_full"
    if (
        "ffmpeg" in combined
        or "calledprocesserror" in combined
        or "encoder" in combined and "failed" in combined
    ):
        return "video_tool"
    return "unknown"


def friendly_error_title(value: Any, fallback: str = "잠시 문제가 생겼어요") -> str:
    category = classify_error(value)
    return {
        "sourcing_video_not_found": "상품 영상을 찾지 못했어요",
        "gemini_key_missing": "Gemini API 키가 필요해요",
        "gemini_key_rejected": "Gemini API 키를 사용할 수 없어요",
        "quota_exhausted": "API 사용량이 잠시 꽉 찼어요",
        "api_key_invalid": "API 키를 다시 확인해 주세요",
        "youtube_not_connected": "YouTube 업로드 권한 만료",
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
        "active_job": "진행 중인 작업이 있어요",
        "registration_pending": "가입 승인 상태를 확인해 주세요",
        "invalid_credentials": "로그인 정보를 확인해 주세요",
        "duplicate_login": "다른 기기에서 사용 중이에요",
        "login_rate_limited": "잠시 후 다시 로그인해 주세요",
        "feature_missing": "필요한 기능을 불러오지 못했어요",
        "disk_full": "저장 공간이 부족해요",
        "video_tool": "영상 처리 기능을 실행하지 못했어요",
    }.get(category, fallback)


def friendly_error_message(value: Any, fallback: str = "잠시 후 다시 시도해 주세요.") -> str:
    category = classify_error(value)
    return {
        "sourcing_video_not_found": (
            "상품 영상을 찾지 못했어요.\n"
            "잠시 후 다시 시도하거나 다른 상품 링크를 사용해 주세요."
        ),
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
        "youtube_not_connected": "설정에서 YouTube를 다시 연결해 주세요.",
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
        "active_job": (
            "이미 대기 중이거나 진행 중인 영상 작업이 있어요.\n"
            "현재 작업을 완료하거나 진행 상황 화면에서 삭제한 뒤 다시 담아 주세요."
        ),
        "registration_pending": "회원가입 승인 상태를 확인한 뒤 다시 시도해 주세요.",
        "invalid_credentials": "아이디 또는 비밀번호가 맞는지 다시 확인해 주세요.",
        "duplicate_login": (
            "다른 기기에서 이미 로그인되어 있어요.\n"
            "기존 기기에서 로그아웃한 뒤 다시 시도해 주세요."
        ),
        "login_rate_limited": (
            "로그인 시도가 잠시 제한됐어요.\n"
            "1분 정도 기다린 뒤 다시 시도해 주세요."
        ),
        "feature_missing": (
            "프로그램에 필요한 기능을 불러오지 못했어요.\n"
            "프로그램을 다시 설치한 뒤 실행해 주세요."
        ),
        "disk_full": "저장 공간이 부족해요. 불필요한 파일을 정리한 뒤 다시 시도해 주세요.",
        "video_tool": (
            "영상 처리 기능을 실행하지 못했어요.\n"
            "프로그램을 다시 실행한 뒤 같은 작업을 다시 시도해 주세요."
        ),
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
    if _INTERNAL_CODE.search(text) or _EXCEPTION_NAME.search(text):
        return True
    if _HTTP_DETAIL.search(text) or _TRACEBACK_DETAIL.search(text):
        return True
    if _looks_like_english_error(text):
        return True
    return False


def _looks_like_english_error(text: str) -> bool:
    if not _ENGLISH_ERROR_WORDS.search(text):
        return False
    hangul_count = len(re.findall(r"[가-힣]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    return latin_count >= 8 and latin_count > hangul_count


def _has_readable_korean(text: str) -> bool:
    return len(re.findall(r"[가-힣]", text)) >= 4


def _clean_mixed_korean_line(line: str) -> str:
    """Keep useful Korean copy while removing an appended raw exception."""
    cleaned = re.sub(
        r"^(?P<bullet>\s*[-•]\s*)?\[(?:[A-Za-z0-9_.\\/-]+/)?"
        r"[A-Z][A-Z0-9_-]{2,}\]\s*(?:[A-Za-z0-9_.-]+\s*:\s*)?",
        lambda match: match.group("bullet") or "",
        line,
    ).strip()
    cleaned = _INTERNAL_CODE.sub("", cleaned).strip()
    cleaned = re.sub(
        r"\s*\((?:[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)|"
        r"HTTP\s*[45]\d{2})[^)]*\)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    if not _has_readable_korean(cleaned):
        return ""

    for separator in (":", "：", " - "):
        if separator not in cleaned:
            continue
        prefix, suffix = cleaned.split(separator, 1)
        if _has_readable_korean(prefix) and (
            _contains_any(suffix, RAW_DETAIL_TOKENS)
            or _EXCEPTION_NAME.search(suffix)
            or _HTTP_DETAIL.search(suffix)
            or _looks_like_english_error(suffix)
        ):
            cleaned = prefix.rstrip(" .") + "."
            break
    return cleaned


def _remove_technical_lines(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if _INTERNAL_CODE_LINE.match(stripped):
            continue
        if _INTERNAL_CODE.search(stripped):
            mixed = _clean_mixed_korean_line(stripped)
            if mixed:
                kept.append(mixed)
            continue
        if _contains_any(stripped, RAW_DETAIL_TOKENS):
            mixed = _clean_mixed_korean_line(stripped)
            if mixed:
                kept.append(mixed)
            continue
        if _parse_mappingish_text(stripped):
            continue
        if re.search(r"\b(?:http_status|google_code|status_code)\s*[:=]\s*\d{3}\b", stripped, re.IGNORECASE):
            continue
        if _EXCEPTION_NAME.search(stripped) or _TRACEBACK_DETAIL.search(stripped):
            mixed = _clean_mixed_korean_line(stripped)
            if mixed:
                kept.append(mixed)
            continue
        if _looks_like_english_error(stripped):
            mixed = _clean_mixed_korean_line(stripped)
            if mixed:
                kept.append(mixed)
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
    text = re.sub(
        r"(?im)^\s*(?:요청\s*(?:ID|아이디)|Request\s*ID)\s*[:=]\s*.*$",
        "",
        text,
    )
    text = re.sub(
        r"\s*(?:\(|\[)?(?:요청\s*(?:ID|아이디)|Request\s*ID)\s*[:=]\s*[^)\]\n]+(?:\)|\])?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    if _looks_question_mark_mojibake(text):
        return fallback
    simple_status = _SIMPLE_STATUS_MAP.get(text.lower())
    if simple_status:
        return simple_status

    category = classify_error(value)
    if category == "sourcing_video_not_found":
        return friendly_error_message(value, fallback=fallback)
    if category != "unknown" and not _has_readable_korean(text):
        return friendly_error_message(value, fallback=fallback)

    if looks_developer_facing(value):
        cleaned = _remove_technical_lines(text)
        if cleaned and _has_readable_korean(cleaned) and not looks_developer_facing(cleaned):
            return cleaned
        if category != "unknown":
            return friendly_error_message(value, fallback=fallback)
        return fallback

    text = re.sub(r"\n?\s*\((?:[A-Za-z_]+Error|Exception|HTTPError|TimeoutError)[^)]*\)\s*$", "", text)
    return text.strip() or fallback


def sanitize_user_title(value: Any, fallback: str = "안내") -> str:
    """Return a short Korean title without internal codes or exception names."""
    text = _stringify(value)
    if not text or _looks_question_mark_mojibake(text):
        return fallback

    mapped = _SAFE_TITLE_MAP.get(text.lower())
    if mapped:
        return mapped

    text = _INTERNAL_CODE.sub("", text).strip(" []/:-")
    if not text:
        return fallback
    if looks_developer_facing(text):
        category = classify_error(text)
        if category != "unknown":
            return friendly_error_title(text, fallback=fallback)
        return fallback
    return text


def friendly_status(value: Any, fallback_title: str = "확인이 필요해요") -> tuple[str, str]:
    return friendly_error_title(value, fallback=fallback_title), friendly_error_message(value)
