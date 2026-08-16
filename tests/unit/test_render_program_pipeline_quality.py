from scripts.render_program_pipeline_upload import ensure_min_upload_duration


def test_short_render_is_not_padded_with_a_frozen_frame(tmp_path):
    source = tmp_path / "short.mp4"
    source.write_bytes(b"not-media")
    verification = {
        "duration": 8.25,
        "has_audio": True,
        "is_vertical_1080x1920": True,
    }

    path, result = ensure_min_upload_duration(
        str(source), verification, tmp_path, min_duration=10.0
    )

    assert path == str(source)
    assert result == verification
    assert list(tmp_path.iterdir()) == [source]
