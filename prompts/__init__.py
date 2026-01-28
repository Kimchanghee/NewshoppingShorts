# -*- coding: utf-8 -*-
"""
프롬프트 모듈
각 기능별 Gemini 프롬프트를 관리합니다.
"""

from .subtitle_split import get_subtitle_split_prompt
from .audio_analysis import get_audio_analysis_prompt
from .video_analysis import get_video_analysis_prompt
from .translation import get_translation_prompt
from .video_validation import get_video_validation_prompt

__all__ = [
    'get_subtitle_split_prompt',
    'get_audio_analysis_prompt',
    'get_video_analysis_prompt',
    'get_translation_prompt',
    'get_video_validation_prompt',
]
