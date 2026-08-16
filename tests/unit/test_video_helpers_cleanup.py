from types import SimpleNamespace

from app.video_helpers import VideoHelpers


def test_cleanup_preserves_user_local_source_and_removes_registered_temp(tmp_path):
    local_source = tmp_path / "user-source.mp4"
    local_source.write_bytes(b"source")
    derived = tmp_path / "batch-trim.mp4"
    derived.write_bytes(b"temporary")
    app = SimpleNamespace(
        video_source="local",
        local_file_path=str(derived),
        _source_local_file_path=str(local_source),
        _temp_downloaded_file=str(derived),
        _temp_downloaded_files=[str(derived)],
    )

    VideoHelpers(app).cleanup_temp_files()

    assert local_source.exists()
    assert not derived.exists()
    assert app._temp_downloaded_file is None
    assert app._temp_downloaded_files == []


def test_cleanup_preserves_untrimmed_local_source(tmp_path):
    local_source = tmp_path / "user-source.mp4"
    local_source.write_bytes(b"source")
    app = SimpleNamespace(
        video_source="local",
        local_file_path=str(local_source),
        _source_local_file_path=str(local_source),
        _temp_downloaded_file=str(local_source),
        _temp_downloaded_files=[],
    )

    VideoHelpers(app).cleanup_temp_files()

    assert local_source.exists()
