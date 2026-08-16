"""Quality contracts for Korean product-introduction scripts.

The video pipeline used to accept any non-empty Gemini response.  A product
name or a few noun phrases could therefore become the complete TTS script.
This module keeps the acceptance rule deterministic and independent from the
prompt so weak model responses are retried instead of silently published.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Sequence


_HEADER_RE = re.compile(
    r"^\s*(?:={2,}\s*)?(?:상품\s*설명|한국어\s*상품\s*소개|최종\s*대본)"
    r"(?:\s*\([^)]*\))?(?:\s*={2,})?\s*$",
    re.IGNORECASE,
)
_TERMINAL_RE = re.compile(r"(?:[.!?。？！…]|(?:요|니다|까요|세요|죠))\s*$")
_WORD_RE = re.compile(r"[가-힣A-Za-z0-9]+")


def clean_product_script(text: str) -> str:
    """Remove response wrappers without changing the spoken copy."""
    cleaned = []
    for raw_line in str(text or "").replace("```", "").splitlines():
        line = raw_line.strip()
        if not line or _HEADER_RE.match(line):
            continue
        line = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if line:
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def _without_cta(text: str, cta_lines: Sequence[str]) -> str:
    body = clean_product_script(text)
    for cta in cta_lines or ():
        value = str(cta or "").strip()
        if value:
            body = body.replace(value, " ")
    return re.sub(r"\s+", " ", body).strip()


def _sentences(body: str) -> list[str]:
    if not body:
        return []
    parts = re.split(r"(?<=[.!?。？！…])\s+|\n+", body)
    return [part.strip() for part in parts if part.strip()]


def quality_requirements(video_duration: float) -> tuple[int, int]:
    """Return minimum (sentences, body characters) for the source duration."""
    try:
        duration = max(10.0, float(video_duration or 0.0))
    except (TypeError, ValueError):
        duration = 10.0
    if duration < 15.0:
        return 2, 28
    if duration < 25.0:
        return 3, 42
    return 4, 60


def maximum_body_characters(video_duration: float) -> int:
    """Cap copy before TTS so later fitting never drops whole selling points."""
    try:
        duration = max(10.0, float(video_duration or 0.0))
    except (TypeError, ValueError):
        duration = 10.0
    if duration < 15.0:
        return 70
    if duration < 25.0:
        return 105
    return 140


def assess_product_script(
    text: str,
    video_duration: float,
    cta_lines: Sequence[str] = (),
) -> Dict[str, Any]:
    """Assess whether copy is a spoken product introduction, not keyword text."""
    cleaned = clean_product_script(text)
    body = _without_cta(cleaned, cta_lines)
    sentences = _sentences(body)
    min_sentences, min_body_chars = quality_requirements(video_duration)
    max_body_chars = maximum_body_characters(video_duration)
    compact_body = re.sub(r"\s+", "", body)
    hangul_count = len(re.findall(r"[가-힣]", body))
    language_chars = len(re.findall(r"[가-힣A-Za-z一-龥]", body))
    hangul_ratio = hangul_count / language_chars if language_chars else 0.0
    complete = [sentence for sentence in sentences if _TERMINAL_RE.search(sentence)]
    complete_ratio = len(complete) / len(sentences) if sentences else 0.0
    words = [word.lower() for word in _WORD_RE.findall(body) if len(word) > 1]
    unique_ratio = len(set(words)) / len(words) if words else 0.0
    reasons = []

    if len(compact_body) < min_body_chars:
        reasons.append("body_too_short")
    if len(compact_body) > max_body_chars:
        reasons.append("body_too_long_for_tts")
    if len(sentences) < min_sentences:
        reasons.append("too_few_sentences")
    if hangul_count < 8 or hangul_ratio < 0.25:
        reasons.append("not_korean_product_copy")
    if complete_ratio < 0.75:
        reasons.append("incomplete_or_keyword_phrases")
    if len(words) >= 6 and unique_ratio < 0.55:
        reasons.append("repetitive_copy")

    return {
        "ok": not reasons,
        "reasons": reasons,
        "body_chars": len(compact_body),
        "sentence_count": len(sentences),
        "complete_sentence_ratio": round(complete_ratio, 3),
        "unique_word_ratio": round(unique_ratio, 3),
        "hangul_ratio": round(hangul_ratio, 3),
        "minimum_body_chars": min_body_chars,
        "maximum_body_chars": max_body_chars,
        "minimum_sentences": min_sentences,
        "cleaned_text": cleaned,
    }


def _display_product_name(name: str) -> str:
    value = re.sub(r"\s+", " ", str(name or "")).strip(" -|,")
    # Marketplace titles often append options/categories after separators.
    value = re.split(r"\s+-\s+|\s+\|\s+", value, maxsplit=1)[0].strip()
    if len(value) > 34:
        value = value[:34].rsplit(" ", 1)[0].strip() or value[:34]
    return value or "이 제품"


def build_safe_product_fallback(
    product_name: str,
    product_description: str,
    video_duration: float,
    cta_lines: Iterable[str] = (),
) -> str:
    """Create complete, conservative copy when grounded AI retries fail.

    It deliberately avoids specifications and benefits that were not verified
    from the video.  The result is still a coherent introduction instead of a
    bare marketplace title.
    """
    name = _display_product_name(product_name or product_description)
    min_sentences, _ = quality_requirements(video_duration)
    sentences = [
        f"영상에서 {name}의 구성과 사용 모습을 함께 살펴볼게요.",
        "제품의 크기와 조작 방법을 화면으로 차근차근 확인할 수 있어요.",
        "실제로 사용하는 장면을 보면서 필요한 용도에 잘 맞는지 비교해 보세요.",
        "보관과 사용이 편한지도 마지막 장면까지 꼼꼼히 확인해 보세요.",
    ][:min_sentences]
    lines = sentences + [str(line).strip() for line in cta_lines if str(line).strip()]
    return "\n".join(lines)
