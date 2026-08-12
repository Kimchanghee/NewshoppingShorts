# -*- coding: utf-8 -*-
"""Privacy-safe, structured diagnostics for application startup.

The startup log is deliberately separate from the general application log.  It
is append-only JSONL so a broken launch still leaves a machine-readable record,
while credential-like values are removed before anything is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import threading
import traceback as traceback_module
from typing import Any, Mapping, Optional
from uuid import uuid4


_RUN_ID = uuid4().hex
_WRITE_LOCK = threading.Lock()
_SCHEMA_VERSION = 1
_REDACTED = "<redacted>"

_SENSITIVE_NAME = (
    r"api[_-]?key|token|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"secret|client[_-]?secret|password|passwd|pwd|authorization|cookie|"
    r"private[_-]?key|credential"
)
_SENSITIVE_ENV_MARKERS = (
    "API_KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "CREDENTIAL",
    "AUTHORIZATION",
    "COOKIE",
)


@dataclass(frozen=True)
class StartupIssue:
    """Safe issue metadata that may cross the diagnostics/UI boundary."""

    code: str
    component: str
    phase: str
    run_id: str
    recoverable: bool = True
    offline_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a signal-safe representation with no exception details."""
        return {
            "code": self.code,
            "component": self.component,
            "phase": self.phase,
            "run_id": self.run_id,
            "recoverable": self.recoverable,
            "offline_allowed": self.offline_allowed,
        }

    def user_message(self) -> str:
        """Return actionable text without including internal exception data."""
        return startup_issue_user_message(self)


def get_startup_log_path() -> Path:
    """Return the per-user startup JSONL path."""
    return Path(os.path.expanduser("~")) / ".ssmaker" / "logs" / "startup.jsonl"


def get_startup_run_id() -> str:
    """Return the identifier shared by startup events in this process."""
    return _RUN_ID


def classify_startup_exception(
    phase: str,
    component: str,
    exc: BaseException,
) -> str:
    """Classify an exception into a stable, non-sensitive support code."""
    del phase, component  # Reserved for future classifications without API churn.
    exc_name = type(exc).__name__.lower()
    exc_module = type(exc).__module__.lower()
    detail = f"{type(exc).__name__}: {exc}".lower()

    if isinstance(exc, (ModuleNotFoundError, ImportError)):
        return "startup_dependency_missing"
    if isinstance(exc, PermissionError):
        return "startup_permission_denied"
    if isinstance(exc, FileNotFoundError):
        return "startup_file_missing"
    if isinstance(exc, TimeoutError) or "timeout" in exc_name:
        return "startup_network_timeout"
    if isinstance(exc, ConnectionError):
        return "startup_network_unavailable"
    if (
        "requests" in exc_module
        and ("connection" in exc_name or "proxy" in exc_name or "ssl" in exc_name)
    ):
        return "startup_network_unavailable"
    if isinstance(exc, OSError) and (
        getattr(exc, "winerror", None) in {126, 127, 193}
        or "dll load failed" in detail
        or "dynamic link library" in detail
    ):
        return "startup_native_dependency"
    if isinstance(exc, (KeyError, ValueError, TypeError)):
        return "startup_configuration_invalid"
    return "startup_unexpected_error"


