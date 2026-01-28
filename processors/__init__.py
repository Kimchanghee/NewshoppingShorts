"""
프로세서 모듈

비디오, 자막, TTS 처리 로직을 담당하는 프로세서 클래스들을 포함합니다.
"""

from processors.subtitle_detector import SubtitleDetector
from processors.subtitle_processor import SubtitleProcessor
from processors.tts_processor import TTSProcessor
from processors.video_composer import VideoComposer

# 하이브리드 감지 최적화 모듈 노출
try:
    from realtime_subtitle_optimization import (
        HybridSubtitleDetector,
        AdaptiveSubtitleSampler1,
        MultiFrameConsistencyDetector,
        TemporalAttentionSubtitleDetector,
        create_hybrid_detector
    )
    HYBRID_OPTIMIZATION_AVAILABLE = True
except ImportError:
    HYBRID_OPTIMIZATION_AVAILABLE = False

__all__ = [
    'SubtitleDetector',
    'SubtitleProcessor',
    'TTSProcessor',
    'VideoComposer',
    'HYBRID_OPTIMIZATION_AVAILABLE'
]
