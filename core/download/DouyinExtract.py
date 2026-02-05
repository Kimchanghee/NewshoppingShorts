import os
import re
import time
import json
from datetime import datetime, timedelta
import traceback
import tempfile
from urllib.parse import urlparse, urlunparse, unquote, urljoin, parse_qs
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
import html
import secrets
from typing import Dict, List, Optional, Tuple, Iterable
from utils.logging_config import get_logger
from core.api import ApiKeyManager

logger = get_logger(__name__)
from utils import DriverConfig, Tool, util
from core.video import VideoTool
from core.api import ApiController
# Note: DouyinExtract, TicktokExtract imports removed - circular reference
from core.video import VideoExtract
from caller import ui_controller

RENDER_DATA_SCRIPT_JSON = re.compile(
    r"<script[^>]*id=\"RENDER_DATA\"[^>]*type=\"application/json\"[^>]*>(.*?)</script>",
    re.S | re.I,
)
RENDER_DATA_ASSIGNMENT = re.compile(r"RENDER_DATA\s*=\s*\"(.*?)\"\s*;", re.S | re.I)
MODAL_ID_RE = re.compile(r"(?:^|[?&#])modal_id=(\d{6,})")

def douyin_extract_from_html(html_text: str) -> Tuple[Optional[str], Dict[str, str]]:
    meta = {}
    m_title = re.search(r"<title>(.*?)</title>", html_text, re.S | re.I)
    if m_title:
        meta["title"] = html.unescape(m_title.group(1)).strip()

    logger.debug("[Douyin] HTML 길이: %d", len(html_text))

    # 방법 1: RENDER_DATA JSON 스크립트
    m = RENDER_DATA_SCRIPT_JSON.search(html_text)
    data_json = None
    if m:
        payload = html.unescape(m.group(1))
        try:
            data_json = unquote(payload)
        except Exception as e:
            logger.debug("[Douyin] unquote 실패, payload 그대로 사용: %s", e)
            data_json = payload
    else:
        m2 = RENDER_DATA_ASSIGNMENT.search(html_text)
        if m2:
            data_json = unquote(m2.group(1))

    if data_json:
        logger.debug("[Douyin] RENDER_DATA 찾음, 길이: %d", len(data_json))
        try:
            data = json.loads(data_json)
            urls = VideoExtract._json_walk_urls(data)
            candidates = [u for u in urls if "douyin" in u or "aweme" in u]
            logger.debug("[Douyin] JSON에서 %d개 후보 URL 찾음", len(candidates))
            best = VideoExtract.pick_best_url(candidates, platform="douyin")
            if best:
                best = best.replace("playwm", "play")
                logger.debug("[Douyin] JSON에서 최적 URL 선택: %s...", best[:100])
                return best, meta
        except Exception as e:
            logger.error("[Douyin] JSON 파싱 오류: %s", str(e))
            ui_controller.write_error_log(e)

    # 방법 2: 비디오 ID 추출 후 API URL 생성
    video_ids = VideoExtract.extract_video_ids(html_text)
    logger.debug("[Douyin] 추출된 비디오 ID: %s", video_ids)
    
    for vid in video_ids:
        try:
            meta["video_id"] = vid
            play_urls = [
                f"https://www.iesdouyin.com/aweme/v1/play/?video_id={vid}&ratio=1080p&line=0&is_play_url=1&source=Web",
                f"https://www.iesdouyin.com/aweme/v1/play/?video_id={vid}&ratio=720p&line=0&is_play_url=1&source=Web",
                f"https://www.douyin.com/aweme/v1/play/?video_id={vid}&ratio=1080p&line=0",
            ]

            for play_url in play_urls:
                logger.debug("[Douyin] API URL 시도: %s", play_url)
                return play_url, meta

        except Exception as e:
            logger.error("[Douyin] 비디오 ID %s 처리 오류: %s", vid, str(e))
            ui_controller.write_error_log(e)
            continue

    # 방법 3: 직접 URL 추출
    direct_urls = VideoExtract.extract_direct_urls(html_text)
    logger.debug("[Douyin] 직접 추출된 URL: %d개", len(direct_urls))

    best_direct = Tool.pick_best_url(direct_urls, platform="douyin")
    if best_direct:
        best_direct = best_direct.replace("playwm", "play")
        logger.debug("[Douyin] 직접 URL에서 최적 선택: %s...", best_direct[:100])
        return best_direct, meta

    logger.warning("[Douyin] 모든 추출 방법 실패")
    return None, meta

