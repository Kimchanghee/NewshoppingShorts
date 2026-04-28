from run_youtube_upload import _is_review_only_fallback


def test_review_only_fallback_detected_from_source():
    assert _is_review_only_fallback(
        "/tmp/anything.mp4",
        {"source": "coupang_image", "auto_publish_safe": False},
    )


def test_review_only_fallback_detected_from_filename():
    assert _is_review_only_fallback(
        "/tmp/sourcing_coupang_image_20260429_video.mp4",
        {"source": ""},
    )


def test_marketplace_video_is_not_review_only():
    assert not _is_review_only_fallback(
        "/tmp/sourcing_aliexpress_1_video.mp4",
        {"source": "aliexpress", "auto_publish_safe": True},
    )
