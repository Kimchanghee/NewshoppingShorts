# -*- coding: utf-8 -*-
"""Prompt for adapting spoken source audio into a Korean product pitch."""

from __future__ import annotations

from typing import List

from core.video.script_quality import maximum_body_characters, quality_requirements


def get_translation_prompt(
    script_text: str,
    video_duration: float,
    target_duration: float,
    target_chars: int,
    length_instruction: str,
    cta_lines: List[str],
    product_name: str = "",
    product_description: str = "",
) -> str:
    """Translate facts while rewriting fragments as a coherent introduction."""
    cta = list(cta_lines or [])
    while len(cta) < 3:
        cta.append("")
    cta_chars = len("".join(cta))
    min_sentences, min_body_chars = quality_requirements(video_duration)
    quality_max_chars = maximum_body_characters(video_duration)
    target_body_chars = max(min_body_chars, int(target_chars) - cta_chars)
    min_chars = max(min_body_chars, int(target_body_chars * 0.85))
    max_chars = min(
        quality_max_chars,
        max(min_chars + 10, int(target_body_chars * 1.20)),
    )
    min_chars = min(min_chars, max_chars - 10)
    context = str(product_name or product_description or "").strip() or "제공되지 않음"

    return f"""아래 중국어 음성 대본의 사실을 바탕으로 한국어 상품 소개 대본을 작성하세요.

【원본 음성 대본】
{script_text}

【상품 참고 정보】
{context}

원본 영상은 {video_duration:.1f}초이고 목표 음성 길이는 {target_duration:.1f}초입니다.
CTA를 제외한 본문 목표는 약 {target_body_chars}자, 허용 범위는 {min_chars}~{max_chars}자입니다.
길이 조절 참고: {length_instruction}

이 작업은 직역이 아니라 사실을 보존한 상품 소개 각색입니다.
원문이 상품명, 감탄사, 짧은 구절 위주여도 그대로 나열하지 말고 자연스러운 완전한 문장으로 연결하세요.
본문은 최소 {min_sentences}문장으로 작성하고 모든 문장에 서술어와 종결 표현을 넣으세요.
문제나 사용 상황 → 제품 정체 → 원문에서 확인되는 기능·사용법 → 실용적 의미 순서로 구성하세요.
원문에 없는 가격, 브랜드, 수치, 재질, 인증, 성능은 만들지 마세요.
자기소개, 판매자·출연자 이름, 계정명, 연락처는 제외하세요.
중국 플랫폼명과 브랜드는 필요하면 ‘온라인몰’ 또는 ‘이 제품’으로 자연스럽게 바꾸세요.
중국 화폐·단위는 문맥상 꼭 필요할 때만 한국식으로 환산하고, 확실하지 않으면 생략하세요.
소리 내어 읽기 좋은 차분한 한국어 구어체를 사용하세요.
불릿, 번호, 타임스탬프, 마크다운, 머리말은 출력하지 마세요.

본문 뒤에는 아래 세 줄을 글자·순서·줄바꿈을 바꾸지 말고 붙이세요.
{cta[0]}
{cta[1]}
{cta[2]}

출력 직전에 단어 나열이 없는지, 최소 문장 수와 본문 길이를 지켰는지 확인한 뒤 최종 대본만 출력하세요.
"""
