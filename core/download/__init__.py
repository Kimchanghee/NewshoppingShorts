"""
Video download modules
- DouyinExtract: 도우인(抖音) 영상 다운로드
"""
# Note: Imports use module-level functions, not class imports
# to avoid circular references
from core.download import DouyinExtract

__all__ = [
    'DouyinExtract',
]