def startup_issue_user_message(issue: StartupIssue | Mapping[str, Any] | str) -> str:
    """Build a user-safe recovery message from an issue or stable code."""
    if isinstance(issue, StartupIssue):
        code = issue.code
        recoverable = issue.recoverable
        offline_allowed = issue.offline_allowed
    elif isinstance(issue, Mapping):
        code = str(issue.get("code", "startup_unexpected_error"))
        recoverable = bool(issue.get("recoverable", True))
        offline_allowed = bool(issue.get("offline_allowed", False))
    else:
        code = str(issue or "startup_unexpected_error")
        recoverable = True
        offline_allowed = False

    messages = {
        "startup_dependency_missing": (
            "필수 프로그램 구성 요소를 불러오지 못했습니다. "
            "최신 설치 파일로 다시 설치한 뒤 재시도해 주세요."
        ),
        "startup_native_dependency": (
            "Windows 실행 구성 요소를 불러오지 못했습니다. "
            "프로그램을 다시 설치한 뒤 재시도해 주세요."
        ),
        "startup_permission_denied": (
            "프로그램이 필요한 파일에 접근할 수 없습니다. "
            "보안 프로그램의 차단 여부와 폴더 권한을 확인해 주세요."
        ),
        "startup_file_missing": (
            "프로그램 실행에 필요한 파일을 찾을 수 없습니다. "
            "최신 설치 파일로 다시 설치해 주세요."
        ),
        "startup_network_timeout": (
            "서버 연결 시간이 초과되었습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요."
        ),
        "startup_network_unavailable": (
            "서버에 연결할 수 없습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요."
        ),
        "startup_configuration_invalid": (
            "프로그램 설정을 읽는 중 문제가 발생했습니다. 프로그램을 다시 시작해 주세요."
        ),
        "startup_unexpected_error": (
            "프로그램을 시작하는 중 문제가 발생했습니다. 프로그램을 다시 시작해 주세요."
        ),
    }
    message = messages.get(code, messages["startup_unexpected_error"])
    if offline_allowed and code in {"startup_network_timeout", "startup_network_unavailable"}:
        message += " 오프라인으로 계속 사용할 수 있는 기능은 그대로 이용할 수 있습니다."
    elif not recoverable:
        message += " 문제가 계속되면 시작 진단 로그와 함께 고객 지원에 문의해 주세요."
    return message


def redact_sensitive_text(value: object) -> str:
    """Remove credential values and user-home details from diagnostic text."""
    text = str(value or "")
    if not text:
        return ""

    # Redact concrete credential values already present in this process.  This
    # catches messages that omit the variable name entirely.
    for name, secret in os.environ.items():
        upper_name = name.upper()
        if not any(marker in upper_name for marker in _SENSITIVE_ENV_MARKERS):
            continue
        if secret and len(secret) >= 4:
            text = text.replace(secret, _REDACTED)

    home = os.path.expanduser("~")
    if home and home not in {"~", "/"}:
        text = re.sub(re.escape(home), "<home>", text, flags=re.IGNORECASE)

    # Auth headers must be handled before the generic assignment pattern so
    # both the scheme and its following credential are consumed.
    text = re.sub(
        r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s,;]+",
        rf"\1{_REDACTED}",
        text,
    )

    # JSON/Python mappings and ordinary KEY=value forms.
    text = re.sub(
        rf"(?i)([\"'](?:{_SENSITIVE_NAME})[\"']\s*:\s*[\"'])(.*?)([\"'])",
        rf"\1{_REDACTED}\3",
        text,
    )
    text = re.sub(
        rf"(?i)(\b(?:{_SENSITIVE_NAME})\b\s*[:=]\s*[\"'])(.*?)([\"'])",
        rf"\1{_REDACTED}\3",
        text,
    )
    text = re.sub(
        rf"(?i)(\b(?:{_SENSITIVE_NAME})\b\s*[:=]\s*)([^\s,;}}\]]+)",
        rf"\1{_REDACTED}",
        text,
    )
    # URL query parameters, command-line options, auth headers and URL userinfo.
    text = re.sub(
        rf"(?i)([?&](?:{_SENSITIVE_NAME})=)[^&#\s]+",
        rf"\1{_REDACTED}",
        text,
    )
    text = re.sub(
        rf"(?i)((?:--?)(?:{_SENSITIVE_NAME})(?:=|\s+))([^\s]+)",
        rf"\1{_REDACTED}",
        text,
    )
    text = re.sub(r"(?i)(https?://[^\s/@:]+:)[^\s/@]+(@)", rf"\1{_REDACTED}\2", text)

    # Common standalone credential formats.
    text = re.sub(r"\bAIza[0-9A-Za-z_-]{20,}\b", _REDACTED, text)
    text = re.sub(
        r"(?<![0-9A-Za-z_.-])AQ\.[0-9A-Za-z_.-]{16,200}(?![0-9A-Za-z_.-])",
        _REDACTED,
        text,
    )
    text = re.sub(
        r"\b(?:sk-[0-9A-Za-z_-]{16,}|(?:pk|ghp|gho|github_pat)_[0-9A-Za-z_-]{16,})\b",
        _REDACTED,
        text,
    )
    text = re.sub(r"\bAKIA[0-9A-Z]{16}\b", _REDACTED, text)
    text = re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        _REDACTED,
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
        _REDACTED,
        text,
    )
    return text


