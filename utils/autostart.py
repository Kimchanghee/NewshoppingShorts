"""Windows login autostart support for SSMaker."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "SSMaker"


def is_supported_platform() -> bool:
    """Return True when HKCU Run autostart can be configured."""
    return os.name == "nt"


def _pythonw_for_current_interpreter() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(executable)


def build_startup_command() -> str:
    """Build the command stored in HKCU Run for the current app build."""
    if getattr(sys, "frozen", False):
        argv = [sys.executable]
    else:
        project_root = Path(__file__).resolve().parents[1]
        argv = [_pythonw_for_current_interpreter(), str(project_root / "ssmaker.py")]
    return subprocess.list2cmdline(argv)


def set_launch_on_startup(enabled: bool, command: Optional[str] = None) -> bool:
    """Enable or disable launch-on-login in the current user's Run registry key."""
    if not is_supported_platform():
        logger.info("[Autostart] Startup registration skipped on unsupported platform")
        return False

    try:
        import winreg

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key,
                    RUN_VALUE_NAME,
                    0,
                    winreg.REG_SZ,
                    command or build_startup_command(),
                )
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
                except FileNotFoundError:
                    pass
        logger.info("[Autostart] Startup registration %s", "enabled" if enabled else "disabled")
        return True
    except Exception as exc:
        logger.warning("[Autostart] Failed to update startup registration: %s", exc)
        return False


def get_registered_command() -> str:
    """Return the registered Run command, or an empty string when absent."""
    if not is_supported_platform():
        return ""

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_READ,
        ) as key:
            value, _value_type = winreg.QueryValueEx(key, RUN_VALUE_NAME)
        return str(value or "")
    except FileNotFoundError:
        return ""
    except Exception as exc:
        logger.debug("[Autostart] Failed to read startup registration: %s", exc)
        return ""


def is_launch_on_startup_registered() -> bool:
    """Return True when SSMaker has a Run entry for the current user."""
    return bool(get_registered_command().strip())


def sync_launch_on_startup(enabled: bool) -> bool:
    """Best-effort sync from saved user preference to the OS startup entry."""
    return set_launch_on_startup(bool(enabled))
