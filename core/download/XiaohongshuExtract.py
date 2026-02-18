import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

from utils.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    "Referer": "https://www.xiaohongshu.com/",
    "Origin": "https://www.xiaohongshu.com",
}

_XHS_URL_RE = re.compile(
    r"(https?://(?:www\.)?xiaohongshu\.com/[^\s]+|https?://xhslink\.com/[^\s]+)",
    re.IGNORECASE,
)
_PAGE_DOMAIN_SUFFIXES = ("xiaohongshu.com", "xhslink.com")
_MEDIA_DOMAIN_SUFFIXES = ("xhscdn.com", "xhscdn.net", "xiaohongshu.com")


def _is_domain_allowed(host: str, suffixes: Tuple[str, ...]) -> bool:
    host = (host or "").lower()
    if not host:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def _extract_url_from_text(text: str) -> str:
    matched = _XHS_URL_RE.search((text or "").strip())
    return matched.group(1) if matched else (text or "").strip()


def _sanitize_url(url_or_text: str, session: requests.Session, timeout: int) -> str:
    clean = _extract_url_from_text(url_or_text)
    if not clean.startswith(("http://", "https://")):
        clean = f"https://{clean}"

    parsed = urlparse(clean)
    if not _is_domain_allowed(parsed.netloc, _PAGE_DOMAIN_SUFFIXES):
        raise ValueError(f"Unsupported Xiaohongshu domain: {parsed.netloc}")

    # xhslink is a short link domain that redirects to xiaohongshu page URLs.
    # Resolve redirect manually so we can validate the final domain.
    current = clean
    for _ in range(3):
        host = urlparse(current).netloc.lower()
        if "xhslink.com" not in host:
            break
        resp = session.get(current, allow_redirects=False, timeout=timeout)
        if resp.status_code not in (301, 302, 303, 307, 308):
            break
        location = resp.headers.get("Location")
        if not location:
            raise RuntimeError("xhslink redirect failed: missing Location header")
        current = urljoin(current, location)

    final_host = urlparse(current).netloc
    if not _is_domain_allowed(final_host, _PAGE_DOMAIN_SUFFIXES):
        raise ValueError(f"Unexpected redirected domain: {final_host}")
    return current


def _fetch_html(url: str, session: requests.Session, timeout: int) -> str:
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    final_host = urlparse(resp.url).netloc
    if not _is_domain_allowed(final_host, _PAGE_DOMAIN_SUFFIXES):
        raise ValueError(f"Unexpected final page domain: {final_host}")
    return resp.text


def _parse_initial_state(html_text: str) -> Dict[str, Any]:
    marker = "window.__INITIAL_STATE__="
    starts = [m.start() for m in re.finditer(re.escape(marker), html_text)]
    if not starts:
        raise RuntimeError("window.__INITIAL_STATE__ not found")

    for start in reversed(starts):
        raw_block = html_text[start + len(marker) :]
        end = raw_block.find("</script>")
        if end < 0:
            continue
        payload = raw_block[:end].strip().rstrip(";")
        payload = payload.replace("\\/", "/")
        payload = re.sub(r"\bundefined\b", "null", payload)
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            continue

    raise RuntimeError("failed to parse window.__INITIAL_STATE__ JSON")


def _extract_note(state: Dict[str, Any]) -> Dict[str, Any]:
    note_root = state.get("note") or {}
    note_map = note_root.get("noteDetailMap") or {}
    if isinstance(note_map, dict) and note_map:
        note_id = note_root.get("firstNoteId") or next(iter(note_map.keys()))
        note = (note_map.get(note_id) or {}).get("note")
        if isinstance(note, dict):
            return note

    phone_note = (((state.get("noteData") or {}).get("data") or {}).get("noteData") or {})
    if isinstance(phone_note, dict) and phone_note:
        return phone_note

    raise RuntimeError("note data not found in parsed state")


def _decode_media_url(url: str) -> str:
    text = bytes(url, "utf-8").decode("unicode_escape")
    text = text.replace("\\/", "/").strip()
    if text.startswith("//"):
        return "https:" + text
    return text


