"""Writable per-user path helpers for installed desktop applications."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Iterable, Optional


def _windows_desktop_from_registry() -> Optional[Path]:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _value_type = winreg.QueryValueEx(key, "Desktop")
        expanded = os.path.expandvars(str(value or "").strip())
        return Path(expanded).expanduser() if expanded else None
    except (FileNotFoundError, OSError):
        return None


def desktop_directory() -> Optional[Path]:
    """Return the user's real desktop, including OneDrive redirection."""
    candidates: Iterable[Optional[Path]] = (
        _windows_desktop_from_registry(),
        Path.home() / "Desktop",
    )
    for candidate in candidates:
        if candidate and candidate.is_dir():
            return candidate
    return None


def default_output_directory() -> Path:
    """Return and create a writable default directory for generated videos."""
    candidates = (
        desktop_directory(),
        Path.home() / "Videos" / "SSMaker",
        Path.home() / "SSMaker" / "outputs",
    )
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            # Use a unique probe so a user's existing file can never be
            # overwritten or removed while checking directory writability.
            probe = candidate / f".ssmaker_write_test_{uuid.uuid4().hex}"
            try:
                probe.write_text("ok", encoding="utf-8")
            finally:
                probe.unlink(missing_ok=True)
            return candidate
        except (OSError, PermissionError):
            continue
    raise OSError("No writable user output directory is available")
