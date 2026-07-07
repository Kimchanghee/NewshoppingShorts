#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Headless smoke test for UploadPanel social connection state handling.

This verifies that TikTok/Instagram/Threads connection statuses can be
stored, reflected in UI cards, and refreshed without opening real dialogs.
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from managers.settings_manager import get_settings_manager  # noqa: E402
from ui.panels.upload_panel import UploadPanel  # noqa: E402


class _DummyState:
    def __init__(self):
        self.youtube_connected = False
        self.youtube_channel_info = None
        self.youtube_auto_upload = False
        self.tiktok_connected = False
        self.instagram_connected = False
        self.threads_connected = False


class _DummyChannel:
    def __init__(self):
        self.display_name = "Dummy TikTok"
        self.username = "dummy_tiktok"


class _DummyTikTokManager:
    def __init__(self):
        self._connected = False
        self._channel = _DummyChannel()

    def get_auth_url(self, state: str = "") -> str:
        return "https://www.tiktok.com/v2/auth/authorize/?client_key=dummy"

    def exchange_code_for_token(self, authorization_code: str) -> bool:
        if not authorization_code:
            return False
        self._connected = True
        return True

    def get_channel_info(self):
        return self._channel

    def disconnect_channel(self):
        self._connected = False


class _DummyYouTubeManager:
    pass


class _DummyGUI:
    def __init__(self):
        self.state = _DummyState()
        self.youtube_manager = _DummyYouTubeManager()
        self.tiktok_manager = _DummyTikTokManager()

    def _on_step_selected(self, step_id: str):
        _ = step_id


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])

    settings = get_settings_manager()
    backup = {
        "tiktok_connected": settings.get_social_connection_status("tiktok"),
        "tiktok_name": settings.get_social_account_name("tiktok"),
        "instagram_connected": settings.get_social_connection_status("instagram"),
        "instagram_name": settings.get_social_account_name("instagram"),
        "threads_connected": settings.get_social_connection_status("threads"),
        "threads_name": settings.get_social_account_name("threads"),
    }
    settings.set_social_connection_status("tiktok", False)
    settings.set_social_connection_status("instagram", False)
    settings.set_social_connection_status("threads", False)

    try:
        gui = _DummyGUI()
        panel = UploadPanel(gui=gui)

        # Helpers parse expected values.
        if panel._extract_oauth_code("https://localhost/callback?code=abc123&state=x") != "abc123":
            print("ERROR: OAuth code extraction failed")
            return 1
        if panel._normalize_social_account("https://www.instagram.com/demo_store/") != "demo_store":
            print("ERROR: social account normalization failed")
            return 2

        ok_tiktok, tiktok_result = panel._perform_tiktok_code_exchange("https://localhost/callback?code=dummy_code_123")
        if not ok_tiktok:
            print("ERROR: tiktok code exchange helper failed:", tiktok_result)
            return 3
        ok_instagram, instagram_result = panel._perform_manual_social_connect("instagram", "https://instagram.com/demo_store")
        if not ok_instagram:
            print("ERROR: instagram manual connect helper failed:", instagram_result)
            return 4
        ok_threads, threads_result = panel._perform_manual_social_connect("threads", "@demo_threads")
        if not ok_threads:
            print("ERROR: threads manual connect helper failed:", threads_result)
            return 5
        panel.refresh()
        app.processEvents()

        if not settings.get_social_connection_status("tiktok"):
            print("ERROR: tiktok status not saved")
            return 6
        if not settings.get_social_connection_status("instagram"):
            print("ERROR: instagram status not saved")
            return 7
        if not settings.get_social_connection_status("threads"):
            print("ERROR: threads status not saved")
            return 8

        if panel._get_channel_status_text("tiktok") != "연결됨":
            print("ERROR: tiktok tab status mismatch")
            return 9
        if panel._get_channel_status_text("instagram") != "연결됨":
            print("ERROR: instagram tab status mismatch")
            return 10
        if panel._get_channel_status_text("threads") != "지원예정":
            print("ERROR: threads tab status mismatch")
            return 11

        # Reset to disconnected and ensure refresh reflects it.
        settings.set_social_connection_status("tiktok", False)
        settings.set_social_connection_status("instagram", False)
        settings.set_social_connection_status("threads", False)
        panel.refresh()
        app.processEvents()

        if panel._get_channel_status_text("tiktok") != "연결 필요":
            print("ERROR: tiktok disconnected status mismatch")
            return 12
        if panel._get_channel_status_text("instagram") != "연결 필요":
            print("ERROR: instagram disconnected status mismatch")
            return 13
        if panel._get_channel_status_text("threads") != "지원예정":
            print("ERROR: threads disconnected status mismatch")
            return 14

        print("OK: upload panel social connection flow")
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


if __name__ == "__main__":
    raise SystemExit(main())