def _extract_video_candidates(note: Dict[str, Any], html_text: str) -> List[str]:
    candidates: List[str] = []

    def add_candidate(url: Optional[str]) -> None:
        if not url:
            return
        decoded = _decode_media_url(url)
        if not decoded.startswith(("http://", "https://")):
            return

        host = urlparse(decoded).netloc
        if not _is_domain_allowed(host, _MEDIA_DOMAIN_SUFFIXES):
            return

        if decoded not in candidates:
            candidates.append(decoded)
        if decoded.startswith("http://"):
            secure = "https://" + decoded[len("http://") :]
            if secure not in candidates:
                candidates.append(secure)

    video = note.get("video") or {}
    consumer = video.get("consumer") or {}
    origin_key = consumer.get("originVideoKey")
    if origin_key:
        add_candidate(f"https://sns-video-bd.xhscdn.com/{origin_key}")

    add_candidate(consumer.get("originVideoUrl"))
    add_candidate(consumer.get("wmVideoUrl"))

    stream = ((video.get("media") or {}).get("stream") or {})
    for codec in ("h266", "h265", "av1", "h264"):
        items = stream.get(codec) or []
        sorted_items = sorted(
            items,
            key=lambda x: (
                int(x.get("height") or 0),
                int(x.get("size") or 0),
                int(x.get("videoBitrate") or 0),
            ),
            reverse=True,
        )
        for item in sorted_items:
            add_candidate(item.get("masterUrl"))
            for backup in item.get("backupUrls") or []:
                add_candidate(backup)

    for match in re.finditer(
        r'<meta\s+name=["\']og:video["\']\s+content=["\']([^"\']+)["\']',
        html_text,
        re.IGNORECASE,
    ):
        add_candidate(match.group(1))

    # Fallback from raw page HTML
    for candidate in re.findall(r"https?://[^\s\"'<>]+", html_text):
        if ".xhscdn." in candidate and (".mp4" in candidate or "videoplayback" in candidate):
            add_candidate(candidate)

    return candidates


def _derive_note_id(url: str, note: Dict[str, Any]) -> str:
    for key in ("noteId", "id", "note_id"):
        value = note.get(key)
        if value:
            return str(value)

    matched = re.search(r"/(?:explore|discovery/item)/([a-zA-Z0-9]+)", url)
    if matched:
        return matched.group(1)
    return "xhs_video"


def _basic_mp4_check(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) < 1024:
        return False
    with open(path, "rb") as f:
        head = f.read(64)
    return b"ftyp" in head


def _ffprobe_info(path: str) -> Tuple[bool, str]:
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        return False, "ffprobe not found"

    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height,duration",
        "-of",
        "json",
        path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return False, (proc.stderr or "").strip() or "ffprobe failed"

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False, "ffprobe returned non-JSON output"

    streams = data.get("streams") or []
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        return False, "no video stream found"
    return True, "video stream verified"


def _verify_video_file(path: str) -> Tuple[bool, str]:
    if not _basic_mp4_check(path):
        return False, "invalid MP4 signature or too small"

    ok, msg = _ffprobe_info(path)
    if ok:
        return True, msg
    if "ffprobe not found" in msg:
        return True, "ffprobe unavailable; basic MP4 signature check passed"
    return False, msg


def _download_candidate(
    media_url: str,
    out_path: str,
    session: requests.Session,
    timeout: int,
) -> Tuple[bool, str]:
    part_path = out_path + ".part"
    if os.path.exists(part_path):
        os.remove(part_path)

    try:
        with session.get(media_url, stream=True, timeout=timeout) as resp:
            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}"

            with open(part_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
    except requests.RequestException as e:
        return False, f"request error: {e}"

    ok, verify_msg = _verify_video_file(part_path)
    if not ok:
        try:
            os.remove(part_path)
        except Exception:
            pass
        return False, f"invalid video file: {verify_msg}"

    if os.path.exists(out_path):
        os.remove(out_path)
    os.replace(part_path, out_path)
    return True, f"saved {os.path.getsize(out_path)} bytes ({verify_msg})"


def download_xiaohongshu_video(url: str, max_retries: int = 3, timeout: int = 30) -> str:
    temp_dir: Optional[str] = None
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            logger.info(
                "[Xiaohongshu] download start: %s%s",
                url,
                f" (retry {attempt + 1}/{max_retries})" if attempt > 0 else "",
            )

            session = requests.Session()
            session.headers.update(_DEFAULT_HEADERS)

            clean_url = _sanitize_url(url, session, timeout)
            html_text = _fetch_html(clean_url, session, timeout)
            state = _parse_initial_state(html_text)
            note = _extract_note(state)
            candidates = _extract_video_candidates(note, html_text)
            if not candidates:
                raise RuntimeError("video URL candidates not found")

            if temp_dir is None:
                temp_dir = tempfile.mkdtemp(prefix="xiaohongshu_video_")

            note_id = _derive_note_id(clean_url, note)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            local_path = os.path.join(temp_dir, f"xiaohongshu_{note_id}_{timestamp}.mp4")

            logger.info("[Xiaohongshu] %d candidate URLs found", len(candidates))
            for idx, candidate in enumerate(candidates, 1):
                logger.debug("[Xiaohongshu] try candidate %d/%d", idx, len(candidates))
                ok, msg = _download_candidate(candidate, local_path, session, timeout)
                if ok:
                    logger.info("[Xiaohongshu] download complete: %s", local_path)
                    return local_path
                logger.debug("[Xiaohongshu] candidate failed: %s", msg)

            raise RuntimeError("all candidate URLs failed")
        except Exception as e:
            last_error = e
            logger.error(
                "[Xiaohongshu] download failed on attempt %d/%d: %s",
                attempt + 1,
                max_retries,
                e,
            )
            if attempt < max_retries - 1:
                time.sleep(min(6, (attempt + 1) * 2))

    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
    raise RuntimeError(
        f"Xiaohongshu download failed after {max_retries} attempts: {last_error}"
    )