def try_douyin_api_methods(item_id: str) -> List[str]:
    """다양한 Douyin API 엔드포인트 시도"""
    api_urls = []
    
    # 다양한 API 엔드포인트
    endpoints = [
        f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={item_id}",
        f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={item_id}",
        f"https://www.iesdouyin.com/aweme/v1/play/?video_id={item_id}&ratio=1080p&line=0&is_play_url=1&source=Web",
        f"https://www.iesdouyin.com/aweme/v1/play/?video_id={item_id}&ratio=720p&line=0&is_play_url=1&source=Web",
    ]
    
    for api_url in endpoints:
        try:
            logger.debug("[API] 시도 중: %s", api_url)
            headers = DriverConfig.get_random_headers(mobile=True)
            headers["Referer"] = "https://www.douyin.com/"

            with DriverConfig.http_open(api_url, headers=headers) as resp:
                if "application/json" in resp.headers.get("Content-Type", ""):
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))

                    # API 응답에서 URL 추출
                    urls = VideoExtract._json_walk_urls(data)
                    for url in urls:
                        if "play" in url or ".mp4" in url:
                            api_urls.append(url)
                else:
                    # 직접 비디오 파일인 경우
                    api_urls.append(api_url)

        except Exception as e:
            logger.error("[API] %s 실패: %s", api_url, str(e))
            ui_controller.write_error_log(e)
            continue
    
    return api_urls

