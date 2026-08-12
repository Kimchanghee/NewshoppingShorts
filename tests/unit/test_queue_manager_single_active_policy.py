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


class DummyLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class DummyTreeItem:
    def __init__(self, metadata, display="https://example.com/item"):
        self.metadata = metadata
        self.display = display

    def data(self, *_args):
        return self.metadata

    def text(self, column):
        return self.display if column == 1 else ""


class DummyTree:
    def __init__(self, items):
        self.items = items

    def selectedItems(self):
        return self.items


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


def test_summer_coupang_youtube_status_expires_without_upload_token(monkeypatch):
    manager = QueueManager.__new__(QueueManager)
    gui = SimpleNamespace(
        summer_status_interval=DummyLabel(),
        summer_status_queue=DummyLabel(),
        summer_status_next=DummyLabel(),
        summer_status_youtube=DummyLabel(),
    )
    manager.gui = gui
    settings = SimpleNamespace(
        get_youtube_connected=lambda: True,
        get_youtube_channel_info=lambda: {"channel_name": "Summer Channel"},
    )
    monkeypatch.setattr(queue_module, "get_settings_manager", lambda: settings)
    monkeypatch.setattr(
        QueueManager,
        "_youtube_upload_token_exists",
        staticmethod(lambda: False),
    )

    manager._update_summer_coupang_status_labels(
        {
            "counts": {"completed": 12, "waiting": 59},
            "total": 71,
            "next_planned_number": "[168]",
            "next_scheduled_display": "07-03 12:00",
            "interval_minutes": 240,
        }
    )

    assert gui.summer_status_youtube.text == "YouTube\n업로드 권한 만료"


def test_summer_coupang_youtube_status_shows_connected_with_upload_token(monkeypatch):
    manager = QueueManager.__new__(QueueManager)
    gui = SimpleNamespace(
        summer_status_interval=DummyLabel(),
        summer_status_queue=DummyLabel(),
        summer_status_next=DummyLabel(),
        summer_status_youtube=DummyLabel(),
    )
    manager.gui = gui
    settings = SimpleNamespace(
        get_youtube_connected=lambda: True,
        get_youtube_channel_info=lambda: {"channel_name": "Summer Channel"},
    )
    monkeypatch.setattr(queue_module, "get_settings_manager", lambda: settings)
    monkeypatch.setattr(
        QueueManager,
        "_youtube_upload_token_exists",
        staticmethod(lambda: True),
    )

    manager._update_summer_coupang_status_labels(
        {
            "counts": {"completed": 12, "waiting": 59},
            "total": 71,
            "next_planned_number": "[168]",
            "next_scheduled_display": "07-03 12:00",
            "interval_minutes": 240,
        }
    )

    assert gui.summer_status_youtube.text == "YouTube\n연결됨 Summer Channel"


def test_clear_waiting_deletes_local_and_scheduled_rows(monkeypatch):
    manager, gui, events = _build_manager(monkeypatch)
    gui.url_queue = ["https://example.com/local"]
    gui.url_status = {"https://example.com/local": "waiting"}
    monkeypatch.setattr(
        queue_module,
        "build_summer_coupang_queue_snapshot",
        lambda: {"total": 2, "counts": {"waiting": 2, "processing": 0}},
    )
    calls = []
    monkeypatch.setattr(
        queue_module,
        "delete_summer_coupang_queue_items",
        lambda scope, **kwargs: calls.append((scope, kwargs))
        or {"deleted": 2, "busy": False},
    )

    manager.clear_waiting_only()

    assert gui.url_queue == []
    assert gui.url_status == {}
    assert calls == [("waiting", {"selected_ids": None})]
    info_messages = [args[2] for args, _ in events["info"] if len(args) >= 3]
    assert "대기 중인 작업 3건을 삭제했습니다." in info_messages


def test_remove_selected_deletes_scheduled_row_by_stable_id(monkeypatch):
    manager, gui, events = _build_manager(monkeypatch)
    gui.url_listbox = DummyTree(
        [DummyTreeItem({"source": "scheduled", "id": "scheduled-001", "status": "waiting"})]
    )
    calls = []
    monkeypatch.setattr(manager, "update_url_listbox", lambda: None)
    monkeypatch.setattr(
        queue_module,
        "delete_summer_coupang_queue_items",
        lambda scope, **kwargs: calls.append((scope, kwargs))
        or {"deleted": 1, "busy": False},
    )

    manager.remove_selected_url()

    assert calls == [
        ("selected", {"selected_ids": ["scheduled-001"]})
    ]
    info_messages = [args[2] for args, _ in events["info"] if len(args) >= 3]
    assert "선택한 항목 1건을 삭제했습니다." in info_messages


def test_clear_all_preserves_processing_rows_in_both_sources(monkeypatch):
    manager, gui, events = _build_manager(monkeypatch)
    gui.url_queue = ["https://example.com/waiting", "https://example.com/processing"]
    gui.url_status = {
        "https://example.com/waiting": "waiting",
        "https://example.com/processing": "processing",
    }
    monkeypatch.setattr(
        queue_module,
        "build_summer_coupang_queue_snapshot",
        lambda: {"total": 2, "counts": {"waiting": 1, "processing": 1}},
    )
    monkeypatch.setattr(
        queue_module,
        "delete_summer_coupang_queue_items",
        lambda scope, **kwargs: {"deleted": 1, "busy": False, "kept_processing": 1},
    )

    manager.clear_url_queue()

    assert gui.url_queue == ["https://example.com/processing"]
    assert gui.url_status == {"https://example.com/processing": "processing"}
    info_messages = [args[2] for args, _ in events["info"] if len(args) >= 3]
    assert any("진행 중 2건은 유지했습니다." in message for message in info_messages)
