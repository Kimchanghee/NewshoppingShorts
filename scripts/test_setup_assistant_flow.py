#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Headless smoke test for SettingsTab setup assistant flow.

This does not perform real Google/Linktree login. Instead it simulates
"user-required" checkpoints and verifies the step engine transitions finish.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Any

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from managers.settings_manager import get_settings_manager  # noqa: E402
from ui.panels.settings_tab import SettingsTab  # noqa: E402


class _DummyYouTubeManager:
    def __init__(self):
        self._connected = False
        self._channel_info: Dict[str, Any] = {}

    def is_connected(self) -> bool:
        return self._connected

    def get_channel_info(self) -> Dict[str, Any]:
        return dict(self._channel_info)

    def mark_connected(self, channel_id: str = "demo_channel_id", channel_name: str = "Demo Channel"):
        self._connected = True
        self._channel_info = {"id": channel_id, "title": channel_name}


class _DummyUploadPanel:
    def __init__(self, yt_manager: _DummyYouTubeManager):
        self._yt = yt_manager

    def _show_youtube_json_connect(self):
        self._yt.mark_connected()
        settings = get_settings_manager()
        settings.set_youtube_connected(True, "demo_channel_id", "Demo Channel")


class _DummyGUI:
    def __init__(self):
        self.output_folder_path = ""
        self.youtube_manager = _DummyYouTubeManager()
        self.tiktok_manager = _DummyTikTokManager()
        self.upload_panel = _DummyUploadPanel(self.youtube_manager)


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


def main() -> int:
    # Keep this script safe for non-GUI environments.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication([])
    settings = get_settings_manager()
    backup = {
        "youtube_connected": settings.get_youtube_connected(),
        "youtube_info": settings.get_youtube_channel_info(),
        "tiktok_connected": settings.get_social_connection_status("tiktok"),
        "tiktok_name": settings.get_social_account_name("tiktok"),
        "instagram_connected": settings.get_social_connection_status("instagram"),
        "instagram_name": settings.get_social_account_name("instagram"),
        "threads_connected": settings.get_social_connection_status("threads"),
        "threads_name": settings.get_social_account_name("threads"),
    }
    gui = _DummyGUI()
    tab = SettingsTab(gui=gui)

    # Avoid dependency on real secret storage contents.
    tab._get_saved_gemini_key_count = lambda: 1  # type: ignore[method-assign]

    # Simulate linktree user action by pre-filling profile URL when action is invoked.
    def _fake_linktree_action():
        tab.linktree_profile_input.setText("https://linktr.ee/demo_store")

    tab._assistant_open_linktree_admin = _fake_linktree_action  # type: ignore[method-assign]
    tab._assistant_open_tiktok_auth = lambda: tab.setup_tiktok_code_input.setText("demo_tiktok_oauth_code")  # type: ignore[method-assign]
    tab._assistant_open_instagram_setup = lambda: tab.setup_instagram_handle_input.setText("demo_instagram")  # type: ignore[method-assign]
    tab._assistant_open_threads_setup = lambda: tab.setup_threads_handle_input.setText("demo_threads")  # type: ignore[method-assign]

    try:
        tab._start_setup_assistant("social4")

        max_ticks = 800
        for _ in range(max_ticks):
            QTest.qWait(15)
            app.processEvents()
            if tab._setup_waiting_user:  # noqa: SLF001
                tab._on_setup_action_clicked()
                app.processEvents()
                tab._on_setup_done_clicked()
                app.processEvents()
            if not tab._setup_running:  # noqa: SLF001
                break

        app.processEvents()
        print("setup_running:", tab._setup_running)  # noqa: SLF001
        print("waiting_user:", tab._setup_waiting_user)  # noqa: SLF001
        print("youtube_connected:", tab._is_youtube_connected())
        print("tiktok_connected:", tab._is_tiktok_connected())
        print("instagram_connected:", tab._is_instagram_connected())
        print("threads_connected:", tab._is_threads_connected())
        print("linktree_profile_ready:", tab._is_linktree_profile_ready())

        if tab._setup_running:  # noqa: SLF001
            print("ERROR: setup assistant did not finish in time")
            return 1
        if not tab._is_youtube_connected():
            print("ERROR: youtube not connected after flow")
            return 2
        if not tab._is_tiktok_connected():
            print("ERROR: tiktok not connected after flow")
            return 3
        if not tab._is_instagram_connected():
            print("ERROR: instagram not connected after flow")
            return 4
        if not tab._is_threads_connected():
            print("ERROR: threads not connected after flow")
            return 5

        print("OK: setup assistant flow completed")
        return 0
    finally:
        settings.set_youtube_connected(
            backup["youtube_connected"],
            str(backup["youtube_info"].get("channel_id", "")),
            str(backup["youtube_info"].get("channel_name", "")),
        )
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


if __name__ == "__main__":
    raise SystemExit(main())
