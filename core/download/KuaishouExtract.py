"""
Kuaishou video downloader.

Uses Kuaishou GraphQL APIs when possible and falls back to yt-dlp.
"""

from __future__ import annotations

import os
import re
import tempfile
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from utils.logging_config import get_logger

logger = get_logger(__name__)

GRAPHQL_URL = "https://www.kuaishou.com/graphql"

VISION_VIDEO_DETAIL_QUERY = """
query visionVideoDetail($photoId: String, $type: String, $page: String, $webPageArea: String) {
  visionVideoDetail(photoId: $photoId, type: $type, page: $page, webPageArea: $webPageArea) {
    status
    type
    photo {
      id
      duration
      caption
      photoUrl
    }
  }
}
"""

VISION_SHORT_VIDEO_RECO_QUERY = """
query visionShortVideoReco(
  $semKeyword: String
  $semCrowd: String
  $utmSource: String
  $utmMedium: String
  $page: String
  $photoId: String
  $utmCampaign: String
) {
  visionShortVideoReco(
    semKeyword: $semKeyword
    semCrowd: $semCrowd
    utmSource: $utmSource
    utmMedium: $utmMedium
    page: $page
    photoId: $photoId
    utmCampaign: $utmCampaign
  ) {
    llsid
    feeds {
      photo {
        id
        duration
        caption
        photoUrl
      }
    }
  }
}
"""

_URL_RE = re.compile(
    r"(https?://(?:[\w-]+\.)?(?:kuaishou\.com|kwai\.com)/[^\s\"'<>]+)",
    re.IGNORECASE,
)

_PAGE_DOMAIN_SUFFIXES = ("kuaishou.com", "kwai.com")
_SHORT_URL_HOSTS = ("v.kuaishou.com", "v.kwai.com")
_VALID_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
}


def _is_domain_allowed(host: str, suffixes: Tuple[str, ...]) -> bool:
    host = (host or "").lower()
    if not host:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def _extract_url_from_text(text: str) -> str:
    matched = _URL_RE.search((text or "").strip())
    return matched.group(1) if matched else (text or "").strip()


def _headers_for_graphql(referer_url: str) -> Dict[str, str]:
    headers = dict(_DEFAULT_HEADERS)
    headers.update(
        {
            "content-type": "application/json",
            "origin": "https://www.kuaishou.com",
            "referer": referer_url,
        }
    )
    return headers


def _sanitize_input_url(url_or_text: str, session: requests.Session, timeout: int) -> str:
    clean = _extract_url_from_text(url_or_text)
    if not clean.startswith(("http://", "https://")):
        clean = f"https://{clean}"

    parsed = urlparse(clean)
    if not _is_domain_allowed(parsed.netloc, _PAGE_DOMAIN_SUFFIXES):
        raise ValueError(f"Unsupported Kuaishou domain: {parsed.netloc}")

    current = clean
    for _ in range(4):
        host = urlparse(current).netloc.lower()
        if host not in _SHORT_URL_HOSTS:
            break
        resp = session.get(current, allow_redirects=False, timeout=timeout)
        if resp.status_code not in (301, 302, 303, 307, 308):
            break
        location = resp.headers.get("Location")
        if not location:
            raise RuntimeError("Kuaishou short-link redirect failed: missing Location header")
        current = urljoin(current, location)

    final_host = urlparse(current).netloc.lower()
    if not _is_domain_allowed(final_host, _PAGE_DOMAIN_SUFFIXES):
        raise ValueError(f"Unexpected redirected domain: {final_host}")

    return current


def _extract_photo_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    path = parsed.path or ""
    parts = [part for part in path.split("/") if part]

    # Main format: /short-video/<photoId>
    if len(parts) >= 2 and parts[0] == "short-video":
        return parts[1]

    # Other common path styles
    for idx, part in enumerate(parts[:-1]):
        if part in {"photo", "video", "f"}:
            candidate = parts[idx + 1]
            if re.fullmatch(r"[A-Za-z0-9_-]{6,}", candidate):
                return candidate

    query = parse_qs(parsed.query or "")
    for key in ("photoId", "photo_id", "id"):
        values = query.get(key)
        if values and values[0]:
            return values[0]

    return None


def _post_graphql(
    session: requests.Session,
    operation_name: str,
    query: str,
    variables: Dict[str, Any],
    referer_url: str,
    timeout: int,
) -> Dict[str, Any]:
    response = session.post(
        GRAPHQL_URL,
        json={
            "operationName": operation_name,
            "query": query,
            "variables": variables,
        },
        headers=_headers_for_graphql(referer_url),
        timeout=timeout,
    )
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Kuaishou GraphQL returned non-JSON response (status={response.status_code})"
        ) from exc


def _resolve_candidate_from_detail(
    payload: Dict[str, Any],
    requested_photo_id: str,
) -> Optional[Tuple[str, str, str]]:
    detail = payload.get("data", {}).get("visionVideoDetail")
    if not isinstance(detail, dict):
        return None

    if detail.get("status") != 1:
        return None

    photo = detail.get("photo")
    if not isinstance(photo, dict):
        return None

    photo_url = str(photo.get("photoUrl") or "")
    if not photo_url:
        return None

    resolved_photo_id = str(photo.get("id") or requested_photo_id)
    caption = str(photo.get("caption") or "")
    return resolved_photo_id, photo_url, caption


