"""
TTS 음성 생성 프롬프트

발음 지침은 tts_handler.py에서 system_instruction으로 전달됨.
이 파일은 호환성 유지용.
"""


def get_tts_prompt(text: str, is_cta: bool = False, use_short: bool = True) -> str:
    """
    TTS용 텍스트 반환 (원본 그대로).
    발음 지침은 API의 system_instruction으로 전달됨.
    """
    return text
