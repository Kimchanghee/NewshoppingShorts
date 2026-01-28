"""
Video download modules
- DouyinExtract: Douyin(중국 틱톡) 영상 다운로드
- TicktokExtract: TikTok 영상 다운로드
"""
# Note: Imports use module-level functions, not class imports
# to avoid circular references
from core.download import DouyinExtract
from core.download import TicktokExtract

__all__ = [
    'DouyinExtract',
    'TicktokExtract',
]
