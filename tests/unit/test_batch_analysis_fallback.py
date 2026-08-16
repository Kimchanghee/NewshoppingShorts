from types import SimpleNamespace

from google.genai import types

from core.video.batch.analysis import (
    _analyze_video_for_batch,
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
    assert "휴대용 미니 청소기" in app.video_analysis_result
    assert "살펴볼게요" in app.translation_result
    assert app.analysis_result["script_quality"]["ok"] is True
    assert app.analysis_result["script_quality"]["review_required"] is True
    assert app.analysis_result["subtitle_positions"] == subtitle_positions
    assert app.analysis_result["fallback_reason"] == "timeout"
    assert logs
    assert progress


def test_analyze_video_without_gemini_uses_sourcing_fallback(monkeypatch):
    logs = []
    progress = []
    app = SimpleNamespace(
        genai_client=None,
        state=SimpleNamespace(
            sourcing_result={
                "description": "fallback product copy",
                "product_info": {"name": "fallback product"},
            }
        ),
        fixed_tts_voice=None,
        last_voice_used=None,
        available_tts_voices=[],
        multi_voice_presets=[],
        _temp_downloaded_file="video.mp4",
        add_log=logs.append,
        update_progress_state=lambda *args: progress.append(args),
        detect_subtitles_with_opencv=lambda: [],
        video_analysis_result=None,
        translation_result=None,
        analysis_result={},
        get_video_duration_helper=lambda: 20.0,
    )
    monkeypatch.setattr("ui.panels.cta_panel.get_selected_cta_lines", lambda _app: [])

    _analyze_video_for_batch(app)

    assert "fallback product" in app.video_analysis_result
    assert "살펴볼게요" in app.translation_result
    assert app.analysis_result["fallback_reason"] == "Gemini analysis is unavailable"
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


def test_weak_no_audio_draft_re_reads_video_until_full_product_script(monkeypatch):
    weak = SimpleNamespace(text="=== 상품 설명 (한국어) ===\n휴대용 미니 냉풍기")
    strong = SimpleNamespace(
        text=(
            "=== 상품 설명 (한국어) ===\n"
            "더운 책상 앞에서 시원한 바람이 필요할 때가 있어요.\n"
            "이 휴대용 냉풍기는 버튼으로 바람을 조절할 수 있어요.\n"
            "화면에서는 본체를 열고 내부 구성을 확인하는 과정이 보여요.\n"
            "작은 공간에서 쓰기 편한지 실제 장면으로 비교해 보세요.\n"
            "영상 속 제품 정보는\n아래 고정댓글에서\n확인해 보세요!"
        )
    )
    responses = [weak, strong]

    class FakeFiles:
        def upload(self, **_kwargs):
            return SimpleNamespace(
                state=types.FileState.ACTIVE,
                uri="mock://video",
                mime_type="video/mp4",
                name="files/mock",
            )

    class FakeModels:
        def __init__(self):
            self.prompts = []

        def generate_content(self, **kwargs):
            self.prompts.append(kwargs["contents"][-1])
            return responses.pop(0)

    models = FakeModels()
    logs = []
    app = SimpleNamespace(
        genai_client=SimpleNamespace(files=FakeFiles(), models=models),
        state=SimpleNamespace(
            sourcing_result={
                "description": "책상 위에서 사용하는 소형 냉풍기",
                "product_info": {"name": "휴대용 미니 냉풍기"},
            }
        ),
        fixed_tts_voice=None,
        last_voice_used=None,
        available_tts_voices=[],
        multi_voice_presets=[],
        _temp_downloaded_file="video.mp4",
        add_log=logs.append,
        update_progress_state=lambda *_args: None,
        detect_subtitles_with_opencv=lambda: [],
        get_video_duration_helper=lambda: 30.0,
        token_calculator=SimpleNamespace(calculate_cost=lambda **_kwargs: {}),
        video_analysis_result=None,
        translation_result=None,
        analysis_result={},
    )
    cta = ["영상 속 제품 정보는", "아래 고정댓글에서", "확인해 보세요!"]
    monkeypatch.setattr(
        "ui.panels.cta_panel.get_selected_cta_lines", lambda _app: cta
    )
    monkeypatch.setattr(
        "core.video.batch.analysis._source_has_audio", lambda _path: False
    )

    _analyze_video_for_batch(app)

    assert len(models.prompts) == 2
    assert "영상을 처음·중간·마지막까지 다시 보고" in models.prompts[1]
    assert app.analysis_result["script_quality"]["ok"] is True
    assert app.analysis_result["script_quality"]["repair_attempts"] == 1
    assert app.analysis_result["script_quality"]["source_has_audio"] is False
    assert "버튼으로 바람을 조절할 수 있어요" in app.translation_result


def test_no_audio_probe_overrides_wrong_transcript_mode_and_repairs_visually(monkeypatch):
    wrong_mode = SimpleNamespace(
        text=(
            "=== 중국어 원본 대본 ===\n"
            "[00:01] 나레이터: 这是一款便携风扇。\n"
            "[00:05] 나레이터: 按下按钮就能使用。"
        )
    )
    repaired = SimpleNamespace(
        text=(
            "=== 상품 설명 (한국어) ===\n"
            "더운 책상 앞에서 간편한 바람이 필요할 때가 있어요.\n"
            "이 제품은 화면에 보이는 작은 휴대용 냉풍기예요.\n"
            "버튼을 눌러 작동 상태를 바꾸는 모습이 차례로 보여요.\n"
            "사용 공간에 잘 맞는지 실제 크기와 조작 장면을 비교해 보세요.\n"
            "영상 속 제품 정보는\n아래 고정댓글에서\n확인해 보세요!"
        )
    )
    responses = [wrong_mode, repaired]

    class FakeFiles:
        def upload(self, **_kwargs):
            return SimpleNamespace(
                state=types.FileState.ACTIVE,
                uri="mock://video",
                mime_type="video/mp4",
                name="files/mock",
            )

    class FakeModels:
        def __init__(self):
            self.prompts = []

        def generate_content(self, **kwargs):
            self.prompts.append(kwargs["contents"][-1])
            return responses.pop(0)

    models = FakeModels()
    app = SimpleNamespace(
        genai_client=SimpleNamespace(files=FakeFiles(), models=models),
        state=SimpleNamespace(
            sourcing_result={
                "description": "책상 위에서 사용하는 소형 냉풍기",
                "product_info": {"name": "휴대용 미니 냉풍기"},
            }
        ),
        fixed_tts_voice=None,
        last_voice_used=None,
        available_tts_voices=[],
        multi_voice_presets=[],
        _temp_downloaded_file="silent-video.mp4",
        add_log=lambda _message: None,
        update_progress_state=lambda *_args: None,
        detect_subtitles_with_opencv=lambda: [],
        get_video_duration_helper=lambda: 30.0,
        token_calculator=SimpleNamespace(calculate_cost=lambda **_kwargs: {}),
        video_analysis_result=None,
        translation_result=None,
        analysis_result={},
    )
    cta = ["영상 속 제품 정보는", "아래 고정댓글에서", "확인해 보세요!"]
    monkeypatch.setattr(
        "ui.panels.cta_panel.get_selected_cta_lines", lambda _app: cta
    )
    monkeypatch.setattr(
        "core.video.batch.analysis._source_has_audio", lambda _path: False
    )

    _analyze_video_for_batch(app)

    assert len(models.prompts) == 2
    assert app.analysis_result["script_generation_mode"] == "visual_product_description"
    assert app.analysis_result["script_quality"]["repair_attempts"] == 1
    assert "휴대용 냉풍기예요" in app.translation_result
