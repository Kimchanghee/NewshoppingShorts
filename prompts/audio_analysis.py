# -*- coding: utf-8 -*-
"""
오디오 분석 프롬프트
TTS 오디오 파일의 각 문장 타임스탬프를 분석하기 위한 Gemini 프롬프트
"""

from typing import List


def get_audio_analysis_prompt(subtitle_segments: List[str]) -> str:
    """
    오디오 타임스탬프 분석용 프롬프트를 생성합니다.

    Args:
        subtitle_segments: 분석할 자막 세그먼트 리스트

    Returns:
        Gemini API에 전달할 프롬프트 문자열
    """
    # 세그먼트 목록 생성
    segment_list = "\n".join([f"{i}. {seg}" for i, seg in enumerate(subtitle_segments, 1)])

    return f"""🎧 오디오 파일을 처음부터 끝까지 주의 깊게 들으세요.

⚠️ 절대 추측하지 마세요! 실제로 들리는 소리만 기준으로 분석하세요.

```
【분석 대상 문장】
{segment_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【핵심 지시사항】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔊 오디오를 실제로 재생하며 분석하세요:
1. 파일 시작 → 첫 음성이 들리는 정확한 시점 = voice_start
2. 각 문장이 발화되는 정확한 시작/종료 시점 측정
3. 마지막 음성이 끝나는 정확한 시점 = voice_end

⚠️ 경고:
- 텍스트 길이로 시간을 추측하면 안됨
- 균등 분배로 계산하면 안됨
- 반드시 실제 오디오 파형/발화를 기준으로 측정

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【출력 형식 - JSON만 출력】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{"audio_duration": 파일전체길이, "voice_start": 첫음성시작, "voice_end": 마지막음성종료, "segments": [{{"index": 1, "text": "문장", "start": 시작초, "end": 종료초}}, ...]}}

▶ 필수 필드:
- audio_duration: 오디오 파일 총 길이 (초)
- voice_start: 무음 후 첫 음성이 시작되는 시점 (초, 소수점 2자리)
- voice_end: 마지막 음성이 끝나는 시점 (초, 소수점 2자리)

▶ segments 배열:
- index: 1부터 순차 증가
- text: 입력 문장 그대로
- start: 해당 문장 발화 시작 시점 (초, 소수점 2자리)
- end: 해당 문장 발화 종료 시점 (초, 소수점 2자리)

▶ 중요 규칙:
- 첫 번째 segment의 start == voice_start (반드시 일치)
- 마지막 segment의 end == voice_end (반드시 일치)
- 모든 segment는 시간순 정렬 (이전 end ≤ 다음 start)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【자기검증 - 출력 전 반드시 확인】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
□ 실제 오디오를 듣고 분석했는가? (추측 금지)
□ voice_start == segments[0].start 인가?
□ voice_end == segments[-1].end 인가?
□ JSON만 출력했는가? (설명/마크다운 금지)
□ 못 찾은 구간은 null 처리했는가?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
"""
