"""Tests for 1-link policy enforcement during session restore."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from managers.session_manager import SessionManager


class DummyGUI:
    def __init__(self):
        self.url_queue = []
        self.url_status = {}
        self.url_status_message = {}
        self.url_remarks = {}
        self.url_timestamps = {}
        self.mix_jobs = {}
        self.current_processing_index = -1
        self.processing_mode = "single"
        self.batch_processing = False
        self.dynamic_processing = False
        self.voice_vars = {}
        self.url_input_panel = SimpleNamespace(refresh_mode=lambda: None)
        self.queue_manager = SimpleNamespace(
            _ensure_mix_store=lambda: self.mix_jobs,
            update_url_listbox=lambda: None,
        )
        self.state = SimpleNamespace(
            processing_mode="single",
            mix_jobs=self.mix_jobs,
        )
        self.generated_videos = []
        self.multi_voice_presets = []
        self.available_tts_voices = []

    def update_url_listbox(self):
        pass

    def update_voice_card_styles(self):
        pass

    def update_voice_summary(self):
        pass

    def refresh_output_folder_display(self):
        pass

    def add_log(self, msg):
        pass


def _make_session_data(url_queue, url_status):
    return {
        "saved_at": "2026-04-07 12:00:00",
        "url_queue": url_queue,
        "url_status": url_status,
        "url_status_message": {},
        "url_remarks": {},
        "current_processing_index": -1,
        "processing_mode": "single",
        "mix_jobs": {},
        "selected_voices": [],
        "url_timestamps": {},
        "stats": {},
    }


def test_restore_enforces_single_active_item():
    """Session restore should keep only the first waiting URL, skip the rest."""
    gui = DummyGUI()
    mgr = SessionManager(gui)

    session = _make_session_data(
        url_queue=["https://a.com", "https://b.com", "https://c.com"],
        url_status={
            "https://a.com": "waiting",
            "https://b.com": "waiting",
            "https://c.com": "waiting",
        },
    )

    with patch("managers.session_manager.logger"):
        result = mgr.restore_session(session)

    assert result is True
    assert gui.url_status["https://a.com"] == "waiting"
    assert gui.url_status["https://b.com"] == "skipped"
    assert gui.url_status["https://c.com"] == "skipped"


def test_restore_preserves_completed_and_failed():
    """Completed/failed URLs should not be affected by 1-link policy."""
    gui = DummyGUI()
    mgr = SessionManager(gui)

    session = _make_session_data(
        url_queue=["https://done.com", "https://fail.com", "https://wait.com"],
        url_status={
            "https://done.com": "completed",
            "https://fail.com": "failed",
            "https://wait.com": "waiting",
        },
    )

    with patch("managers.session_manager.logger"):
        result = mgr.restore_session(session)

    assert result is True
    assert gui.url_status["https://done.com"] == "completed"
    assert gui.url_status["https://fail.com"] == "failed"
    assert gui.url_status["https://wait.com"] == "waiting"


def test_restore_single_waiting_no_demotion():
    """A single waiting URL should remain untouched."""
    gui = DummyGUI()
    mgr = SessionManager(gui)

    session = _make_session_data(
        url_queue=["https://only.com"],
        url_status={"https://only.com": "waiting"},
    )

    with patch("managers.session_manager.logger"):
        result = mgr.restore_session(session)

    assert result is True
    assert gui.url_status["https://only.com"] == "waiting"
