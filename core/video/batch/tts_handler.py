"""
TTS Handler for Batch Processing (호환성 유지 모듈)
====================================================
이 파일은 기존 코드와의 호환성을 유지하기 위한 re-export 모듈입니다.

실제 구현은 다음 파일들로 분리되었습니다:
- audio_utils.py: 오디오 유틸리티 (ffmpeg, 무음 제거, 정규화)
- whisper_analyzer.py: Whisper STT 분석
- tts_speed.py: TTS 배속 처리
- tts_generator.py: TTS 생성

기존 코드에서 from .tts_handler import xxx 로 사용하던 부분은
그대로 동작합니다 (이 파일이 re-export 해줍니다).
"""

# ============================================================================
# Audio Utilities (audio_utils.py에서 가져옴)
# ============================================================================
from .audio_utils import (
    _ensure_pydub_converter,
    _write_wave_fallback,
    _trim_silence,
    _prepare_segment,
)

# ============================================================================
# Whisper Analyzer (whisper_analyzer.py에서 가져옴)
# ============================================================================
from .whisper_analyzer import (
    analyze_tts_with_whisper,
    analyze_tts_with_gemini,
)

# ============================================================================
# TTS Speed Processing (tts_speed.py에서 가져옴)
# ============================================================================
from .tts_speed import (
    _apply_speed_to_segment_tts,
    combine_tts_files_with_speed,
)

# ============================================================================
# TTS Generator (tts_generator.py에서 가져옴)
# ============================================================================
from .tts_generator import (
    _create_fallback_metadata,
    _generate_tts_full_script,
    _generate_tts_for_segment,
    _generate_tts_for_batch,
    _cleanup_previous_attempts,
)

# ============================================================================
# 모든 공개 함수들을 __all__에 명시 (import * 지원)
# ============================================================================
__all__ = [
    # audio_utils
    '_ensure_pydub_converter',
    '_write_wave_fallback',
    '_trim_silence',
    '_prepare_segment',
    # whisper_analyzer
    'analyze_tts_with_whisper',
    'analyze_tts_with_gemini',
    # tts_speed
    '_apply_speed_to_segment_tts',
    'combine_tts_files_with_speed',
    # tts_generator
    '_create_fallback_metadata',
    '_generate_tts_full_script',
    '_generate_tts_for_segment',
    '_generate_tts_for_batch',
    '_cleanup_previous_attempts',
]
