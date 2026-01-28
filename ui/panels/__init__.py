"""
UI 패널 모듈

각 섹션별 UI 패널 클래스들을 포함합니다.
"""

from .header_panel import HeaderPanel
from .url_input_panel import URLInputPanel
from .voice_panel import VoicePanel
from .font_panel import FontPanel
from .cta_panel import CTAPanel
from .queue_panel import QueuePanel
from .progress_panel import ProgressPanel
from .url_content_panel import URLContentPanel

__all__ = [
    'HeaderPanel',
    'URLInputPanel',
    'VoicePanel',
    'FontPanel',
    'CTAPanel',
    'QueuePanel',
    'ProgressPanel',
    'URLContentPanel',
]
