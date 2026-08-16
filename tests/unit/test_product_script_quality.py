from core.video.script_quality import (
    assess_product_script,
    build_safe_product_fallback,
    clean_product_script,
)
from prompts.translation import get_translation_prompt
from prompts.video_analysis import get_video_analysis_prompt
from processors.tts_processor import TTSProcessor


CTA = ["영상 속 제품 정보는", "아래 고정댓글에서", "확인해 보세요!"]


def test_keyword_row_is_rejected_as_product_script():
    report = assess_product_script("휴대용 미니 냉풍기 여름 필수품", 30.0, CTA)
    assert report["ok"] is False
    assert "too_few_sentences" in report["reasons"]
    assert "incomplete_or_keyword_phrases" in report["reasons"]


def test_complete_product_introduction_passes():
    script = "\n".join(
        [
            "더운 책상 앞에서 시원한 바람이 필요할 때가 있어요.",
            "이 휴대용 냉풍기는 조작부를 눌러 바람을 켤 수 있어요.",
            "화면에서는 물을 넣고 바람 세기를 조절하는 과정이 보여요.",
            "작은 공간에서 쓰기 좋은지 사용 장면을 보고 비교해 보세요.",
            *CTA,
        ]
    )
    report = assess_product_script(script, 30.0, CTA)
    assert report["ok"] is True
    assert report["sentence_count"] == 4


def test_non_korean_transcript_is_rejected_as_korean_product_copy():
    report = assess_product_script(
        "这是一款便携风扇。画面展示按钮操作。适合夏天使用。请确认商品信息。",
        30.0,
        CTA,
    )
    assert report["ok"] is False
    assert "not_korean_product_copy" in report["reasons"]


def test_overlong_draft_is_rejected_before_tts_can_drop_later_sentences():
    sentence = "영상에서 제품의 구성과 실제 사용하는 방법을 자세하게 확인할 수 있어요."
    report = assess_product_script(" ".join([sentence] * 6), 30.0, CTA)
    assert report["ok"] is False
    assert "body_too_long_for_tts" in report["reasons"]
    assert report["maximum_body_chars"] == 140


def test_safe_fallback_never_returns_bare_marketplace_title():
    script = build_safe_product_fallback(
        "휴대용 미니 냉풍기 - 계절가전",
        "",
        30.0,
        CTA,
    )
    report = assess_product_script(script, 30.0, CTA)
    assert report["ok"] is True
    assert "사용 모습을 함께 살펴볼게요" in script
    assert script.endswith(CTA[-1])


def test_clean_product_script_removes_model_header_and_bullets():
    raw = "=== 상품 설명 (한국어) ===\n- 화면에서 제품을 확인할 수 있어요."
    assert clean_product_script(raw) == "화면에서 제품을 확인할 수 있어요."


def test_no_audio_prompt_requires_full_timeline_visual_grounding():
    prompt = get_video_analysis_prompt(
        CTA,
        video_duration=30.0,
        product_name="휴대용 미니 냉풍기",
        source_has_audio=False,
    )
    assert "오디오 트랙이 없습니다" in prompt
    assert "사분의 일" in prompt
    assert "문제나 사용 상황" in prompt
    assert "명사·상품명·검색어만 나열" in prompt


def test_translation_prompt_demands_adaptation_not_literal_keyword_copy():
    prompt = get_translation_prompt(
        "[00:01] 나레이터: 冷风机 夏天 必备",
        30.0,
        20.0,
        90,
        "핵심 내용 유지",
        CTA,
        product_name="휴대용 미니 냉풍기",
    )
    assert "직역이 아니라 사실을 보존한 상품 소개 각색" in prompt
    assert "그대로 나열하지 말고" in prompt
    assert "문제나 사용 상황" in prompt


def test_subtitle_segments_use_readable_clauses_instead_of_nine_char_fragments():
    processor = TTSProcessor(None)
    script = (
        "제품 상단에는 조작하기 쉬운 버튼이 있어 풍량을 조절할 수 있습니다. "
        "작은 공간에서 편하게 사용할 수 있어요."
    )
    segments = processor._split_script_for_tts(script)
    assert len(segments) <= 5
    assert all(len(segment) <= 17 for segment in segments)
