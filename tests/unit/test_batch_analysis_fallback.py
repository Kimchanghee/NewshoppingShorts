from types import SimpleNamespace

from core.video.batch.analysis import (
    _apply_sourcing_analysis_fallback,
    _get_sourcing_fallback_text,
    _run_with_timeout,
)


def test_sourcing_fallback_text_uses_product_description():
    app = SimpleNamespace(
        state=SimpleNamespace(
            sourcing_result={
                "description": "충전식 보풀 제거기",
                "product_info": {"name": "fallback name"},
            }
        )
    )

    assert _get_sourcing_fallback_text(app) == "충전식 보풀 제거기"


def test_apply_sourcing_analysis_fallback_populates_analysis_result():
    logs = []
    progress = []
    subtitle_positions = [{"x": 1, "y": 2, "w": 3, "h": 4}]
    app = SimpleNamespace(
        state=SimpleNamespace(
            sourcing_result={
                "product_info": {
                    "name": "휴대용 미니 청소기",
                    "description": "",
                }
            }
        ),
        add_log=logs.append,
        update_progress_state=lambda *args: progress.append(args),
        detect_subtitles_with_opencv=lambda: subtitle_positions,
        video_analysis_result=None,
        translation_result=None,
        analysis_result={},
    )

    assert _apply_sourcing_analysis_fallback(app, "timeout")
    assert app.video_analysis_result == "휴대용 미니 청소기"
    assert app.translation_result == "휴대용 미니 청소기"
    assert app.analysis_result["subtitle_positions"] == subtitle_positions
    assert app.analysis_result["fallback_reason"] == "timeout"
    assert logs
    assert progress


def test_run_with_timeout_does_not_wait_for_stuck_call():
    import time

    started = time.monotonic()

    def slow_call():
        time.sleep(1)
        return "late"

    try:
        _run_with_timeout(slow_call, 0.01, "slow test call")
        assert False, "expected timeout"
    except TimeoutError:
        pass

    assert time.monotonic() - started < 0.5
