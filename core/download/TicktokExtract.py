import re
import json
import html
from typing import Dict, List, Optional, Tuple, Iterable

from utils.logging_config import get_logger
from utils import DriverConfig
from utils import Tool

logger = get_logger(__name__)

SIGI_RE = re.compile(r"<script id=\"SIGI_STATE\"[^>]*>(.*?)</script>", re.S)

def tiktok_extract_from_html(html_text: str) -> Tuple[Optional[str], Dict[str, str]]:
    meta = {}
    m_title = re.search(r"<title>(.*?)</title>", html_text, re.S | re.I)
    if m_title:
        meta["title"] = html.unescape(m_title.group(1)).strip()

    m = SIGI_RE.search(html_text)
    if m:
        try:
            data = json.loads(m.group(1))
            item_mod = data.get("ItemModule") or {}
            item = None
            if isinstance(item_mod, dict) and item_mod:
                item = next(iter(item_mod.values()))
            if item:
                author = item.get("author") or item.get("nickname")
                desc = item.get("desc") or item.get("title")
                vid = item.get("id") or item.get("aweme_id")
                if author:
                    meta["author"] = str(author)
                if desc:
                    meta["desc"] = str(desc)
                if vid:
                    meta["id"] = str(vid)

                video = item.get("video") or {}
                candidates = []
                for bi in video.get("bitrateInfo", []) or []:
                    play = bi.get("PlayAddr") or bi.get("playAddr") or {}
                    urls = (
                        play.get("UrlList")
                        or play.get("urlList")
                        or play.get("Url")
                        or []
                    )
                    if isinstance(urls, list):
                        candidates.extend(urls)
                    elif isinstance(urls, str):
                        candidates.append(urls)
                for k in ("playAddr", "downloadAddr"):
                    v = video.get(k)
                    if isinstance(v, str):
                        candidates.append(v)

                best = Tool.pick_best_url(candidates, platform="tiktok")
                if best:
                    return best, meta
        except Exception as e:
            logger.debug("[TikTok] SIGI_STATE 파싱 실패: %s", e)

    candidates = re.findall(r"https?://[^\"'<>\s]+", html_text)
    url_ = Tool.pick_best_url(candidates, platform="tiktok")
    return url_, meta

def fetch_tiktok_video(url: str) -> Tuple[Optional[str], Dict[str, str]]:
    final = DriverConfig.resolve_redirect(url, headers={"Referer": "https://www.tiktok.com/"})
    with DriverConfig.http_open(final, headers={"Referer": "https://www.tiktok.com/"}) as resp:
        html_text = resp.read().decode("utf-8", errors="ignore")
    return tiktok_extract_from_html(html_text)