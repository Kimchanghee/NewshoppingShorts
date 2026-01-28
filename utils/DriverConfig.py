from urllib.parse import urlparse, urlunparse, unquote, urljoin
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from typing import Dict, List, Optional, Tuple, Iterable
import random

from utils.logging_config import get_logger

logger = get_logger(__name__)

# 강화된 헤더 설정
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# 다양한 User-Agent 목록
DESKTOP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 14; Mobile; rv:120.0) Gecko/120.0 Firefox/120.0",
]

def get_random_headers(mobile=False):
    """랜덤한 헤더 생성 (안티-봇 우회용)"""
    base = MOBILE_HEADERS.copy() if mobile else DEFAULT_HEADERS.copy()
    user_agent_pool = MOBILE_USER_AGENTS if mobile else DESKTOP_USER_AGENTS
    if not user_agent_pool:
        user_agent_pool = MOBILE_USER_AGENTS + DESKTOP_USER_AGENTS
    user_agent = random.choice(user_agent_pool) if user_agent_pool else base.get("User-Agent", "")
    if user_agent:
        base["User-Agent"] = user_agent

    # 재현성/디버깅을 위한 로깅 - 실제 선택된 UA의 특성 기록
    # User-Agent 문자열에서 실제 모바일 여부 확인
    is_actually_mobile = "Mobile" in user_agent or "iPhone" in user_agent or "Android" in user_agent
    device_type = "mobile" if is_actually_mobile else "desktop"
    browser = "Safari" if "Safari" in user_agent and "Chrome" not in user_agent else \
              "Firefox" if "Firefox" in user_agent else "Chrome"
    logger.debug("[HTTP] User-Agent 선택: %s (%s) | mobile=%s, 실제=%s", browser, device_type, mobile, device_type)

    return base

def http_open(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30):
    hdrs = get_random_headers()
    if headers:
        hdrs.update(headers)
        # 덮어쓴 UA가 있으면 다시 로깅
        if "User-Agent" in headers:
            ua = headers["User-Agent"]
            is_mobile = "Mobile" in ua or "iPhone" in ua or "Android" in ua
            browser = "Safari" if "Safari" in ua and "Chrome" not in ua else \
                      "Firefox" if "Firefox" in ua else "Chrome"
            device = "mobile" if is_mobile else "desktop"
            logger.debug("[HTTP] User-Agent 덮어씀: %s (%s)", browser, device)
    req = Request(url, headers=hdrs)
    return urlopen(req, timeout=timeout)

def _http_open(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30):
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    req = Request(url, headers=hdrs)
    return urlopen(req, timeout=timeout)

    
def resolve_redirect(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> str:
    class _NoBodyRedirect(HTTPRedirectHandler):
        pass
    opener = build_opener(_NoBodyRedirect)
    hdrs = get_random_headers()
    if headers:
        hdrs.update(headers)
        if "User-Agent" in headers:
            ua = headers["User-Agent"]
            is_mobile = "Mobile" in ua or "iPhone" in ua or "Android" in ua
            browser = "Safari" if "Safari" in ua and "Chrome" not in ua else \
                      "Firefox" if "Firefox" in ua else "Chrome"
            device = "mobile" if is_mobile else "desktop"
            logger.debug("[HTTP] User-Agent 덮어씀: %s (%s)", browser, device)
    req = Request(url, headers=hdrs)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.geturl()
    except Exception as e:
        logger.warning("[Redirect Error] %s", str(e))
        return url
    
    

def _resolve_redirect(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> str:
    class _NoBodyRedirect(HTTPRedirectHandler):
        pass
    
    opener = build_opener(_NoBodyRedirect)
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    req = Request(url, headers=hdrs)
    with opener.open(req, timeout=timeout) as resp:
        return resp.geturl()
    
def ensure_https(url: str) -> str:
    p = urlparse(url)
    if not p.scheme:
        return urlunparse(("https",) + p[1:])
    if p.scheme == "http":
        return urlunparse(("https",) + p[1:])
    return url

    
    