def _load_app_version_build() -> tuple[str, str]:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "version.json")
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            candidates.append(Path(bundle_dir) / "version.json")
    candidates.append(Path(__file__).resolve().parent.parent / "version.json")

    for candidate in candidates:
        try:
            with candidate.open("r", encoding="utf-8") as version_file:
                payload = json.load(version_file)
            version = str(payload.get("version") or "0.0.0")
            build = str(payload.get("build_number") or payload.get("build") or "")
            return version, build
        except (OSError, ValueError, TypeError):
            continue
    return "0.0.0", ""


def _base_record(
    *,
    phase: str,
    component: str,
    code: str,
    recoverable: bool,
    offline_allowed: bool,
) -> dict[str, Any]:
    version, build = _load_app_version_build()
    return {
        "schema_version": _SCHEMA_VERSION,
        "run_id": _RUN_ID,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "app_version": version,
        "app_build": build,
        "frozen": bool(getattr(sys, "frozen", False)),
        "phase": str(phase or "startup"),
        "component": str(component or "unknown"),
        "code": str(code or "startup_unexpected_error"),
        "recoverable": bool(recoverable),
        "offline_allowed": bool(offline_allowed),
    }


def _append_record(record: Mapping[str, Any]) -> None:
    """Best-effort append; diagnostics must never become a startup failure."""
    try:
        path = get_startup_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(dict(record), ensure_ascii=False, separators=(",", ":"))
        with _WRITE_LOCK:
            with path.open("a", encoding="utf-8", newline="\n") as log_file:
                log_file.write(line + "\n")
    except (OSError, TypeError, ValueError):
        pass


def record_startup_event(
    phase: str,
    component: str,
    *,
    code: str = "startup_started",
) -> None:
    """Write a non-error startup lifecycle event."""
    record = _base_record(
        phase=phase,
        component=component,
        code=code,
        recoverable=True,
        offline_allowed=False,
    )
    record.update(
        {
            "event": "startup_event",
            "exception_type": "",
            "exception_message": "",
            "traceback": "",
        }
    )
    _append_record(record)


def record_startup_exception(
    phase: str,
    component: str,
    exc: BaseException,
    *,
    code: Optional[str] = None,
    recoverable: bool = True,
    offline_allowed: bool = False,
) -> StartupIssue:
    """Record a complete redacted traceback and return safe issue metadata."""
    stable_code = str(code or classify_startup_exception(phase, component, exc))
    issue = StartupIssue(
        code=stable_code,
        component=str(component or "unknown"),
        phase=str(phase or "startup"),
        run_id=_RUN_ID,
        recoverable=bool(recoverable),
        offline_allowed=bool(offline_allowed),
    )
    formatted_traceback = "".join(
        traceback_module.format_exception(type(exc), exc, exc.__traceback__)
    )
    record = _base_record(
        phase=issue.phase,
        component=issue.component,
        code=issue.code,
        recoverable=issue.recoverable,
        offline_allowed=issue.offline_allowed,
    )
    record.update(
        {
            "event": "startup_exception",
            "exception_type": type(exc).__name__,
            "exception_message": redact_sensitive_text(exc),
            "traceback": redact_sensitive_text(formatted_traceback),
        }
    )
    _append_record(record)
    return issue


__all__ = [
    "StartupIssue",
    "classify_startup_exception",
    "get_startup_log_path",
    "get_startup_run_id",
    "record_startup_event",
    "record_startup_exception",
    "redact_sensitive_text",
    "startup_issue_user_message",
]
