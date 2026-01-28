"""
Batch Processing Module
=======================
배치 영상 처리를 담당하는 모듈입니다.
TTS 생성, 자막 싱크, 영상 인코딩 등의 기능을 제공합니다.

모듈 구조:
- utils.py: 유틸리티 함수 (텍스트 분할, 파일 저장 등)
- encoder.py: GPU 인코딩 관련 함수
- processor.py: 메인 배치 처리 워크플로우
- analysis.py: 영상 분석 및 번역
- subtitle_handler.py: 자막 생성 및 동기화

TTS 관련 모듈 (tts_handler.py에서 세분화):
- audio_utils.py: 오디오 유틸리티 (ffmpeg, 무음 제거)
- whisper_analyzer.py: Whisper STT 분석
- tts_speed.py: TTS 배속 처리
- tts_generator.py: TTS 생성
- tts_handler.py: 호환성 유지용 re-export 모듈
"""

# Main processor functions
from .processor import (
    dynamic_batch_processing_thread,
    clear_all_previous_results,
)

# Utility functions
from .utils import (
    save_wave_file,
    _extract_product_name,
    _extract_text_from_response,
    _get_voice_display_name,
    _translate_error_message,
    _get_short_error_message,
    _select_sentences_with_priority,
    _split_text_naturally,
    parse_script_from_text,
)

# Encoder functions
from .encoder import (
    RealtimeEncodingLogger,
    _check_gpu_encoder_available,
    _ensure_even_resolution,
)

# TTS handler functions
from .tts_handler import (
    analyze_tts_with_gemini,
    combine_tts_files_with_speed,
)

# Subtitle handler functions
from .subtitle_handler import (
    create_subtitle_clips_for_speed,
)

# Analysis functions
# (These are used internally by processor, not typically needed externally)

__all__ = [
    # Processor
    'dynamic_batch_processing_thread',
    'clear_all_previous_results',
    # Utils
    'save_wave_file',
    '_extract_product_name',
    '_extract_text_from_response',
    '_get_voice_display_name',
    '_translate_error_message',
    '_get_short_error_message',
    '_select_sentences_with_priority',
    '_split_text_naturally',
    'parse_script_from_text',
    # Encoder
    'RealtimeEncodingLogger',
    '_check_gpu_encoder_available',
    '_ensure_even_resolution',
    # TTS
    'analyze_tts_with_gemini',
    'combine_tts_files_with_speed',
    # Subtitle
    'create_subtitle_clips_for_speed',
]
