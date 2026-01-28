import re
from typing import Dict, List, Optional, Tuple, Iterable

from utils import DriverConfig
from utils import Tool

VIDEO_DATA_PATTERNS = [
    re.compile(r'"play_addr".*?"uri":"([^"]+)"', re.S),
    re.compile(r'"vid":"([^"]+)"', re.S),
    re.compile(r'"aweme_id":"([^"]+)"', re.S),
    re.compile(r'video_id["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{8,})', re.S),
    re.compile(r'aweme_id["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{8,})', re.S),
    re.compile(r'/video/(\d{10,})', re.S),
]

URL_PATTERNS = [
    re.compile(r'https://[^"\'<>\s]*douyin[^"\'<>\s]*play[^"\'<>\s]*', re.S),
    re.compile(r'https://[^"\'<>\s]*aweme[^"\'<>\s]*play[^"\'<>\s]*', re.S),
    re.compile(r'https://[^"\'<>\s]*\.mp4[^"\'<>\s]*', re.S),
]


def extract_video_ids(html_text: str) -> List[str]:
    """HTML에서 다양한 방법으로 비디오 ID 추출"""
    video_ids = []
    
    for pattern in VIDEO_DATA_PATTERNS:
        matches = pattern.findall(html_text)
        video_ids.extend(matches)
    
    # 중복 제거 및 유효성 검사
    unique_ids = []
    for vid in video_ids:
        if vid and len(vid) >= 8 and vid not in unique_ids:
            unique_ids.append(vid)
    
    return unique_ids

def extract_direct_urls(html_text: str) -> List[str]:
    """HTML에서 직접 비디오 URL 추출"""
    urls = []
    
    for pattern in URL_PATTERNS:
        matches = pattern.findall(html_text)
        urls.extend(matches)
    
    # 일반 URL 패턴도 시도
    all_urls = re.findall(r"https?://[^\"'<>\s]+", html_text)
    for url in all_urls:
        if "douyin" in url and ("play" in url or "video" in url or ".mp4" in url):
            urls.append(url)
    
    return urls
    
    
def _json_walk_urls(obj) -> List[str]:
    urls = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            urls.extend(_json_walk_urls(v))
    elif isinstance(obj, list):
        for v in obj:
            urls.extend(_json_walk_urls(v))
    elif isinstance(obj, str):
        if obj.startswith("http") and ("douyin" in obj or "aweme" in obj):
            urls.append(obj)
    return urls