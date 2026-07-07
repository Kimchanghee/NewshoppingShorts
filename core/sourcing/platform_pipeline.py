# -*- coding: utf-8 -*-
"""
3플랫폼(도우인/콰이쇼우/샤오홍슈) 소싱 오케스트레이터 — UI와 풀자동화 큐가 공유.

쿠팡 링크 → 상품명 → 파트너스 딥링크 → 키워드(Gemini→룰) → 3채널 순차 검색·다운로드
→ 소스 중복 차단 → 재편집(9:16·워터마크 크롭·속도 변형·훅) 까지 담당한다.
링크트리 발행/업로드는 호출자(UI 패널·큐 스크립트)가 기존 경로로 수행한다.

반환 report 형식은 기존 SourcingPipeline.get_report()와 호환되는 키를 사용:
  ok, error, product_info{name}, deep_link, keywords, hit, final_video, render_integrity
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[str, str, float], None]]

# 재편집 기본값: 살짝 빠르게(Content ID 완화) — 원본 오디오 유지.
DEFAULT_REEDIT_OPTIONS = {"speed": 1.03, "mirror": False, "mute": False, "bgm_path": None}

# 산출물 보존 기간(일) — 지난 파일은 다음 실행 때 정리.
OUTPUT_RETENTION_DAYS = 7


def default_output_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".ssmaker", "platform_video_output")


def _emit(progress: ProgressCb, step: str, msg: str, pct: float) -> None:
    if progress is None:
        return
    try:
        progress(step, msg, pct)
    except Exception:
        pass


def cleanup_old_outputs(output_dir: str, retention_days: int = OUTPUT_RETENTION_DAYS) -> int:
    """보존 기간이 지난 산출물 정리(용량 누적 방지). 삭제 개수 반환."""
    removed = 0
    try:
        cutoff = time.time() - retention_days * 86400
        for name in os.listdir(output_dir):
            path = os.path.join(output_dir, name)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                continue
    except OSError:
        pass
    if removed:
        logger.info("[PlatformPipeline] 오래된 산출물 %d개 정리", removed)
    return removed


def build_queries(product_name: str, keywords: Dict[str, str]) -> List[str]:
    """검색 쿼리 목록(중국어 우선 → 한국어 상품명 → 영어)."""
    cn = str((keywords or {}).get("chinese", "") or "").strip()
    en = str((keywords or {}).get("english", "") or "").strip()
    out: List[str] = []
    for q in (cn, str(product_name or "").strip(), en):
        if q and q not in out:
            out.append(q)
    return out


async def _convert_keywords(product_name: str, gemini_client: Any) -> Dict[str, str]:
    """Gemini 우선, 실패/누락 시 rule-based로 보강(기존 coupang 파이프라인과 동일 정책)."""
    from core.sourcing.keyword_converter import (
        convert_keywords_gemini,
        convert_keywords_rule_based,
    )
    kw: Dict[str, str] = {}
    try:
        kw = dict(await convert_keywords_gemini(product_name, gemini_client) or {})
    except Exception as e:
        logger.warning("[PlatformPipeline] Gemini 키워드 변환 실패, 룰 폴백: %s", e)
    if not str(kw.get("chinese", "") or "").strip() or not str(kw.get("english", "") or "").strip():
        rule = convert_keywords_rule_based(product_name) or {}
        if not str(kw.get("chinese", "") or "").strip() and rule.get("chinese"):
            kw["chinese"] = rule["chinese"]
        if not str(kw.get("english", "") or "").strip() and rule.get("english"):
            kw["english"] = rule["english"]
    return kw


def _resolve_purchase_link(coupang_url: str) -> Dict[str, str]:
    """구매 링크 결정 — 수동 링크가 항상 최우선(파트너스 API 키는 선택 사항).

    우선순위:
      1) 사용자가 설정에 넣어둔 수동 파트너스/상품 링크 (API 키·매출 조건 불필요)
      2) 파트너스 API 딥링크 (키가 연결된 경우에만, 조용히 시도)
      3) 쿠팡 원본 링크
    """
    manual = ""
    try:
        from managers.settings_manager import get_settings_manager
        manual = str(get_settings_manager().get_youtube_comment_manual_product_link() or "").strip()
    except Exception:
        manual = ""
    if manual:
        return {"purchase_url": manual, "deep_link": manual, "source": "manual"}

    try:
        from managers.coupang_manager import get_coupang_manager
        cm = get_coupang_manager()
        if cm.is_connected():
            link = str(cm.generate_deep_link(coupang_url) or "").strip()
            if link:
                return {"purchase_url": link, "deep_link": link, "source": "api"}
    except Exception as e:
        logger.debug("[PlatformPipeline] API 딥링크 생략: %s", e)
    return {"purchase_url": coupang_url, "deep_link": "", "source": "original"}


async def run_platform_sourcing(
    coupang_url: str,
    output_dir: Optional[str] = None,
    progress: ProgressCb = None,
    platforms: Optional[List[str]] = None,
    browser: Any = None,
    gemini_client: Any = None,
    product_name_hint: str = "",
    reedit_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """쿠팡 링크 → 3플랫폼 소싱 + 재편집. 결과 report dict 반환(업로드는 호출자 몫)."""
    from core.sourcing.coupang_scraper import scrape_product
    from core.sourcing.platform_shorts_searcher import (
        search_platform_shorts,
        start_browser,
    )
    from core.video.reeditor import reedit

    out_dir = output_dir or default_output_dir()
    os.makedirs(out_dir, exist_ok=True)
    cleanup_old_outputs(out_dir)

    report: Dict[str, Any] = {
        "ok": False, "error": "", "sourcing_method": "platform_video",
        "coupang_url": coupang_url,
        "product_info": {}, "deep_link": "", "keywords": {},
        "queries": [], "hit": None, "final_video": "",
        "render_integrity": {"ok": False, "source": "platform_video"},
    }

    own_browser = False
    if browser is None:
        try:
            browser = await start_browser()
            own_browser = True
        except Exception as e:
            report["error"] = f"브라우저를 시작할 수 없습니다: {e}"
            _emit(progress, "product_analysis", report["error"], 0.0)
            return report

    try:
        # ── 1) 쿠팡 상품 분석 ──
        _emit(progress, "product_analysis", "쿠팡 상품 분석 중...", 0.0)
        product: Dict[str, Any] = {}
        try:
            product = await scrape_product(browser, coupang_url) or {}
        except Exception as e:
            logger.warning("[PlatformPipeline] 상품 스크랩 실패: %s", e)
        product_name = str(product.get("name") or product.get("title") or "").strip()
        if not product_name:
            product_name = str(product_name_hint or "").strip()
            if product_name:
                product = dict(product or {})
                product["name"] = product_name
        if not product_name:
            report["error"] = "쿠팡 상품명을 가져오지 못했어요. 링크를 확인해 주세요."
            _emit(progress, "product_analysis", report["error"], 0.0)
            return report
        report["product_info"] = product
        _emit(progress, "product_analysis", f"상품: {product_name[:40]}", 1.0)

        # ── 2) 구매 링크 결정(수동 링크 최우선 — API 키 불필요) ──
        _emit(progress, "deep_link", "구매 링크 확인 중...", 0.0)
        link_info = _resolve_purchase_link(coupang_url)
        report["deep_link"] = link_info["deep_link"]
        report["purchase_url"] = link_info["purchase_url"]
        report["purchase_link_source"] = link_info["source"]
        _label = {"manual": "수동 링크 사용", "api": "API 딥링크 생성", "original": "원본 링크 사용"}
        _emit(progress, "deep_link", _label.get(link_info["source"], "링크 준비 완료"), 1.0)

        # ── 3) 키워드 변환(Gemini→룰) ──
        _emit(progress, "keyword_convert", "키워드 변환 중...", 0.0)
        keywords = await _convert_keywords(product_name, gemini_client)
        queries = build_queries(product_name, keywords)
        report["keywords"], report["queries"] = keywords, queries
        _emit(progress, "keyword_convert",
              f"검색어: {' / '.join(q[:14] for q in queries[:3])}", 1.0)

        # ── 4) 3채널 검색·다운로드(소스 중복 스킵) ──
        _emit(progress, "overseas_search", f"'{product_name[:20]}' 로 3채널 검색 중...", 0.1)
        skip_ids = set()
        try:
            from managers.uploaded_registry import get_uploaded_registry
            skip_ids = get_uploaded_registry().used_source_ids()
        except Exception:
            pass
        hit = await search_platform_shorts(
            browser, queries, out_dir, platforms=platforms, skip_source_ids=skip_ids
        )
        if not hit:
            report["error"] = "세 채널 모두에서 쓸 수 있는 영상을 찾지 못했어요. (로그인 필요/안티봇/중복 가능)"
            _emit(progress, "overseas_search", report["error"], 0.0)
            return report
        report["hit"] = hit
        _emit(progress, "overseas_search", f"{hit['platform']}에서 영상 확보", 1.0)
        _emit(progress, "video_download", f"{hit['platform']} 영상 {hit.get('size_mb', 0)}MB", 1.0)

        # ── 5) 재편집(변형 저작물화) ──
        _emit(progress, "video_create", "재편집 중(워터마크 크롭·9:16·속도 변형)...", 0.1)
        opts = {**DEFAULT_REEDIT_OPTIONS, **(reedit_options or {})}
        edited = os.path.join(
            out_dir, f"edited_{hit['platform']}_{uuid.uuid4().hex[:8]}.mp4"
        )
        ok = await asyncio.to_thread(
            reedit, hit["video_file"], edited,
            hook_text=product_name,
            speed=float(opts.get("speed") or 1.0),
            mirror=bool(opts.get("mirror")),
            mute=bool(opts.get("mute")),
            bgm_path=opts.get("bgm_path"),
        )
        if not ok or not os.path.exists(edited):
            report["error"] = "재편집에 실패했어요."
            _emit(progress, "video_create", report["error"], 0.0)
            return report
        report["final_video"] = edited
        report["render_integrity"] = {"ok": True, "source": "platform_video",
                                      "platform": hit["platform"], "via": hit.get("via", "")}
        _emit(progress, "video_create", "재편집 완료", 1.0)

        # ── 6) 소스 사용 기록(재사용 차단) + 원본 정리 ──
        try:
            from managers.uploaded_registry import get_uploaded_registry
            get_uploaded_registry().record_source(
                str(hit.get("video_url") or ""),
                meta={"platform": hit["platform"], "coupang_url": coupang_url,
                      "product_name": product_name[:80]},
            )
        except Exception as e:
            logger.debug("[PlatformPipeline] 소스 기록 실패: %s", e)
        try:
            os.remove(hit["video_file"])
        except OSError:
            pass

        report["ok"] = True
        return report
    finally:
        if own_browser:
            try:
                await browser.stop()
            except Exception:
                pass
