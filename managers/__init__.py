"""
매니저 모듈

상태 및 데이터 관리를 담당하는 매니저 클래스들을 포함합니다.

This module contains manager classes responsible for state and data management.
"""

from managers.queue_manager import QueueManager
from managers.progress_manager import ProgressManager
from managers.voice_manager import VoiceManager
from managers.output_manager import OutputManager
from managers.settings_manager import SettingsManager, get_settings_manager
from managers.youtube_manager import YouTubeManager, get_youtube_manager
from managers.processing_queue import (
    ProcessingQueue,
    UrlStatus,
    get_processing_queue,
    reset_processing_queue
)

__all__ = [
    'QueueManager',
    'ProgressManager',
    'VoiceManager',
    'OutputManager',
    'SettingsManager',
    'get_settings_manager',
    'YouTubeManager',
    'get_youtube_manager',
    # URL 처리 큐 관련
    'ProcessingQueue',
    'UrlStatus',
    'get_processing_queue',
    'reset_processing_queue',
]
