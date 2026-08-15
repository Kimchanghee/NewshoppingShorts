from app.showcase_page import MEDIA_BASE_URL, SAMPLES, render_ocr_showcase


def test_showcase_renders_five_before_after_video_pairs():
    html = render_ocr_showcase()

    assert html.startswith("<!doctype html>")
    assert html.count("<article class=\"sample-card\"") == 5
    assert html.count("<video controls") == 10
    assert html.count("원본 영상</strong>") == 5
    assert html.count("SSmaker 제작본</strong>") == 5
    assert "잔존 중국어 자막" in html
    assert "3,408" in html


def test_showcase_uses_public_release_assets_for_every_sample():
    html = render_ocr_showcase()

    for sample in SAMPLES:
        assert f"{MEDIA_BASE_URL}/{sample.source_filename}" in html
        assert f"{MEDIA_BASE_URL}/{sample.result_filename}" in html
        assert f"{MEDIA_BASE_URL}/poster_{sample.number}_before.jpg" in html
        assert f"{MEDIA_BASE_URL}/poster_{sample.number}_after.jpg" in html


def test_showcase_has_accessible_controls_and_responsive_assets():
    html = render_ocr_showcase()

    assert 'lang="ko"' in html
    assert 'href="#samples"' in html
    assert 'role="group" aria-label="영상 배치 선택"' in html
    assert 'aria-pressed="true">나란히' in html
    assert 'src="/static/ocr_showcase.js" defer' in html
    assert 'href="/static/ocr_showcase.css"' in html
    assert html.count('type="video/mp4"') == 10
