from __future__ import annotations

from typing import Dict, List

VOICE_PROFILES: List[Dict[str, str]] = [
    # === 여성 음성 ===
    {
        "id": "aurora",
        "label": "소희",
        "description": "맑고 밝은 톤, 생동감 있는 내레이션",
        "voice_name": "aoede",
        "gender": "female",
        "sample_text": "반갑습니다. 저는 소희예요. 맑고 밝은 목소리로 여러분께 즐거운 이야기를 전해드리고 싶어요. 언제나 활기차고 긍정적인 에너지를 담아 말씀드릴게요.",
    },
    {
        "id": "luna",
        "label": "지현",
        "description": "차분하고 부드러운 내레이션",
        "voice_name": "callirrhoe",
        "gender": "female",
        "sample_text": "안녕하세요. 지현이라고 해요. 차분하고 편안한 목소리로 여러분의 이야기를 함께 나누고 싶습니다. 부드럽고 안정적인 톤으로 귀에 쏙쏙 들어오는 내레이션을 선사할게요.",
    },
    {
        "id": "breeze",
        "label": "예린",
        "description": "산뜻하고 경쾌한 톤",
        "voice_name": "zephyr",
        "gender": "female",
        "sample_text": "안녕하세요. 예린이에요. 상쾌한 바람처럼 산뜻하고 경쾌한 목소리로 여러분과 함께하고 싶어요. 밝고 감성적인 분위기로 마음을 전달해 드릴게요.",
    },
    {
        "id": "crystal",
        "label": "다은",
        "description": "맑고 또렷한 발음",
        "voice_name": "pulcherrima",
        "gender": "female",
        "sample_text": "반갑습니다. 다은이예요. 맑고 투명한 목소리로 또렷하게 말씀드릴게요. 깨끗하고 선명한 발음으로 듣기 편한 내용을 전해드리겠습니다.",
    },
    {
        "id": "stella",
        "label": "나윤",
        "description": "따뜻하고 온화한 톤",
        "voice_name": "laomedeia",
        "gender": "female",
        "sample_text": "안녕하세요. 나윤이에요. 부드럽고 온화한 목소리로 여러분께 편안함을 드리고 싶습니다. 은은하고 따뜻한 톤으로 마음을 어루만지는 이야기를 들려드릴게요.",
    },
    # === 남성 음성 ===
    {
        "id": "radiant",
        "label": "도현",
        "description": "밝고 경쾌한 에너지",
        "voice_name": "orus",
        "gender": "male",
        "sample_text": "안녕하세요. 도현입니다. 밝고 경쾌한 남성 목소리로 명확하고 힘찬 메시지를 전달해 드리겠습니다. 활기 넘치는 에너지와 함께 즐거운 이야기를 나눠볼까요.",
    },
    {
        "id": "eclipse",
        "label": "시우",
        "description": "차분하고 신뢰감 있는 톤",
        "voice_name": "charon",
        "gender": "male",
        "sample_text": "안녕하세요. 시우입니다. 차분하고 안정감 있는 남성 목소리로 여러분께 신뢰를 드리고 싶습니다. 깊이 있는 톤으로 진중한 내레이션을 선보이겠습니다.",
    },
    {
        "id": "nebula",
        "label": "준서",
        "description": "카리스마 있고 박력있는 톤",
        "voice_name": "fenrir",
        "gender": "male",
        "sample_text": "반갑습니다. 준서라고 합니다. 카리스마 넘치는 힘 있는 목소리로 강렬한 인상을 남기고 싶습니다. 든든하고 박력 있는 발성으로 메시지를 확실하게 전달해 드릴게요.",
    },
    {
        "id": "achird",
        "label": "민재",
        "description": "따뜻하고 포근한 톤",
        "voice_name": "achird",
        "gender": "male",
        "sample_text": "안녕하세요. 민재예요. 따뜻하고 온화한 목소리로 여러분께 편안함을 선물하고 싶습니다. 부드러운 남성 톤으로 마음을 녹이는 이야기를 들려드릴게요.",
    },
    {
        "id": "orion",
        "label": "지호",
        "description": "활기차고 역동적인 톤",
        "voice_name": "puck",
        "gender": "male",
        "sample_text": "안녕하세요. 지호입니다. 활기차고 생동감 넘치는 목소리로 여러분께 에너지를 전달하고 싶어요. 열정적이고 역동적인 분위기로 함께 즐거운 시간을 만들어가요.",
    },
]

DEFAULT_MULTI_VOICE_PRESETS = [profile["voice_name"] for profile in VOICE_PROFILES[:5]]