def fetch_douyin_video(url: str) -> Tuple[Optional[str], Dict[str, str]]:
    logger.info("[Douyin] 다운로드 시작: %s", url)
    
    base_headers = DriverConfig.get_random_headers(mobile=True)
    base_headers["Referer"] = "https://www.douyin.com/"
    base_headers["Cookie"] = f"msToken={secrets.token_hex(16)}; ttwid={secrets.token_hex(32)}"

    meta = {}
    
    try:
        # 1단계: URL 리다이렉트 해결
        logger.debug("[Douyin] 1단계: URL 리다이렉트 해결")
        final_url = DriverConfig.resolve_redirect(url, headers=base_headers)
        logger.debug("[Douyin] 최종 URL: %s", final_url)
        
        # URL에서 비디오 ID 추출 시도
        url_video_ids = []
        id_patterns = [
            r'/video/(\d{10,})',
            r'[?&](?:aweme_id|video_id|item_id)=(\d+)',
            r'/(\d{19,})',  # 긴 숫자 ID
        ]
        
        for pattern in id_patterns:
            matches = re.findall(pattern, final_url)
            url_video_ids.extend(matches)
        
        logger.debug("[Douyin] URL에서 추출된 ID: %s", url_video_ids)

        # 2단계: HTML 페이지 가져오기
        logger.debug("[Douyin] 2단계: HTML 페이지 가져오기")
        try:
            with DriverConfig.http_open(final_url, headers=base_headers) as resp:
                html_text = resp.read().decode("utf-8", errors="ignore")
            logger.debug("[Douyin] HTML 크기: %d 바이트", len(html_text))
        except Exception as e:
            logger.error("[Douyin] HTML 가져오기 실패: %s", str(e))
            ui_controller.write_error_log(e)
            html_text = ""

        # 3단계: HTML에서 URL 추출
        logger.debug("[Douyin] 3단계: HTML에서 URL 추출")
        if html_text:
            direct_url, html_meta = douyin_extract_from_html(html_text)
            meta.update(html_meta)

            if direct_url:
                logger.debug("[Douyin] HTML에서 URL 추출 성공: %s...", direct_url[:100])
                return direct_url, meta

        # 4단계: API 방법들 시도
        logger.debug("[Douyin] 4단계: API 방법들 시도")
        all_ids = url_video_ids + [meta.get("video_id", "")]
        all_ids = [vid for vid in all_ids if vid and len(vid) >= 8]
        
        for video_id in all_ids:
            logger.debug("[Douyin] API 시도 - 비디오 ID: %s", video_id)
            api_urls = try_douyin_api_methods(video_id)

            if api_urls:
                best_api_url = Tool.pick_best_url(api_urls, platform="douyin")
                if best_api_url:
                    logger.debug("[Douyin] API에서 최적 URL 선택: %s...", best_api_url[:100])
                    return best_api_url, meta

        # 5단계: 대체 헤더로 재시도
        logger.debug("[Douyin] 5단계: 대체 헤더로 재시도")
        alt_headers = DriverConfig.get_random_headers(mobile=False)
        alt_headers.update({
            "Referer": "https://www.douyin.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        
        try:
            with DriverConfig.http_open(final_url, headers=alt_headers) as resp:
                alt_html = resp.read().decode("utf-8", errors="ignore")

            alt_direct, alt_meta = douyin_extract_from_html(alt_html)
            if alt_direct:
                logger.debug("[Douyin] 대체 헤더로 성공: %s...", alt_direct[:100])
                return alt_direct, {**meta, **alt_meta}

        except Exception as e:
            logger.error("[Douyin] 대체 헤더 시도 실패: %s", str(e))
            ui_controller.write_error_log(e)

        # 6단계: 마지막 수단 - 일반적인 패턴으로 URL 생성
        logger.debug("[Douyin] 6단계: 패턴 기반 URL 생성")
        if url_video_ids:
            fallback_urls = []
            for vid in url_video_ids[:3]:  # 최대 3개만
                fallback_urls.extend([
                    f"https://aweme.snssdk.com/aweme/v1/play/?video_id={vid}&line=0&ratio=1080p&media_type=4&vr_type=0&improve_bitrate=0&is_play_url=1&is_support_h265=0&source=PackSourceEnum_PUBLISH",
                    f"https://www.iesdouyin.com/aweme/v1/play/?video_id={vid}&ratio=1080p&line=0&watermark=1&source=Web",
                    f"https://www.douyin.com/aweme/v1/play/?video_id={vid}&line=0&file_id=0&quality=normal&tos=cn",
                ])
            
            for fallback_url in fallback_urls:
                logger.debug("[Douyin] 패턴 URL 시도: %s", fallback_url)
                return fallback_url, meta

    except Exception as e:
        logger.error("[Douyin] 전체 프로세스 오류: %s", str(e), exc_info=True)
        ui_controller.write_error_log(e)

    logger.warning("[Douyin] 모든 방법 실패")
    return None, meta


def download_tiktok_douyin_video(url: str, max_retries: int = 3) -> str:
        """두 번째 파일의 다운로드 로직 100% 적용 (재시도 로직 포함)"""
        temp_dir = None
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info("[다운로드] %s%s", url, f" (시도 {attempt + 1}/{max_retries})" if attempt > 0 else "")

                url = normalize_douyin_modal_url(url)

                if temp_dir is None:
                    temp_dir = tempfile.mkdtemp(prefix="tiktok_douyin_")

                # 품질 설정 (UI에서 선택 가능하게 할 수도 있음)
                target_height = None  # None = best quality
                prefer_small = False

                # 1. 플랫폼 감지 (두 번째 파일 로직 그대로)
                platform = detect_platform(url)
                logger.info("[다운로드] 플랫폼: %s", platform)

                # 2. 비디오 정보 추출 (두 번째 파일 로직 그대로)
                if platform == "tiktok":
                    direct_url, meta = _fetch_tiktok_video(url)
                    referer = "https://www.tiktok.com/"
                else:  # douyin
                    direct_url, meta = _fetch_douyin_video(url, target_height, prefer_small)
                    referer = "https://www.douyin.com/"

                if not direct_url:
                    raise RuntimeError("비디오 URL을 추출할 수 없습니다")

                # 3. 파일명 생성 (두 번째 파일 로직 그대로)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = _decide_filename(platform, meta, timestamp)
                local_path = os.path.join(temp_dir, filename)

                logger.info("[다운로드] 저장 위치: %s", local_path)
                logger.debug("[다운로드] 비디오 URL: %s...", direct_url[:100])

                # 4. 다운로드 실행 (두 번째 파일 로직 그대로)
                _download_file(
                    direct_url,
                    local_path,
                    referer=referer,
                    platform=platform,
                    target_height=target_height,
                    prefer_small=prefer_small
                )

                # 파일 확인
                if not os.path.exists(local_path) or os.path.getsize(local_path) < 1024:
                    # HLS/TS 파일 체크
                    ts_path = local_path[:-4] + ".ts" if local_path.endswith('.mp4') else local_path
                    if os.path.exists(ts_path):
                        local_path = ts_path
                        logger.debug("[다운로드] HLS/TS 파일 사용: %s", ts_path)
                    else:
                        raise Exception("다운로드 실패 또는 파일이 너무 작습니다")

                logger.info("[다운로드 완료] 크기: %d bytes", os.path.getsize(local_path))
                return local_path

            except Exception as e:
                last_error = e
                logger.error("[다운로드 오류] 시도 %d/%d: %s", attempt + 1, max_retries, str(e))
                ui_controller.write_error_log(e)

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2초, 4초 대기
                    logger.info("[다운로드] %d초 후 재시도...", wait_time)
                    time.sleep(wait_time)
                else:
                    # 마지막 시도 실패 시 임시 디렉토리 정리
                    if temp_dir and os.path.exists(temp_dir):
                        try:
                            import shutil
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            logger.debug("[다운로드] 임시 디렉토리 정리: %s", temp_dir)
                        except Exception as cleanup_err:
                            logger.warning("[다운로드] 임시 디렉토리 정리 실패: %s", cleanup_err)

        raise Exception(f"TikTok/Douyin 다운로드 실패 ({max_retries}회 시도): {str(last_error)}")
        
def detect_platform(url: str) -> str:
        """URL에서 플랫폼 감지"""
        host = urlparse(url).netloc.lower()
        if any(host.endswith(d) for d in ("tiktok.com", "v.tiktok.com", "m.tiktok.com", "www.tiktok.com")):
            return "tiktok"
        elif any(host.endswith(d) for d in ("douyin.com", "v.douyin.com", "www.iesdouyin.com", "www.douyin.com")):
            return "douyin"
        elif "tiktok" in host:
            return "tiktok"
        elif "douyin" in host:
            return "douyin"
        else:
            raise ValueError("TikTok 또는 Douyin URL이 아닙니다")
    
def _fetch_tiktok_video (url: str) -> Tuple[Optional[str], Dict[str, str]]:
        """두 번째 파일의 fetch_tiktok_video 그대로"""
        # 리다이렉트 해결
        final = DriverConfig._resolve_redirect(url, headers={"Referer": "https://www.tiktok.com/"})
        
        # HTML 가져오기
        with DriverConfig._http_open(final, headers={"Referer": "https://www.tiktok.com/"}) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")
        
        return _tiktok_extract_from_html(html_text)
    
def _tiktok_extract_from_html(html_text: str) -> Tuple[Optional[str], Dict[str, str]]:
    meta = {}
    m_title = re.search(r"<title>(.*?)</title>", html_text, re.S | re.I)
    if m_title:
        meta["title"] = html.unescape(m_title.group(1)).strip()

    # 1) SIGI_STATE JSON 우선
    SIGI_RE = re.compile(r"<script id=\"SIGI_STATE\"[^>]*>(.*?)</script>", re.S)
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
                if author: meta["author"] = str(author)
                if desc:   meta["desc"] = str(desc)
                if vid:    meta["id"]   = str(vid)

                video = item.get("video") or {}
                candidates: List[str] = []

                # bitrateInfo → PlayAddr.UrlList / urlList / Url
                for bi in (video.get("bitrateInfo") or []) or []:
                    play = bi.get("PlayAddr") or bi.get("playAddr") or {}
                    urls = play.get("UrlList") or play.get("urlList") or play.get("Url") or []
                    if isinstance(urls, list):
                        candidates.extend(urls)
                    elif isinstance(urls, str):
                        candidates.append(urls)

                # playAddr/downloadAddr (문자열 또는 dict)
                for k in ("playAddr", "downloadAddr"):
                    v = video.get(k)
                    if isinstance(v, dict):
                        urls = v.get("UrlList") or v.get("urlList") or v.get("Url") or []
                        if isinstance(urls, list):
                            candidates.extend(urls)
                        elif isinstance(urls, str):
                            candidates.append(urls)
                    elif isinstance(v, str):
                        candidates.append(v)

                # 썸네일/JS 같은 잡다수 제거
                candidates = _filter_videoish_urls(candidates)

                if candidates:
                    best = Tool.pick_best_url(candidates, platform="tiktok")
                    if best:
                        return best, meta
        except Exception as e:
            logger.debug("[TikTok] SIGI_STATE 파싱 실패: %s", e)

    # 2) <video> 태그 src 탐색 (SSR 케이스 보완)
    vid_srcs = re.findall(r"<video[^>]+src=[\"']([^\"']+)[\"']", html_text, re.I)
    vid_srcs = _filter_videoish_urls(vid_srcs)
    if vid_srcs:
        best = Tool.pick_best_url(vid_srcs, platform="tiktok")
        if best:
            return best, meta

    # 3) Fallback: 페이지 내 모든 URL 중 video-ish만
    all_urls = re.findall(r"https?://[^\"'<>\s]+", html_text)
    all_urls = _filter_videoish_urls(all_urls)
    if all_urls:
        best = Tool.pick_best_url(all_urls, platform="tiktok")
        if best:
            return best, meta

    return None, meta


def _fetch_douyin_video( url: str, target_height: Optional[int] = None, 
                            prefer_small: bool = False) -> Tuple[Optional[str], Dict[str, str]]:
    
        url = normalize_douyin_modal_url(url)
    
        """두 번째 파일의 fetch_douyin_video 그대로"""
        # 모바일 헤더 사용
        MOBILE_HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        
        base_headers = dict(MOBILE_HEADERS)
        base_headers["Referer"] = "https://www.douyin.com/"
        base_headers["Cookie"] = f"msToken={secrets.token_hex(16)}"
        
        # 리다이렉트 해결
        final = DriverConfig._resolve_redirect(url, headers=base_headers)
        
        # HTML 파싱 시도
        meta = {}
        html_text = ""
        try:
            with DriverConfig._http_open(final, headers=base_headers) as resp:
                html_text = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error("[Douyin] HTML 가져오기 오류: %s", str(e)[:100])
        
        try:
            from urllib.parse import urlparse, urljoin
            p = urlparse(final)
            if "/search" in p.path or "type=general" in final:
                ids = re.findall(r'href=[\'"]/(?:video)/(\d+)[\'"]', html_text) \
                    + re.findall(r'https?://www\.douyin\.com/video/(\d+)', html_text)

                if ids:
                    video_page = f"https://www.douyin.com/video/{ids[0]}"
                    with DriverConfig._http_open(video_page, headers=base_headers) as resp2:
                        html_text = resp2.read().decode("utf-8", errors="ignore")
                    final = video_page
                else:
                    raise RuntimeError("검색 결과에서 동영상 링크를 찾을 수 없습니다. 개별 동영상 URL을 주세요.")
        except RuntimeError:
            raise  # RuntimeError는 상위로 전달
        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error("[Douyin] 검색 페이지 처리 오류: %s", str(e)[:100])

        direct, meta = _douyin_extract_from_html(html_text, target_height, prefer_small)
        if direct:
            return direct, meta
        
        # 비디오 ID 추출
        item_id = _extract_douyin_id_from_url(final)
        
        if not item_id:
            m = re.search(r'(?:aweme_id|itemId|item_id)\D(\d{8,22})', html_text)
            if m:
                item_id = m.group(1)
                
        # API 시도
        if item_id:
            try:
                api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={item_id}"
                with DriverConfig._http_open(api_url, headers={"Referer": "https://www.iesdouyin.com/"}) as r:
                    data = json.loads(r.read().decode("utf-8", errors="ignore"))
                
                item = (data.get("item_list") or [None])[0] or {}
                author = item.get("author") or {}
                video = item.get("video") or {}
                
                meta.update({
                    "author": author.get("nickname") or author.get("short_id") or "",
                    "desc": item.get("desc") or "",
                    "id": item.get("aweme_id") or item_id,
                })
                
                urls = (video.get("play_addr") or {}).get("url_list") or []
                
                if not urls:
                    uri = (video.get("play_addr") or {}).get("uri") or video.get("vid")
                    if uri:
                        ratio = _quality_to_ratio(target_height)
                        line = '1' if prefer_small else '0'
                        urls = [
                            f"https://www.iesdouyin.com/aweme/v1/play/?video_id={uri}&ratio={ratio}&line={line}&is_play_url=1&source=Web"
                        ]
                
                direct = Tool.pick_best_url(urls, platform="douyin")
                if direct:
                    direct = direct.replace("playwm", "play")
                    if "aweme/v1/play" in direct or "ratio=" in direct:
                        direct = _rewrite_ratio_in_url(direct, target_height, prefer_small)
                    return direct, meta
            except Exception as e:
                ui_controller.write_error_log(e)
                logger.error("[Douyin] API 호출 오류: %s", str(e)[:100])

        return None, meta
    
def _douyin_extract_from_html(html_text: str, target_height: Optional[int] = None, 
                                  prefer_small: bool = False) -> Tuple[Optional[str], Dict[str, str]]:
        """두 번째 파일의 douyin_extract_from_html 그대로"""
        meta = {}
        
        # Title 추출
        m_title = re.search(r"<title>(.*?)</title>", html_text, re.S | re.I)
        if m_title:
            meta["title"] = html.unescape(m_title.group(1)).strip()
        
        # RENDER_DATA 추출
        RENDER_DATA_SCRIPT_JSON = re.compile(
            r"<script[^>]*id=\"RENDER_DATA\"[^>]*type=\"application/json\"[^>]*>(.*?)</script>",
            re.S | re.I,
        )
        RENDER_DATA_ASSIGNMENT = re.compile(r"RENDER_DATA\s*=\s*\"(.*?)\"\s*;", re.S | re.I)
        
        m = RENDER_DATA_SCRIPT_JSON.search(html_text)
        data_json = None
        
        if m:
            payload = html.unescape(m.group(1))
            try:
                data_json = unquote(payload)
            except Exception as e:
                logger.debug("[Douyin] _douyin_extract_from_html unquote 실패: %s", e)
                data_json = payload
        else:
            m2 = RENDER_DATA_ASSIGNMENT.search(html_text)
            if m2:
                data_json = unquote(m2.group(1))
        
        if data_json:
            try:
                data = json.loads(data_json)
                urls = _json_walk_urls(data)
                candidates = [u for u in urls if "douyin" in u]
                best = Tool.pick_best_url(candidates, platform="douyin")
                if best:
                    best = best.replace("playwm", "play")
                    if "aweme/v1/play" in best or "ratio=" in best:
                        best = _rewrite_ratio_in_url(best, target_height, prefer_small)
                    return best, meta
            except Exception as e:
                logger.debug("[Douyin] HTML 파싱 중 오류: %s", str(e)[:80])
        
        # video_id 추출 시도
        m_vid = re.search(r'"play_addr"\s*:\s*\{[^}]*"uri"\s*:\s*"([a-zA-Z0-9_\-]{8,})"', html_text)
        if not m_vid:
            m_vid = re.search(r'"vid"\s*:\s*"([a-zA-Z0-9_\-]{8,})"', html_text)
        
        if m_vid:
            vid = m_vid.group(1)
            meta["video_id"] = vid
            ratio = _quality_to_ratio(target_height)
            line = '1' if prefer_small else '0'
            play_url = (
                f"https://www.iesdouyin.com/aweme/v1/play/?video_id="
                f"{vid}&ratio={ratio}&line={line}&is_play_url=1&source=Web"
            )
            return play_url, meta
        
        # Fallback: HTML에서 URL 찾기
        candidates = re.findall(r"https?://[^\"'<>\s]+", html_text)
        url_ = Tool.pick_best_url(candidates, platform="douyin")
        if url_:
            url_ = url_.replace("playwm", "play")
        return url_, meta

def _download_file( url: str, dest_path: str, referer: str, platform: str = "",
                      target_height: Optional[int] = None, prefer_small: bool = False) -> None:
        """두 번째 파일의 download_file 그대로 (HLS 지원 포함)"""
        # 헤더 설정
        if platform == "douyin":
            MOBILE_HEADERS = {
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
            headers = dict(MOBILE_HEADERS)
        else:
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
            headers = dict(DEFAULT_HEADERS)
        
        headers.update({
            "Referer": referer or "",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        })
        
        # HLS 체크
        if platform == "douyin" and _is_m3u8_like(url):
            ts_path = dest_path
            if ts_path.lower().endswith(".mp4"):
                ts_path = dest_path[:-4] + ".ts"
            _download_hls_m3u8(url, ts_path, headers, target_height, prefer_small)
            return
        
        # 일반 다운로드 시도
        logger.info("[다운로드] HTTP 스트림 다운로드 시작...")
        size, ctype, total = _stream_download(url, dest_path, headers)
        logger.info("[다운로드] 완료: %.1fKB (type: %s)", size / 1024 if size else 0, ctype or "unknown")
        
        if platform == "douyin" and _is_m3u8_like(url, ctype):
            try:
                os.remove(dest_path)
            except OSError:
                pass
            ts_path = dest_path[:-4] + ".ts" if dest_path.lower().endswith(".mp4") else dest_path + ".ts"
            _download_hls_m3u8(url, ts_path, headers, target_height, prefer_small)
            return
        
        suspicious = ("video" not in ctype and "application/octet-stream" not in ctype) or size < 200_000
        
        if not suspicious:
            return
        
        # 리다이렉트 재시도
        try:
            final = DriverConfig._resolve_redirect(url, headers=headers)
        except Exception as e:
            logger.debug("[다운로드] 리다이렉트 해결 실패, 원본 URL 사용: %s", e)
            final = url
        
        if final != url:
            try:
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
                size2, ctype2, _ = _stream_download(final, dest_path, headers)
                if "video" in ctype2 or size2 >= 200_000:
                    return
            except Exception as e:
                logger.debug("[다운로드] 리다이렉트된 URL 다운로드 실패: %s", e)
        
        # Douyin playwm/play 토글
        if platform == "douyin":
            alt = url.replace("playwm", "play") if "playwm" in url else url.replace("play/", "playwm/")
            if alt != url:
                try:
                    try:
                        os.remove(dest_path)
                    except OSError:
                        pass
                    size3, ctype3, _ = _stream_download(alt, dest_path, headers)
                    if _is_m3u8_like(alt, ctype3):
                        try:
                            os.remove(dest_path)
                        except OSError:
                            pass
                        ts_path = dest_path[:-4] + ".ts" if dest_path.lower().endswith(".mp4") else dest_path + ".ts"
                        _download_hls_m3u8(alt, ts_path, headers, target_height, prefer_small)
                        return
                    if "video" in ctype3 or size3 >= 200_000:
                        return
                except Exception as e:
                    logger.debug("[다운로드] playwm/play 토글 다운로드 실패: %s", e)
        
        raise RuntimeError("Downloaded content does not look like a valid video")
    
def _decide_filename(platform: str, meta: Dict[str, str], timestamp: str) -> str:
        parts = []
        
        if meta.get("author"):
            parts.append(Tool.sanitize_filename(meta["author"]))
        if meta.get("id"):
            parts.append(meta["id"])
        elif meta.get("title"):
            parts.append(Tool.sanitize_filename(meta["title"]))
        elif meta.get("desc"):
            parts.append(Tool.sanitize_filename(meta["desc"]))
        
        base = "_".join(p for p in parts if p)
        if not base:
            base = platform + "_video"
        
        return f"{base}_{timestamp}.mp4"
    
    

def _download_hls_m3u8(m3u8_url: str, dest_path: str, headers: Dict[str, str],
                           target_height: Optional[int] = None, prefer_small: bool = False) -> None:
        """두 번째 파일의 download_hls_m3u8 그대로"""
        # M3U8 플레이리스트 가져오기
        req = Request(m3u8_url, headers=headers)
        with urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
        
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        
        # 마스터 플레이리스트 체크
        if any(ln.startswith("#EXT-X-STREAM-INF") for ln in lines):
            variants = []
            variants_wh = []
            i = 0
            while i < len(lines):
                if lines[i].startswith("#EXT-X-STREAM-INF"):
                    info = lines[i]
                    bw_match = re.search(r"BANDWIDTH=(\d+)", info)
                    bw = int(bw_match.group(1)) if bw_match else 0
                    res_match = re.search(r"RESOLUTION=(\d+)x(\d+)", info)
                    height = int(res_match.group(2)) if res_match else 0
                    
                    j = i + 1
                    while j < len(lines) and lines[j].startswith("#"):
                        j += 1
                    if j < len(lines):
                        uri = urljoin(m3u8_url, lines[j])
                        variants.append((bw, uri))
                        variants_wh.append((height, bw, uri))
                    i = j
                else:
                    i += 1
            
            if not variants:
                raise RuntimeError("Invalid HLS master playlist")
            
            # 품질 선택
            if target_height:
                eligible = [v for v in variants_wh if v[0] and v[0] <= target_height]
                if eligible:
                    if prefer_small:
                        eligible.sort(key=lambda x: (x[0], x[1]))
                        chosen = eligible[0][2]
                    else:
                        eligible.sort(key=lambda x: (x[0], x[1]), reverse=True)
                        chosen = eligible[0][2]
                else:
                    variants_wh.sort(key=lambda x: (x[0], x[1]), reverse=True)
                    chosen = variants_wh[-1][2] if variants_wh else variants[0][1]
            else:
                if prefer_small:
                    variants.sort(key=lambda x: x[0])
                    chosen = variants[0][1]
                else:
                    variants.sort(key=lambda x: x[0], reverse=True)
                    chosen = variants[0][1]
            
            return _download_hls_m3u8(chosen, dest_path, headers, None, False)
        
        # 미디어 플레이리스트: 세그먼트 다운로드
        segments = [urljoin(m3u8_url, ln) for ln in lines if not ln.startswith("#")]
        
        if not segments:
            raise RuntimeError("No segments found in HLS playlist")
        
        total = len(segments)
        downloaded = 0
        
        with open(dest_path, "wb") as out:
            for idx, seg in enumerate(segments, 1):
                req_s = Request(seg, headers=headers)
                with urlopen(req_s, timeout=60) as rseg:
                    while True:
                        chunk = rseg.read(1024 * 256)
                        if not chunk:
                            break
                        out.write(chunk)
                downloaded += 1
                logger.debug("  HLS %d/%d segments", idx, total)

        logger.debug("  HLS %d/%d segments complete", total, total)
        
        
def _quality_to_ratio(target_height: Optional[int]) -> str:
        if target_height is None:
            return "1080p"
        if target_height >= 1080:
            return "1080p"
        if target_height >= 720:
            return "720p"
        if target_height >= 480:
            return "480p"
        return "360p"
    
def _extract_douyin_id_from_url(url: str) -> Optional[str]:
        patterns = [
            r"/video/(\d+)",
            r"[?&](?:aweme_id|item_ids)=(\d+)",
            r"/share/video/(\d+)"
        ]
        for pattern in patterns:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None

def _rewrite_ratio_in_url( url: str, target_height: Optional[int], prefer_small: bool = False) -> str:
        ratio = _quality_to_ratio(target_height)
        if "ratio=" in url:
            url = re.sub(r"ratio=\d+p", f"ratio={ratio}", url)
        else:
            sep = '&' if ('?' in url) else '?'
            url = f"{url}{sep}ratio={ratio}"
        
        if "line=" in url:
            url = re.sub(r"line=\d+", f"line={'1' if prefer_small else '0'}", url)
        else:
            sep = '&' if ('?' in url) else '?'
            url = f"{url}{sep}line={'1' if prefer_small else '0'}"
        return url
    
    
def _json_walk_urls(obj) -> List[str]:
        urls = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                urls.extend(_json_walk_urls(v))
        elif isinstance(obj, list):
            for v in obj:
                urls.extend(_json_walk_urls(v))
        elif isinstance(obj, str):
            if obj.startswith("http"):
                urls.append(obj)
        return urls
    
    
def _stream_download(to_url: str, dest_path: str, headers: Dict[str, str]) -> Tuple[int, str, Optional[int]]:
        req = Request(to_url, headers=headers)
        with urlopen(req, timeout=60) as resp, open(dest_path, "wb") as f:
            ct = resp.headers.get("Content-Type") or ""
            total = resp.headers.get("Content-Length")
            total_i = int(total) if total and total.isdigit() else None
            downloaded = 0
            last_print = time.time()
            chunk = 1024 * 256
            
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                f.write(buf)
                downloaded += len(buf)
                now = time.time()
                if now - last_print >= 0.5:
                    if total_i and total_i > 0:
                        pct = downloaded / total_i * 100
                        logger.debug("  %s/%s (%.1f%%)", _human_size(downloaded), _human_size(total_i), pct)
                    else:
                        logger.debug("  %s downloaded", _human_size(downloaded))
                    last_print = now

            if total_i and total_i > 0:
                logger.debug("  %s/%s (100.0%%)", _human_size(downloaded), _human_size(total_i))
            else:
                logger.debug("  %s downloaded", _human_size(downloaded))
            
            return downloaded, ct.lower(), total_i
        
        
def _is_m3u8_like( url: str, content_type: str = "") -> bool:
        url_l = url.lower()
        ctype_l = (content_type or "").lower()
        return (".m3u8" in url_l) or ("mpegurl" in ctype_l) or ("x-mpegurl" in ctype_l)
    
def _human_size( n: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(n)
        for u in units:
            if size < 1024.0:
                return f"{size:.1f}{u}"
            size /= 1024.0
        return f"{size:.1f}PB"
    
def _filter_videoish_urls(urls: List[str]) -> List[str]:
    if not urls:
        return []
    bad_ext = (".js", ".css", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp", ".woff", ".woff2", ".ttf", ".map")
    video_hosts = (
        "tiktokcdn.com", "tiktokcdn-us.com", "tiktokcdn-eu.com",
        "bytecdn", "byteoversea", "bytegoofy", "v16-webapp", "v19-webapp"
    )
    out = []
    for u in urls:
        ul = u.lower()
        if any(ul.endswith(ext) for ext in bad_ext):
            continue
        if any(x in ul for x in (".m3u8", ".mp4", "/play/", "/playwm/", "/video/tos")):
            out.append(u)
            continue
        # host 기반으로 추가 허용 (tiktok 동영상 CDN일 확률 높음)
        if any(h in ul for h in video_hosts):
            out.append(u)
    # 중복 제거, 너무 짧은건 제외
    seen = set()
    out2 = []
    for u in out:
        if len(u) > 12 and u not in seen:
            out2.append(u)
            seen.add(u)
    return out2

def normalize_douyin_modal_url(url: str) -> str:
    """
    Douyin의 jingxuan 검색/스포츠 등 컬렉션 페이지로 들어오는 URL에서
    modal_id만 뽑아 /jingxuan?modal_id={id} 형태로 표준화한다.
    해당 케이스가 아니면 원본 URL을 그대로 반환한다.
    """
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower()
        if "douyin.com" not in host:
            return url  # Douyin이 아니면 건드리지 않음

        # 검색/컬렉션 계열 경로 여부 (jingxuan/.../search 등)
        path = p.path or ""
        looks_like_collection = (
            "/jingxuan/" in path or
            "/search" in path or
            path.startswith("/jingxuan")
        )

        # modal_id 추출 (query 우선, 없으면 전체 문자열에서 백업 정규식)
        qs = parse_qs(p.query or "")
        modal_id = (qs.get("modal_id") or [None])[0]
        if not modal_id:
            m = MODAL_ID_RE.search(url)
            modal_id = m.group(1) if m else None

        if looks_like_collection and modal_id:
            # https://www.douyin.com/jingxuan?modal_id={id} 로 표준화
            normalized = urlunparse((p.scheme or "https", host, "/jingxuan", "", f"modal_id={modal_id}", ""))
            return normalized

        return url
    except Exception as e:
        # 문제가 생기면 원본 유지
        logger.debug("[Douyin] normalize_douyin_modal_url 오류, 원본 URL 유지: %s", e)
        return url