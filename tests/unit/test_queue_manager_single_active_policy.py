from types import SimpleNamespace

import pytest

from managers import queue_manager as queue_module
from managers.queue_manager import QueueManager


class DummyGUI:
    def __init__(self):
        self.url_queue = []
        self.url_status = {}
        self.url_status_message = {}
        self.url_timestamps = {}
        self.url_remarks = {}
        self.mix_jobs = {}
        self.url_auto_upload_status = {}
        self.state = SimpleNamespace(mix_jobs=self.mix_jobs)


def _build_manager(monkeypatch):
    events = {"warning": [], "info": []}
    monkeypatch.setattr(
        queue_module,
        "show_warning",
        lambda *args, **kwargs: events["warning"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        queue_module,
        "show_info",
        lambda *args, **kwargs: events["info"].append((args, kwargs)),
    )
    monkeypatch.setattr(queue_module, "show_question", lambda *args, **kwargs: True)

    gui = DummyGUI()
    manager = QueueManager(gui)
    return manager, gui, events


def test_add_url_to_queue_blocks_when_active_waiting_exists(monkeypatch):
    manager, gui, _ = _build_manager(monkeypatch)

    assert manager.add_url_to_queue("https://example.com/1") is True
    assert manager.add_url_to_queue("https://example.com/2") is False
    assert gui.url_queue == ["https://example.com/1"]


def test_add_url_to_queue_allows_new_item_after_completion(monkeypatch):
    manager, gui, _ = _build_manager(monkeypatch)

    first = "https://example.com/1"
    second = "https://example.com/2"
    assert manager.add_url_to_queue(first) is True
    gui.url_status[first] = "completed"

    assert manager.add_url_to_queue(second) is True
    assert gui.url_status[second] == "waiting"


def test_enqueue_urls_keeps_only_first_candidate_and_ignores_rest(monkeypatch):
    manager, gui, events = _build_manager(monkeypatch)

    added, duplicated = manager._enqueue_urls(
        "https://example.com/1 https://example.com/2 https://example.com/3",
        "input",
    )

    assert (added, duplicated) == (1, 0)
    assert gui.url_queue == ["https://example.com/1"]
    info_messages = [args[2] for args, _ in events["info"] if len(args) >= 3]
    assert any("ignored 2 extra link(s)" in msg for msg in info_messages)


def test_enqueue_urls_is_rejected_when_active_item_exists(monkeypatch):
    manager, gui, events = _build_manager(monkeypatch)
    assert manager.add_url_to_queue("https://example.com/1") is True

    added, duplicated = manager._enqueue_urls("https://example.com/2", "input")

    assert (added, duplicated) == (0, 0)
    assert gui.url_queue == ["https://example.com/1"]
    warning_messages = [args[2] for args, _ in events["warning"] if len(args) >= 3]
    assert any("Only one active link is allowed" in msg for msg in warning_messages)


def test_add_mix_job_is_rejected_when_active_item_exists(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)
    assert manager.add_url_to_queue("https://example.com/1") is True

    with pytest.raises(ValueError, match="Only one active job is allowed"):
        manager.add_mix_job(["https://mix.example/1", "https://mix.example/2"])


def test_update_queue_status_blocks_new_url_when_active_exists(monkeypatch):
    """update_queue_status should not append a new URL when an active item exists."""
    manager, gui, _ = _build_manager(monkeypatch)
    assert manager.add_url_to_queue("https://example.com/1") is True

    # Try to sneak in a new waiting URL via update_queue_status
    manager.update_queue_status("https://example.com/2", "waiting")

    assert "https://example.com/2" not in gui.url_queue
    assert "https://example.com/2" not in gui.url_status


def test_update_queue_status_allows_existing_url_status_change(monkeypatch):
    """update_queue_status should still update status for URLs already in the queue."""
    manager, gui, _ = _build_manager(monkeypatch)
    assert manager.add_url_to_queue("https://example.com/1") is True

    manager.update_queue_status("https://example.com/1", "processing", "downloading")

    assert gui.url_status["https://example.com/1"] == "processing"
    assert gui.url_status_message["https://example.com/1"] == "downloading"


def test_update_queue_status_allows_terminal_status_new_url(monkeypatch):
    """update_queue_status should allow adding a URL with terminal status (e.g. completed)."""
    manager, gui, _ = _build_manager(monkeypatch)
    assert manager.add_url_to_queue("https://example.com/1") is True

    # A completed URL should be allowed even when active item exists
    manager.update_queue_status("https://example.com/done", "completed")

    assert "https://example.com/done" in gui.url_queue
    assert gui.url_status["https://example.com/done"] == "completed"
