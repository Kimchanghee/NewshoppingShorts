#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Headless E2E matrix test for setup assistant platform scopes.

Scopes covered:
- youtube
- tiktok
- instagram
- threads
- linktree
- social4
- all
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

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
        self.youtube_manager = _DummyYouTubeManager()
        self.tiktok_manager = _DummyTikTokManager()
        self.instagram_manager = _DummyInstagramManager()
        self.upload_panel = _DummyUploadPanel(self.youtube_manager)


def _reset_connection_settings(tab: SettingsTab = None) -> None:
    settings = get_settings_manager()
    settings.set_youtube_connected(False, "", "")
    settings.set_social_connection_status("tiktok", False, "")
    settings.set_social_connection_status("instagram", False, "")
    settings.set_social_connection_status("threads", False, "")
    settings.set_linktree_settings(webhook_url="", api_key="", profile_url="", auto_publish=False)
    ig_manager = getattr(getattr(tab, "gui", None), "instagram_manager", None)
    if ig_manager is not None and hasattr(ig_manager, "reset"):
        ig_manager.reset()


def _run_scope(tab: SettingsTab, app: QApplication, scope: str) -> bool:
    _reset_connection_settings(tab)
    tab.setup_tiktok_code_input.clear()
    tab.setup_instagram_handle_input.clear()
    tab.setup_threads_handle_input.clear()
    tab.linktree_profile_input.clear()

    tab._start_setup_assistant(scope)

    max_ticks = 900
    for _ in range(max_ticks):
        QTest.qWait(15)
        app.processEvents()
        if tab._setup_waiting_user:  # noqa: SLF001
            tab._on_setup_action_clicked()
            app.processEvents()
            tab._on_setup_done_clicked()
            app.processEvents()
        if not tab._setup_running:  # noqa: SLF001
            return True
    return False


def _assert_scope_result(tab: SettingsTab, scope: str) -> List[str]:
    errors: List[str] = []
    if scope in {"youtube", "social4", "all"} and not tab._is_youtube_connected():
        errors.append("youtube not connected")
    if scope in {"tiktok", "social4", "all"} and not tab._is_tiktok_connected():
        errors.append("tiktok not connected")
    if scope in {"instagram", "social4", "all"} and not tab._is_instagram_connected():
        errors.append("instagram not connected")
    if scope in {"threads", "social4", "all"} and not tab._is_threads_connected():
        errors.append("threads not connected")
    if scope in {"linktree", "all"} and not tab._is_linktree_profile_ready():
        errors.append("linktree profile not ready")
    return errors


def main() -> int:
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
        "linktree": settings.get_linktree_settings(),
    }

    gui = _DummyGUI()

    # Instagram now connects through the official Graph API manager.
    import managers.instagram_manager as _ig_module
    gui_instagram_manager = gui.instagram_manager
    _ig_module.get_instagram_manager = lambda gui=None: gui_instagram_manager  # type: ignore[assignment]

    tab = SettingsTab(gui=gui)
    tab._get_saved_gemini_key_count = lambda: 1  # type: ignore[method-assign]

    # Deterministic user-step helpers for E2E flow.
    tab._assistant_open_tiktok_auth = lambda: tab.setup_tiktok_code_input.setText("demo_tiktok_oauth_code")  # type: ignore[method-assign]
    # Instagram: simulate completing the official Facebook Login OAuth on action.
    tab._assistant_open_instagram_connect = lambda: gui_instagram_manager.mark_connected()  # type: ignore[method-assign]
    tab._assistant_open_threads_setup = lambda: tab.setup_threads_handle_input.setText("demo_threads")  # type: ignore[method-assign]
    tab._assistant_open_linktree_admin = lambda: tab.linktree_profile_input.setText("https://linktr.ee/demo_store")  # type: ignore[method-assign]

    scopes = ["youtube", "tiktok", "instagram", "threads", "linktree", "social4", "all"]
    failures: List[str] = []

    try:
        for scope in scopes:
            finished = _run_scope(tab, app, scope)
            if not finished:
                failures.append(f"{scope}: flow timeout")
                continue
            errors = _assert_scope_result(tab, scope)
            if errors:
                failures.append(f"{scope}: {', '.join(errors)}")

        if failures:
            for row in failures:
                print("ERROR:", row)
            return 1

        print("OK: setup assistant e2e matrix passed")
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
        linktree_backup = backup["linktree"] or {}
        settings.set_linktree_settings(
            webhook_url=str(linktree_backup.get("webhook_url", "")),
            api_key=str(linktree_backup.get("api_key", "")),
            profile_url=str(linktree_backup.get("profile_url", "")),
            auto_publish=bool(linktree_backup.get("auto_publish", False)),
        )
        app.quit()


if __name__ == "__main__":
    raise SystemExit(main())

