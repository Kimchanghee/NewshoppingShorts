from core.download.KuaishouExtract import _extract_photo_id, _infer_extension


def test_extract_photo_id_from_short_video_path():
    assert _extract_photo_id("https://www.kuaishou.com/short-video/3x5zabcde") == "3x5zabcde"


def test_extract_photo_id_from_query():
    assert _extract_photo_id("https://www.kuaishou.com/something?photoId=abc12345") == "abc12345"


def test_extract_photo_id_returns_none_for_unknown_path():
    assert _extract_photo_id("https://www.kuaishou.com/") is None


def test_infer_extension_defaults_to_mp4():
    assert _infer_extension("https://cdn.example.com/path/video") == ".mp4"


def test_infer_extension_keeps_known_extensions():
    assert _infer_extension("https://cdn.example.com/path/video.webm") == ".webm"
