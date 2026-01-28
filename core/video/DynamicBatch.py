"""
DynamicBatch - Backward Compatibility Wrapper

This file has been refactored into a modular structure under core/video/batch/.
This wrapper maintains backward compatibility for existing imports.

New modular structure:
- core/video/batch/utils.py: Utility functions
- core/video/batch/encoder.py: GPU encoding functions
- core/video/batch/tts_handler.py: TTS generation and processing
- core/video/batch/subtitle_handler.py: Subtitle handling
- core/video/batch/analysis.py: Video analysis and translation
- core/video/batch/processor.py: Main batch processing logic

All functions are re-exported here for backward compatibility.
"""

# Re-export all functions from the batch module
from .batch import (
    # Main processor functions
    dynamic_batch_processing_thread,
    clear_all_previous_results,

    # Utility functions
    save_wave_file,
    _extract_product_name,
    _extract_text_from_response,
    _get_voice_display_name,
    _translate_error_message,
    _get_short_error_message,
    _select_sentences_with_priority,
    _split_text_naturally,
    parse_script_from_text,

    # Encoder functions
    RealtimeEncodingLogger,
    _check_gpu_encoder_available,
    _ensure_even_resolution,

    # TTS functions
    analyze_tts_with_gemini,
    combine_tts_files_with_speed,

    # Subtitle functions
    create_subtitle_clips_for_speed,
)

# GPU encoder cache variable (maintained for compatibility)
_GPU_ENCODER_AVAILABLE = None

__all__ = [
    'dynamic_batch_processing_thread',
    'clear_all_previous_results',
    'save_wave_file',
    '_extract_product_name',
    '_extract_text_from_response',
    '_get_voice_display_name',
    '_translate_error_message',
    '_get_short_error_message',
    '_select_sentences_with_priority',
    '_split_text_naturally',
    'parse_script_from_text',
    'RealtimeEncodingLogger',
    '_check_gpu_encoder_available',
    '_ensure_even_resolution',
    'analyze_tts_with_gemini',
    'combine_tts_files_with_speed',
    'create_subtitle_clips_for_speed',
]
