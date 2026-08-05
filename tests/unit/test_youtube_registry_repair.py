# -*- coding: utf-8 -*-
"""YouTube post-upload duplicate-registry repair tests."""

from managers.youtube_manager import AutoUploadSettings, YouTubeManager


def _repair_item():
    return {
        "video_path": "already-moved.mp4",
        "product_info": "복구 대상 상품",
        "source_url": "https://www.coupang.com/vp/products/123",
        "video_id": "youtube-id-1",
        "upload_completed_registry_repair_required": True,
        "registry_error": "disk busy",
    }


def test_registry_repair_never_requires_a_second_youtube_upload(monkeypatch):
    calls = []

    class _Registry:
        def record(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(
        "managers.uploaded_registry.get_uploaded_registry", lambda: _Registry()
    )
    manager = YouTubeManager.__new__(YouTubeManager)
    manager._youtube_service = None
    manager._ensure_youtube_service = lambda: (_ for _ in ()).throw(
        AssertionError("YouTube service must not be called during repair")
    )
    item = _repair_item()

    assert manager._upload_video(item) is True
    assert calls[0]["video_id"] == "youtube-id-1"
    assert "upload_completed_registry_repair_required" not in item
    assert "registry_error" not in item


def test_registry_repair_failure_stays_queued_without_reupload(monkeypatch):
    class _Registry:
        def record(self, **kwargs):
            raise OSError("still unavailable")

    monkeypatch.setattr(
        "managers.uploaded_registry.get_uploaded_registry", lambda: _Registry()
    )
    manager = YouTubeManager.__new__(YouTubeManager)
    manager._youtube_service = None
    manager._ensure_youtube_service = lambda: (_ for _ in ()).throw(
        AssertionError("YouTube service must not be called during repair")
    )
    item = _repair_item()

    assert manager._upload_video(item) is False
    assert item["upload_completed_registry_repair_required"] is True
    assert "still unavailable" in item["registry_error"]


def test_lost_final_upload_response_stays_uncertain_without_reupload(monkeypatch, tmp_path):
    video = tmp_path / "uncertain.mp4"
    video.write_bytes(b"video")
    uploads = []
    released = []

    class _Registry:
        def reserve(self, **_kwargs):
            return "reservation-1", ""

        def release_reservation(self, reservation_id):
            released.append(reservation_id)

    class _UploadRequest:
        def next_chunk(self):
            uploads.append("attempt")
            raise ConnectionError("response lost after remote commit")

    class _Videos:
        def insert(self, **_kwargs):
            return _UploadRequest()

    class _Service:
        def videos(self):
            return _Videos()

    monkeypatch.setattr(
        "managers.uploaded_registry.get_uploaded_registry", lambda: _Registry()
    )
    monkeypatch.setattr(
        "managers.youtube_manager.MediaFileUpload", lambda *_args, **_kwargs: object()
    )
    manager = YouTubeManager.__new__(YouTubeManager)
    manager._youtube_service = _Service()
    manager._upload_settings = AutoUploadSettings(enabled=True)
    manager._try_post_auto_comment = lambda *_args, **_kwargs: None
    item = {
        "video_path": str(video),
        "title": "정상 제목",
        "description": "설명",
        "tags": [],
        "product_info": "복구 상품",
        "source_url": "https://www.coupang.com/vp/products/456",
        "render_integrity_required": True,
        "render_integrity": {"ok": True},
    }

    assert manager._upload_video(item) is False
    assert item["upload_outcome_uncertain"] is True
    assert item["upload_registry_reservation_id"] == "reservation-1"
    assert released == []

    assert manager._upload_video(item) is False
    assert uploads == ["attempt"]
    assert released == []


def test_upload_queue_reports_silent_account_guard_rejection():
    manager = YouTubeManager.__new__(YouTubeManager)
    manager._upload_settings = AutoUploadSettings(enabled=False)
    manager._upload_queue = []
    manager._upload_running = False
    manager._account_guard_message = lambda: "blocked account"
    manager._last_error_message = ""

    accepted = manager.add_to_upload_queue(
        video_path="ready.mp4",
        title="제목",
        render_integrity={"ok": True},
        render_integrity_required=True,
    )

    assert accepted is False
    assert manager._upload_queue == []


def test_operator_reconciliation_unblocks_quarantined_item(monkeypatch):
    calls = []

    class _Registry:
        def reconcile_reservation(self, reservation_id, *, uploaded, video_id=""):
            calls.append((reservation_id, uploaded, video_id))

    monkeypatch.setattr(
        "managers.uploaded_registry.get_uploaded_registry", lambda: _Registry()
    )
    manager = YouTubeManager.__new__(YouTubeManager)
    manager._upload_queue = []
    manager._uncertain_uploads = [
        {
            "upload_registry_reservation_id": "reservation-7",
            "upload_outcome_uncertain": True,
            "video_path": "ready.mp4",
        }
    ]
    manager._on_upload_complete = None

    assert manager.reconcile_uncertain_upload(
        "reservation-7", uploaded=False
    ) is True
    assert calls == [("reservation-7", False, "")]
    assert manager._uncertain_uploads == []
    assert len(manager._upload_queue) == 1
    assert "upload_outcome_uncertain" not in manager._upload_queue[0]
    assert "upload_registry_reservation_id" not in manager._upload_queue[0]