def _resolve_candidate_from_reco(
    payload: Dict[str, Any],
    requested_photo_id: str,
) -> Optional[Tuple[str, str, str]]:
    reco = payload.get("data", {}).get("visionShortVideoReco")
    if not isinstance(reco, dict):
        return None

    feeds = reco.get("feeds") or []
    candidates: list[Tuple[str, str, str]] = []
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        photo = feed.get("photo")
        if not isinstance(photo, dict):
            continue
        resolved_photo_id = str(photo.get("id") or "")
        photo_url = str(photo.get("photoUrl") or "")
        caption = str(photo.get("caption") or "")
        if resolved_photo_id and photo_url:
            candidates.append((resolved_photo_id, photo_url, caption))

    if not candidates:
        return None

    exact = next((c for c in candidates if c[0] == requested_photo_id), None)
    return exact or candidates[0]


def _resolve_kuaishou_video(
    session: requests.Session,
    photo_id: str,
    referer_url: str,
    timeout: int,
) -> Optional[Tuple[str, str, str]]:
    try:
        detail_payload = _post_graphql(
            session=session,
            operation_name="visionVideoDetail",
            query=VISION_VIDEO_DETAIL_QUERY,
            variables={"photoId": photo_id, "page": "short-video"},
            referer_url=referer_url,
            timeout=min(timeout, 20),
        )
        detail_candidate = _resolve_candidate_from_detail(detail_payload, photo_id)
        if detail_candidate is not None:
            return detail_candidate
    except Exception as exc:
        logger.debug("[Kuaishou] visionVideoDetail failed: %s", exc)

    try:
        reco_payload = _post_graphql(
            session=session,
            operation_name="visionShortVideoReco",
            query=VISION_SHORT_VIDEO_RECO_QUERY,
            variables={"page": "short-video", "photoId": photo_id},
            referer_url=referer_url,
            timeout=timeout,
        )
        return _resolve_candidate_from_reco(reco_payload, photo_id)
    except Exception as exc:
        logger.debug("[Kuaishou] visionShortVideoReco failed: %s", exc)
        return None


def _infer_extension(video_url: str) -> str:
    suffix = os.path.splitext(urlparse(video_url).path)[1].lower()
    return suffix if suffix in _VALID_EXTENSIONS else ".mp4"


def _sanitize_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
    return cleaned or "video"


def _download_media_file(
    session: requests.Session,
    media_url: str,
    output_path: str,
    timeout: int,
) -> None:
    headers = dict(_DEFAULT_HEADERS)
    headers["Accept"] = "*/*"

    downloaded_size = 0
    with session.get(media_url, headers=headers, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded_size += len(chunk)

    if downloaded_size < 1024:
        raise RuntimeError("Kuaishou media download produced an empty/invalid file")


def _download_with_yt_dlp(url: str, output_dir: str) -> str:
    try:
        import yt_dlp
    except Exception as exc:
        raise RuntimeError(
            "GraphQL extraction failed and yt-dlp is unavailable for fallback"
        ) from exc

    outtmpl = os.path.join(output_dir, "kuaishou_%(id)s_%(timestamp)s.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "http_headers": dict(_DEFAULT_HEADERS),
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if isinstance(info, dict) and info.get("entries"):
            info = next((entry for entry in info["entries"] if entry), None)
        if not isinstance(info, dict):
            raise RuntimeError("yt-dlp did not return downloadable media info")
        expected_path = ydl.prepare_filename(info)

    if expected_path and os.path.exists(expected_path):
        return expected_path

    candidates = [
        os.path.join(output_dir, name)
        for name in os.listdir(output_dir)
        if name.startswith("kuaishou_")
    ]
    if not candidates:
        raise RuntimeError("yt-dlp completed but output file was not found")

    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def download_kuaishou_video(url: str, max_retries: int = 3, timeout: int = 30) -> str:
    temp_dir: Optional[str] = None
    last_error: Optional[Exception] = None

    for attempt in range(max(max_retries, 1)):
        try:
            logger.info(
                "[Kuaishou] download start: %s%s",
                url,
                f" (retry {attempt + 1}/{max_retries})" if attempt > 0 else "",
            )

            session = requests.Session()
            session.headers.update(_DEFAULT_HEADERS)

            clean_url = _sanitize_input_url(url, session, timeout)
            if temp_dir is None:
                temp_dir = tempfile.mkdtemp(prefix="kuaishou_video_")

            photo_id = _extract_photo_id(clean_url)
            if photo_id:
                candidate = _resolve_kuaishou_video(
                    session=session,
                    photo_id=photo_id,
                    referer_url=clean_url,
                    timeout=timeout,
                )
                if candidate is not None:
                    resolved_photo_id, media_url, _caption = candidate
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = _infer_extension(media_url)
                    filename = f"kuaishou_{_sanitize_token(resolved_photo_id)}_{timestamp}{ext}"
                    output_path = os.path.join(temp_dir, filename)
                    _download_media_file(session, media_url, output_path, timeout)
                    logger.info("[Kuaishou] download complete: %s", output_path)
                    return output_path

            logger.info("[Kuaishou] GraphQL resolution unavailable, falling back to yt-dlp")
            output_path = _download_with_yt_dlp(clean_url, temp_dir)
            logger.info("[Kuaishou] yt-dlp fallback complete: %s", output_path)
            return output_path
        except Exception as exc:
            last_error = exc
            logger.error(
                "[Kuaishou] download failed on attempt %d/%d: %s",
                attempt + 1,
                max(max_retries, 1),
                exc,
            )
            if attempt < max(max_retries, 1) - 1:
                time.sleep(min(6, (attempt + 1) * 2))

    raise RuntimeError(
        f"Kuaishou download failed after {max(max_retries, 1)} attempts: {last_error}"
    )
