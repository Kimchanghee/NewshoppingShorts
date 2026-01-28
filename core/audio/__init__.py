"""
Audio Processing Module
=======================
TTS 생성 및 오디오 처리를 위한 통합 모듈입니다.

주요 컴포넌트:
- AudioPipeline: TTS 생성, 배속 적용, 길이 조정을 위한 통합 파이프라인
- AudioConfig: 오디오 처리 설정
"""

from .pipeline import AudioPipeline, AudioConfig

__all__ = ["AudioPipeline", "AudioConfig"]
