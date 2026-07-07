#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Headless smoke test for setup-assistant clipboard autofill.

Verifies that waiting-user steps can be advanced by clipboard text only:
- TikTok callback URL(code)
- Instagram profile URL
- Threads profile URL
- Linktree public profile URL
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from managers.settings_manager import get_settings_manager  # noqa: E402
from ui.panels.settings_tab import SettingsTab  # noqa: E402


class _DummyTikTokChannel:
    def __init__(self):
        self.username = "demo_tiktok"
        self.display_name = "Demo TikTok"


class _DummyTikTokManager:
    def __init__(self):
        self._connected = False
        self._channel = _DummyTikTokChannel()

    def get_auth_url(self, state: str = "") -> str:
        return "https://www.tiktok.com/v2/auth/authorize/?client_key=dummy&state=" + (state or "default")

    def exchange_code_for_token(self, authorization_code: str) -> bool:
        if not authorization_code:
            return False
        self._connected = True
        return True

    def is_connected(self) -> bool:
        return self._connected

    def get_channel_info(self):
        return self._channel


class _DummyInstagramManager:
    """Mimics official-API InstagramManager connection state for headless tests."""

    def __init__(self):
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def mark_connected(self):
        self._connected = True

    def reset(self):
        self._connected = False


class _DummyGUI:
    def __init__(self):
        self.output_folder_path = ""
        self.tiktok_manager = _DummyTikTokManager()
        self.instagram_manager = _DummyInstagramManager()


def _run_until_waiting_or_done(tab: SettingsTab, app: QApplication, max_ticks: int = 300) -> None:
    for _ in range(max_ticks):
        QTest.qWait(15)
        app.processEvents()
        if tab._setup_waiting_user or not tab._setup_running:  # noqa: SLF001
            return


def _run_until_done(tab: SettingsTab, app: QApplication, max_ticks: int = 700) -> None:
    for _ in range(max_ticks):
        QTest.qWait(15)
        app.processEvents()
        if not tab._setup_running:  # noqa: SLF001
            return


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])
    settings = get_settings_manager()
    backup: Dict[str, Any] = {
        "tiktok_connected": settings.get_social_connection_status("tiktok"),
        "tiktok_name": settings.get_social_account_name("tiktok"),
        "instagram_connected": settings.get_social_connection_status("instagram"),
        "instagram_name": settings.get_social_account_name("instagram"),
        "threads_connected": settings.get_social_connection_status("threads"),
        "threads_name": settings.get_social_account_name("threads"),
        "linktree": settings.get_linktree_settings(),
    }
    settings.set_social_connection_status("tiktok", False)
    settings.set_social_connection_status("instagram", False)
    settings.set_social_connection_status("threads", False)
    settings.set_linktree_settings(
        webhook_url="",
        api_key="",
        profile_url="",
        auto_publish=False,
    )

    gui = _DummyGUI()

    # Instagram now connects through the official Graph API manager (OAuth),
    # so route _is_instagram_connected() to the dummy manager.
    import managers.instagram_manager as _ig_module
    gui_instagram_manager = gui.instagram_manager
    _ig_module.get_instagram_manager = lambda gui=None: gui_instagram_manager  # type: ignore[assignment]

    try:
        tab = SettingsTab(gui=gui)
        tab._get_saved_gemini_key_count = lambda: 1  # type: ignore[method-assign]
        # Instagram no longer connects via clipboard; complete OAuth on action.
        tab._assistant_open_instagram_connect = lambda: gui_instagram_manager.mark_connected()  # type: ignore[method-assign]

        # 1) TikTok clipboard autofill
        tab._start_setup_assistant("tiktok")
        _run_until_waiting_or_done(tab, app)
        QApplication.clipboard().setText("https://localhost/callback?code=tiktok_code_123456&state=abc")
        _run_until_done(tab, app)
        if tab._setup_running:  # noqa: SLF001
            print("ERROR: tiktok scope did not finish")
            return 1
        if not tab._is_tiktok_connected():
            print("ERROR: tiktok not connected via clipboard autofill")
            return 2

        # 2) Instagram — official API (OAuth), not clipboard. Drive via action/done.
        tab._start_setup_assistant("instagram")
        for _ in range(700):
            QTest.qWait(15)
            app.processEvents()
            if tab._setup_waiting_user:  # noqa: SLF001
                tab._on_setup_action_clicked()  # simulates completing OAuth
                app.processEvents()
                tab._on_setup_done_clicked()
                app.processEvents()
            if not tab._setup_running:  # noqa: SLF001
                break
        if tab._setup_running:  # noqa: SLF001
            print("ERROR: instagram scope did not finish")
            return 3
        if not tab._is_instagram_connected():
            print("ERROR: instagram not connected via official API flow")
            return 4

        # 3) Threads clipboard autofill
        tab._start_setup_assistant("threads")
        _run_until_waiting_or_done(tab, app)
        QApplication.clipboard().setText("https://www.threads.net/@demo_threads")
        _run_until_done(tab, app)
        if tab._setup_running:  # noqa: SLF001
            print("ERROR: threads scope did not finish")
            return 5
        if not tab._is_threads_connected():
            print("ERROR: threads not connected via clipboard autofill")
            return 6

        # 4) Linktree clipboard autofill
        tab._start_setup_assistant("linktree")
        _run_until_waiting_or_done(tab, app)
        QApplication.clipboard().setText("https://linktr.ee/demo_store_clipboard")
        _run_until_done(tab, app)
        if tab._setup_running:  # noqa: SLF001
            print("ERROR: linktree scope did not finish")
            return 7
        if not tab._is_linktree_profile_ready():
            print("ERROR: linktree profile not ready via clipboard autofill")
            return 8

        print("OK: setup assistant clipboard autofill flow")
        return 0
    finally:
        settings.set_social_connection_status(
            "tiktok",
            bool(backup["tiktok_connected"]),
            str(backup["tiktok_name"] if backup["tiktok_connected"] else ""),
        )
        settings.set_social_connection_status(
            "instagram",
            bool(backup["instagram_connected"]),
            str(backup["instagram_name"] if backup["instagram_connected"] else ""),
        )
        settings.set_social_connection_status(
            "threads",
            bool(backup["threads_connected"]),
            str(backup["threads_name"] if backup["threads_connected"] else ""),
        )
        linktree_backup = backup["linktree"] or {}
        settings.set_linktree_settings(
            webhook_url=str(linktree_backup.get("webhook_url", "")),
            api_key=str(linktree_backup.get("api_key", "")),
            profile_url=str(linktree_backup.get("profile_url", "")),
            auto_publish=bool(linktree_backup.get("auto_publish", False)),
        )


if __name__ == "__main__":
    raise SystemExit(main())

