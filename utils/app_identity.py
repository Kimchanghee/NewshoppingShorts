# -*- coding: utf-8 -*-
"""Application identity and installed release metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from utils.auto_updater import get_current_version, get_version_file_path


APP_DISPLAY_NAME = "쇼핑 쇼츠 헬퍼"


@dataclass(frozen=True)
class AppIdentity:
    """Display-ready application name and installed release metadata."""

    name: str
    version: str
    updated_at: str
    display_date: str
    accessible_date: str

    @property
    def display_metadata(self) -> str:
        return f"v{self.version} · 업데이트 {self.display_date}"

    @property
    def accessible_description(self) -> str:
        return (
            f"{self.name}, 현재 버전 {self.version}, "
            f"업데이트 날짜 {self.accessible_date}"
        )


def _format_update_date(raw_value: str) -> tuple[str, str]:
    """Return compact visual and screen-reader friendly release dates."""
    value = str(raw_value or "").strip()
    if not value:
        return "날짜 미확인", "확인할 수 없음"

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return value, value

    return (
        parsed.strftime("%Y.%m.%d"),
        f"{parsed.year}년 {parsed.month}월 {parsed.day}일",
    )


def load_app_identity() -> AppIdentity:
    """Load the installed version and update date in source and frozen builds."""
    version = str(get_current_version() or "0.0.0").strip()
    updated_at = ""

    try:
        version_path = get_version_file_path()
        if version_path and version_path.exists():
            with version_path.open("r", encoding="utf-8") as version_file:
                payload = json.load(version_file)
            version = str(payload.get("version") or version).strip()
            updated_at = str(
                payload.get("updated_at") or payload.get("build_date") or ""
            ).strip()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        # A readable version is still available from the updater fallback.
        pass

    display_date, accessible_date = _format_update_date(updated_at)
    return AppIdentity(
        name=APP_DISPLAY_NAME,
        version=version,
        updated_at=updated_at,
        display_date=display_date,
        accessible_date=accessible_date,
    )
