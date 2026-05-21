#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Headless smoke test for setup-assistant Codex CLI bridge helpers.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

from PyQt6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from managers.settings_manager import get_settings_manager  # noqa: E402
from ui.panels.settings_tab import SettingsTab  # noqa: E402


class _DummyGUI:
    def __init__(self):
        self.output_folder_path = ""


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])
    settings = get_settings_manager()
    backup: Dict[str, Any] = settings.get_codex_cli_settings()
    backup_cu: Dict[str, Any] = settings.get_computer_use_settings()

    try:
        if not settings.set_codex_cli_settings(path="codex", model="gpt-5.4", enabled=True):
            print("ERROR: failed to save codex cli settings")
            return 1

        loaded = settings.get_codex_cli_settings()
        if loaded.get("path") != "codex":
            print("ERROR: codex path mismatch")
            return 2
        if loaded.get("model") != "gpt-5.4":
            print("ERROR: codex model mismatch")
            return 3

        if not settings.set_computer_use_settings(
            paid_only=True,
            bridge_enabled=True,
            bridge_url="https://bridge.example.com",
            bridge_api_key="demo-bridge-key",
        ):
            print("ERROR: failed to save computer use settings")
            return 4

        cu_loaded = settings.get_computer_use_settings()
        if cu_loaded.get("bridge_url") != "https://bridge.example.com":
            print("ERROR: computer use bridge url mismatch")
            return 5
        if not cu_loaded.get("bridge_enabled"):
            print("ERROR: computer use bridge enabled mismatch")
            return 6

        tab = SettingsTab(gui=_DummyGUI())
        tab._setup_running = True  # noqa: SLF001
        tab._setup_scope = "tiktok"  # noqa: SLF001
        tab._setup_steps = ["tiktok_user_auth"]  # noqa: SLF001
        tab._setup_step_index = 0  # noqa: SLF001
        prompt = tab._build_codex_prompt_for_current_step()

        if "TikTok OAuth 연결" not in prompt:
            print("ERROR: codex prompt focus missing")
            return 7
        if "login, 2FA, CAPTCHA" not in prompt:
            print("ERROR: codex prompt human boundary missing")
            return 8

        enabled_sample = (
            "Name          Command\n"
            "computer-use  /tmp/SkyComputerUseClient mcp enabled\n"
        )
        disabled_sample = (
            "Name          Command\n"
            "computer-use  /tmp/SkyComputerUseClient mcp disabled\n"
        )
        if not SettingsTab._has_enabled_computer_use_mcp(enabled_sample):
            print("ERROR: enabled mcp parsing failed")
            return 9
        if SettingsTab._has_enabled_computer_use_mcp(disabled_sample):
            print("ERROR: disabled mcp parsing failed")
            return 10

        # paid_only=True + no login user => launch/check controls must be disabled
        tab._refresh_computer_use_access_ui()
        if tab.setup_codex_launch_btn.isEnabled():
            print("ERROR: codex launch button should be disabled for non-paid/no-login")
            return 11

        print("OK: setup assistant codex bridge helpers")
        return 0
    finally:
        settings.set_codex_cli_settings(
            path=str(backup.get("path", "codex") or "codex"),
            model=str(backup.get("model", "") or ""),
            enabled=bool(backup.get("enabled", True)),
        )
        settings.set_computer_use_settings(
            paid_only=bool(backup_cu.get("paid_only", True)),
            bridge_enabled=bool(backup_cu.get("bridge_enabled", False)),
            bridge_url=str(backup_cu.get("bridge_url", "") or ""),
            bridge_api_key=str(backup_cu.get("bridge_api_key", "") or ""),
        )
        app.quit()


if __name__ == "__main__":
    raise SystemExit(main())
