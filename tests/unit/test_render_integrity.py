from types import SimpleNamespace

from core.video import render_integrity


def _app(tmp_path, *, blur_applied=True, subtitle_count=2):
    audio = tmp_path / "tts.wav"
    audio.write_bytes(b"audio")
    return SimpleNamespace(
        add_subtitles=True,
        apply_blur=True,
        progress_states={
            "subtitle": {"status": "completed", "progress": 100},
            "subtitle_overlay": {"status": "completed", "progress": 100},
            "finalize": {"status": "completed", "progress": 100},
        },
        tts_sync_info={"file_path": str(audio)},
        _per_line_tts=[{"path": str(audio)}, {"path": str(audio)}],
        latest_blur_metadata={
            "requested": True,
            "completed": True,
            "applied": blur_applied,
            "regions": 1 if blur_applied else 0,
            "reason": "",
        },
        final_render_integrity={},
        render_integrity_by_path={},
    )


def test_render_integrity_passes_for_program_render(tmp_path, monkeypatch):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    app = _app(tmp_path)
    monkeypatch.setattr(
        render_integrity,
        "_probe_video",
        lambda _path: {
            "has_video": True,
            "has_audio": True,
            "width": 1080,
            "height": 1920,
            "duration": 12.0,
        },
    )

    metadata = render_integrity.create_render_integrity_metadata(
        app,
        str(video),
        subtitle_applied=True,
        subtitle_count=2,
        voice="test",
    )
    app.final_render_integrity = metadata

    result = render_integrity.validate_render_ready_for_upload(app, str(video))

    assert result["ok"]
    assert result["reasons"] == []


def test_render_integrity_blocks_missing_program_metadata(tmp_path, monkeypatch):
    video = tmp_path / "raw.mp4"
    video.write_bytes(b"video")
    app = _app(tmp_path)
    monkeypatch.setattr(
        render_integrity,
        "_probe_video",
        lambda _path: {"has_video": True, "has_audio": True, "duration": 12.0},
    )

    result = render_integrity.validate_render_ready_for_upload(app, str(video))

    assert not result["ok"]
    assert "missing_program_render_metadata" in result["reasons"]


def test_render_integrity_blocks_when_blur_was_not_applied(tmp_path, monkeypatch):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    app = _app(tmp_path, blur_applied=False)
    monkeypatch.setattr(
        render_integrity,
        "_probe_video",
        lambda _path: {"has_video": True, "has_audio": True, "duration": 12.0},
    )
    metadata = render_integrity.create_render_integrity_metadata(
        app,
        str(video),
        subtitle_applied=True,
        subtitle_count=2,
        voice="test",
    )
    app.final_render_integrity = metadata

    result = render_integrity.validate_render_ready_for_upload(app, str(video))

    assert not result["ok"]
    assert "blur_not_applied" in result["reasons"]
    assert "missing_blur_regions" in result["reasons"]
