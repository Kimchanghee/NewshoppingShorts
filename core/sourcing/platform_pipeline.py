# -*- coding: utf-8 -*-
"""
3플랫폼(샤오홍슈/도우인/콰이쇼우) 소싱 오케스트레이터 — UI와 풀자동화 큐가 공유.

쿠팡 링크 → 상품명 → 파트너스 딥링크 → 중국어 키워드(Gemini→룰) → 3채널 검색·다운로드
→ 소스 중복 차단 → 재편집(9:16·워터마크 크롭·속도 변형·훅) 까지 담당한다.
링크트리 발행/업로드는 호출자(UI 패널·큐 스크립트)가 기존 경로로 수행한다.

반환 report 형식은 기존 SourcingPipeline.get_report()와 호환되는 키를 사용:
  ok, error, product_info{name}, deep_link, keywords, hit, final_video, render_integrity
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin

from utils.logging_config import get_logger

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[str, str, float], None]]
BeforeCommitCb = Optional[Callable[[str], None]]


def _platform_relevance_threshold(
    configured_score: float,
    *,
    required_score: Optional[float] = None,
) -> float:
    """Threshold for a related product-family clip, not an identical listing.

    Marketplace product matching can remain at 90%, but a short-form source
    only needs to demonstrate the same product category. Category guards and
    explicit attribute contradictions are still evaluated separately.
    """
    if required_score is not None:
        try:
            required = float(required_score)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "required relevance score must be finite and within 0.70..1.0"
            ) from exc
        if not math.isfinite(required) or not 0.70 <= required <= 1.0:
            raise ValueError(
                "required relevance score must be finite and within 0.70..1.0"
            )
        return required
    try:
        configured = float(configured_score)
    except (TypeError, ValueError):
        configured = 0.75
    return max(0.70, min(0.75, configured))

# 재편집 기본값: 쇼츠 템포에 맞춰 살짝 빠르게 — 원본 오디오 유지.
DEFAULT_REEDIT_OPTIONS = {"speed": 1.03, "mirror": False, "mute": False, "bgm_path": None}

# 산출물 보존 기간(일) — 지난 파일은 다음 실행 때 정리.
OUTPUT_RETENTION_DAYS = 7
FAILURE_REPORT_RETENTION_DAYS = 30
_BLOCKED_DELIVERY_STAGES = ["video_edit", "youtube_upload", "linktree_publish"]


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
                report_cutoff = time.time() - FAILURE_REPORT_RETENTION_DAYS * 86400
                effective_cutoff = (
                    report_cutoff if name.startswith("report_platform_") else cutoff
                )
                if os.path.isfile(path) and os.path.getmtime(path) < effective_cutoff:
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
    """중국 플랫폼용 쿼리(중국어 정확 번역을 항상 첫 검색어로)."""
    cn = str((keywords or {}).get("chinese", "") or "").strip()
    en = str((keywords or {}).get("english", "") or "").strip()
    if cn:
        from core.sourcing.product_searcher import _preferred_chinese_query_variants

        base_queries = list(_preferred_chinese_query_variants(cn, en))
        # Google-indexed short-form results use seller vocabulary that is often
        # more specific than the literal Korean title translation.  Keep the
        # exact translation first, then try the live-verified product-family
        # aliases before broad fallbacks such as ``水枪``.
        seller_aliases: List[str] = []
        if "水枪" in cn and "喷泉" in cn:
            seller_aliases.extend(["抽拉式 喷泉 水枪", "旋转喷泉水枪 玩具"])
        if "水枪" in cn and "海豚" in cn:
            seller_aliases.append("海豚水枪玩具")
        if "水枪" in cn and "鲨鱼" in cn:
            seller_aliases.append("鲨鱼水枪玩具")
        if "水枪" in cn and "恐龙" in cn:
            seller_aliases.append("恐龙抽拉式水枪")
        if "回旋球" in cn or "飞行回旋球" in cn:
            seller_aliases.append("感应悬浮回旋球 玩具")

        queries = list(dict.fromkeys(
            base_queries[:1] + seller_aliases + base_queries[1:]
        ))
        # Product-video discovery does not require an identical seller/model.
        # Exact translated intent remains first, then add the Chinese product
        # family chunks so a brand or generation suffix cannot collapse recall
        # to one stale result (e.g. "... Ditwo" -> "电动打奶器").
        for chunk in re.findall(r"[\u3400-\u9fff]{2,12}", cn):
            if chunk not in queries:
                queries.append(chunk)
        return queries[:7]
    if en:
        return [en]
    fallback = str(product_name or "").strip()
    if fallback and not any("가" <= char <= "힣" for char in fallback):
        return [fallback]
    return []


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
    """구매 링크 결정 — 입력 파트너스 링크 또는 API 딥링크를 우선한다.

    우선순위:
      1) 사용자가 소싱 입력에 넣은 쿠팡 파트너스 링크
      2) 파트너스 API 딥링크 (키가 연결된 경우에만, 조용히 시도)
      3) 쿠팡 원본 링크

    ``youtube_comment_manual_product_link``는 이름 그대로 댓글에 표시할 원상품
    주소이므로 구매/제휴 링크로 승격하지 않는다.
    """
    from utils.url_security import is_coupang_partner_link

    if is_coupang_partner_link(coupang_url):
        link = str(coupang_url or "").strip()
        return {"purchase_url": link, "deep_link": link, "source": "manual"}

    try:
        from managers.coupang_manager import get_coupang_manager
        cm = get_coupang_manager()
        if cm.is_connected():
            link = str(cm.generate_deep_link(coupang_url) or "").strip()
            if is_coupang_partner_link(link):
                return {"purchase_url": link, "deep_link": link, "source": "api"}
            return {
                "purchase_url": coupang_url,
                "deep_link": "",
                "source": "original",
                "warning": cm.get_last_error_message(),
            }
    except Exception as e:
        logger.debug("[PlatformPipeline] API 딥링크 생략: %s", e)
    return {"purchase_url": coupang_url, "deep_link": "", "source": "original"}


def _resolve_partner_product_url(coupang_url: str) -> str:
    """Resolve one trusted Partners short link to its Coupang product URL.

    Cache matching is based on the stable Coupang product id. A newly issued
    affiliate code for the same product must therefore be resolved before we
    give up on an already verified marketplace video. Redirect following is
    deliberately disabled: only the first Location header is inspected and it
    is accepted only when it is another official HTTPS Coupang URL containing
    a product id.
    """
    from core.sourcing.report_cache import extract_coupang_product_id
    from utils.url_security import (
        is_coupang_partner_link,
        is_official_coupang_url,
    )

    source = str(coupang_url or "").strip()
    if not is_coupang_partner_link(source):
        return source if extract_coupang_product_id(source) else ""

    try:
        import requests

        response = requests.get(
            source,
            allow_redirects=False,
            stream=True,
            timeout=(3.0, 5.0),
            headers={"User-Agent": "Mozilla/5.0 (SSMaker cache resolver)"},
        )
        try:
            location = urljoin(source, str(response.headers.get("Location") or ""))
        finally:
            response.close()
    except Exception as exc:
        logger.info("[PlatformPipeline] 파트너스 상품 URL 확인 생략: %s", type(exc).__name__)
        return ""

    if not is_official_coupang_url(location, allow_shortlinks=False):
        return ""
    return location if extract_coupang_product_id(location) else ""


def _failure(
    code: str,
    cause: str,
    action: str,
    *,
    retriable: bool = True,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "code": code,
        "cause": str(cause or "").strip(),
        "action": str(action or "").strip(),
        "retriable": bool(retriable),
        "can_choose_other_product": True,
        "diagnostics": dict(diagnostics or {}),
        "blocked_stages": list(_BLOCKED_DELIVERY_STAGES),
    }


_DIAGNOSTIC_PLATFORM_LABELS = {
    "douyin": "Douyin",
    "xiaohongshu": "Xiaohongshu",
    "kuaishou": "Kuaishou",
    "search:duckduckgo": "DuckDuckGo",
    "search:bing": "Bing",
    "search:brave": "Brave Search",
}
_DIAGNOSTIC_REASON_LABELS = {
    "browser_session_failed": "브라우저 연결 종료",
    "access_challenge": "로그인/봇 차단",
    "page_open_timeout": "페이지 시간초과",
    "page_open_error": "페이지 열기 실패",
    "rate_limited": "요청 제한",
    "query_error": "검색 처리 오류",
    "no_results": "검색 결과 없음",
    "no_video_url": "재생 URL 없음",
    "download_timeout": "다운로드 시간초과",
    "download_failed": "다운로드 실패",
    "technical_rejected": "재생 조건 미달",
    "relevance_rejected": "상품 연관성 미달",
    "missing_candidate_metadata": "상품 확인 정보 없음",
    "duplicate_source": "이미 사용한 영상",
    "time_budget_exceeded": "검색 시간 예산 초과",
}


def _diagnostic_summary(diagnostics: Optional[Dict[str, Any]]) -> str:
    diagnostics = dict(diagnostics or {})
    per_platform = dict(diagnostics.get("platforms") or {})
    requested = [str(value) for value in diagnostics.get("requested_platforms") or []]
    ordered = list(dict.fromkeys(requested + sorted(per_platform)))
    parts: List[str] = []
    for platform in ordered:
        platform_counts = dict(per_platform.get(platform) or {})
        reasons = []
        for code, label in _DIAGNOSTIC_REASON_LABELS.items():
            count = int(platform_counts.get(code, 0) or 0)
            if count:
                reasons.append(f"{label} {count}회")
        if reasons:
            platform_label = _DIAGNOSTIC_PLATFORM_LABELS.get(platform, platform)
            parts.append(f"{platform_label}: {', '.join(reasons[:4])}")
    return " / ".join(parts[:6])


def _persist_platform_run_report(output_dir: str, report: Dict[str, Any]) -> str:
    """Persist both successful and failed attempts for queue/recovery audits."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        report.setdefault("finished_at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        report.setdefault("status", "succeeded" if report.get("ok") else "failed")
        if not report.get("ok"):
            failure = dict(report.get("failure") or {})
            report.setdefault(
                "blocked_stages",
                list(failure.get("blocked_stages") or _BLOCKED_DELIVERY_STAGES),
            )
        filename = (
            f"report_platform_{time.strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}.json"
        )
        path = os.path.join(output_dir, filename)
        report["report_path"] = path
        temporary = f"{path}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        os.replace(temporary, path)
        return path
    except Exception as exc:
        logger.warning("[PlatformPipeline] 실행 리포트 저장 실패: %s", exc)
        return ""


def describe_platform_search_failure(diagnostics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn low-level search counters into one actionable user-facing cause."""
    diagnostics = dict(diagnostics or {})
    counts = dict(diagnostics.get("counts") or {})
    if counts.get("browser_session_failed"):
        return _failure(
            "browser_session_failed",
            "자동 검색 브라우저 연결이 실행 중 종료되었습니다.",
            "현재 상품은 재시도 대기로 두고, 다음 실행에서 브라우저를 새로 시작합니다.",
            diagnostics=diagnostics,
        )
    if counts.get("access_challenge"):
        return _failure(
            "platform_access_blocked",
            "검색 사이트가 로그인 또는 안티봇 확인 화면을 표시했습니다.",
            "열린 Chrome에서 해당 사이트에 로그인한 뒤 같은 상품을 다시 검색해 주세요.",
            diagnostics=diagnostics,
        )
    if any(counts.get(key) for key in (
        "page_open_timeout", "page_open_error", "rate_limited",
        "query_error", "time_budget_exceeded",
    )):
        return _failure(
            "platform_search_unavailable",
            "검색 사이트 응답이 없거나 네트워크 시간 제한을 넘었습니다.",
            "인터넷 연결과 사이트 상태를 확인하고 잠시 후 다시 검색해 주세요.",
            diagnostics=diagnostics,
        )
    if counts.get("duplicate_source") and not any(
        counts.get(key) for key in ("relevance_rejected", "technical_rejected", "download_failed")
    ):
        return _failure(
            "all_sources_already_used",
            "검색된 영상이 모두 이전에 사용했거나 이미 점검한 소스였습니다.",
            "다른 상품을 선택하거나 잠시 후 새 검색 결과가 생겼을 때 다시 시도해 주세요.",
            diagnostics=diagnostics,
        )
    if counts.get("relevance_rejected") or counts.get("missing_candidate_metadata"):
        return _failure(
            "no_relevant_video",
            "검색 결과는 있었지만 상품 일치 근거가 부족해 안전 기준에서 제외했습니다.",
            "다른 상품을 선택하거나 상품명이 더 명확한 파트너스 링크로 다시 시도해 주세요.",
            diagnostics=diagnostics,
        )
    if any(counts.get(key) for key in ("technical_rejected", "download_failed", "download_timeout")):
        return _failure(
            "candidate_download_failed",
            "검색된 영상이 재생 조건을 충족하지 못했거나 다운로드에 실패했습니다.",
            "같은 상품을 다시 검색하면 다른 후보를 시도합니다. 계속 실패하면 다른 상품을 선택해 주세요.",
            diagnostics=diagnostics,
        )
    return _failure(
        "no_search_results",
        "선택한 검색 사이트에서 사용할 수 있는 상품 영상을 찾지 못했습니다.",
        "같은 상품을 다시 검색하거나 다른 상품을 선택해 주세요.",
        diagnostics=diagnostics,
    )


def format_failure_message(title: str, failure: Dict[str, Any]) -> str:
    message = (
        f"{title}\n"
        f"원인: {failure.get('cause') or '확인되지 않은 오류'}\n"
        f"해결: {failure.get('action') or '다시 시도해 주세요.'}"
    )
    summary = _diagnostic_summary(failure.get("diagnostics"))
    if summary:
        message += f"\n검색 내역: {summary}"
    if failure.get("blocked_stages"):
        message += (
            "\n후속 단계: 영상을 확보하지 못해 편집, YouTube 업로드, "
            "Linktree 등록을 시작하지 않았습니다."
        )
    return message


async def run_platform_sourcing(
    coupang_url: str,
    output_dir: Optional[str] = None,
    progress: ProgressCb = None,
    platforms: Optional[List[str]] = None,
    browser: Any = None,
    gemini_client: Any = None,
    product_name_hint: str = "",
    reedit_options: Optional[Dict[str, Any]] = None,
    min_similarity_score: float = 0.9,
    before_commit: BeforeCommitCb = None,
    download_only: bool = False,
    platform_min_relevance_score: Optional[float] = None,
    allow_image_fallback: bool = False,
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
        "quality_profile": "platform_reedit",
        "coupang_url": coupang_url,
        "product_info": {}, "deep_link": "", "keywords": {},
        "queries": [], "hit": None, "final_video": "",
        "render_integrity": {"ok": False, "source": "platform_video"},
        "failure": None, "blocked_stages": [],
        "source_kind": "",
        "auto_publish_safe": False,
        "requires_review": False,
        "fallback_reason": "",
    }

    own_browser = False
    product: Dict[str, Any] = {}

    async def ensure_browser(step: str) -> bool:
        """Start the owned browser lazily and report one structured failure."""
        nonlocal browser, own_browser
        if browser is not None:
            return True
        try:
            browser = await start_browser()
            own_browser = True
            return True
        except Exception as exc:
            report["failure"] = _failure(
                "browser_start_failed",
                f"자동 검색 브라우저를 시작하지 못했습니다 ({type(exc).__name__}).",
                "이 상품은 자동으로 대체 소스를 확인한 뒤 다음 예약 상품으로 넘어갑니다.",
            )
            report["error"] = format_failure_message(
                "상품 검색을 시작하지 못했어요.", report["failure"]
            )
            report["blocked_stages"] = list(report["failure"]["blocked_stages"])
            _emit(progress, step, report["error"], 0.0)
            return False

    async def try_review_image_fallback(
        triggering_failure: Dict[str, Any],
    ) -> bool:
        """Create an explicitly opted-in review artifact without charging work."""
        if download_only or not allow_image_fallback:
            return False
        image_url = str(product.get("image") or "").strip()
        if not image_url.startswith(("http://", "https://", "//")):
            return False

        from core.sourcing.pipeline import create_product_image_video_fallback

        _emit(
            progress,
            "video_create",
            "실사용 영상을 확보하지 못해 상품 이미지 검토용 영상을 만드는 중...",
            0.1,
        )
        fallback = await create_product_image_video_fallback(
            coupang_url=coupang_url,
            product_info=product,
            output_dir=out_dir,
        )
        if not fallback:
            return False

        fallback_video = str(fallback.get("video_file") or "")
        if not fallback_video or not os.path.exists(fallback_video):
            return False
        fallback = dict(fallback)
        fallback.setdefault("platform", "coupang_image")
        fallback.setdefault("via", "product_image")
        report["hit"] = fallback
        report["selected_source_url"] = str(
            fallback.get("video_url") or image_url
        )
        report["selected_source_id"] = ""
        report["final_video"] = fallback_video
        report["source_kind"] = "coupang_image"
        report["auto_publish_safe"] = False
        report["requires_review"] = True
        report["fallback_reason"] = str(
            fallback.get("fallback_reason") or "no_marketplace_video"
        )
        report["fallback_failure"] = dict(triggering_failure or {})
        report["failure"] = None
        report["error"] = ""
        report["blocked_stages"] = ["youtube_upload", "linktree_publish"]
        report["render_integrity"] = {
            "ok": True,
            "source": "coupang_image",
            "platform": "coupang_image",
            "via": "product_image",
        }
        report["ok"] = True
        _emit(
            progress,
            "video_create",
            "검토용 상품 이미지 영상 생성 완료 · 자동 업로드는 건너뜁니다.",
            1.0,
        )
        return True

    try:
        # ── 1) 캐시/큐 힌트를 먼저 사용하고, 꼭 필요할 때만 쿠팡을 연다. ──
        _emit(progress, "product_analysis", "저장된 상품 정보 확인 중...", 0.0)
        product_error = ""
        try:
            from core.sourcing.report_cache import find_cached_product_info

            product = dict(find_cached_product_info(coupang_url) or {})
        except Exception as exc:
            logger.warning("[PlatformPipeline] 상품 정보 캐시 확인 실패: %s", exc)
            product_error = type(exc).__name__
            product = {}

        # A failed report may contain a newly issued affiliate URL and a valid
        # product name, but no stable product id. Resolve that trusted short
        # link once and prefer metadata from the destination product. Without
        # this step the incomplete report shadows an older verified video and
        # needlessly sends the run back to blocked marketplace searches.
        try:
            from core.sourcing.report_cache import extract_coupang_product_id

            cached_product_url = str(product.get("url") or "")
            needs_stable_product_id = bool(product) and not extract_coupang_product_id(
                cached_product_url
            )
        except Exception:
            needs_stable_product_id = False
        if needs_stable_product_id:
            original_product_name = str(
                product.get("name") or product.get("title") or ""
            ).strip()
            resolved_product_url = _resolve_partner_product_url(coupang_url)
            if resolved_product_url and resolved_product_url != coupang_url:
                try:
                    resolved_product = dict(
                        find_cached_product_info(resolved_product_url) or {}
                    )
                except Exception as exc:
                    logger.warning(
                        "[PlatformPipeline] resolved 상품 캐시 확인 실패: %s", exc
                    )
                    resolved_product = {}
                if resolved_product:
                    product = resolved_product
                product = dict(product)
                if original_product_name:
                    product["name"] = original_product_name
                product["url"] = resolved_product_url
                product["affiliate_url"] = coupang_url

        hint = str(product_name_hint or "").strip()
        if hint:
            product = dict(product or {})
            product["name"] = hint
            product.setdefault("url", coupang_url)
            product["name_source"] = "product_name_hint"

        product_name = str(product.get("name") or product.get("title") or "").strip()
        if not product_name:
            # A prior explicitly publish-safe report can identify the product
            # even when its metadata record is incomplete. This URL-only
            # preflight must happen before Chrome or the blocked Coupang page.
            try:
                from core.sourcing.pipeline import find_cached_publish_safe_video

                preflight_hit = find_cached_publish_safe_video(
                    coupang_url=coupang_url,
                    product_info={},
                    output_dir=out_dir,
                    used_source_ids=set(),
                    min_similarity_score=_platform_relevance_threshold(
                        min_similarity_score,
                        required_score=platform_min_relevance_score,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "[PlatformPipeline] URL 기반 안전 영상 캐시 확인 실패: %s",
                    exc,
                )
                preflight_hit = None
            if preflight_hit:
                cached_title = str(
                    (preflight_hit.get("product") or {}).get("title")
                    or preflight_hit.get("title")
                    or ""
                ).strip()
                if cached_title:
                    product = {
                        "name": cached_title,
                        "url": coupang_url,
                        "source": "publish_safe_video_cache",
                    }
                    product_name = cached_title

        if not product_name:
            # With no cached metadata at all, resolve the trusted affiliate
            # redirect only after the URL-only safe-cache preflight missed.
            # This keeps the common cache path fast and still avoids opening a
            # full browser merely to learn the stable Coupang product id.
            resolved_product_url = _resolve_partner_product_url(coupang_url)
            if resolved_product_url and resolved_product_url != coupang_url:
                try:
                    from core.sourcing.report_cache import find_cached_product_info

                    product = dict(find_cached_product_info(resolved_product_url) or {})
                except Exception as exc:
                    logger.warning(
                        "[PlatformPipeline] resolved 상품 캐시 확인 실패: %s", exc
                    )
                    product = {}
                product_name = str(
                    product.get("name") or product.get("title") or ""
                ).strip()
                if product_name:
                    product = dict(product)
                    product["url"] = resolved_product_url
                    product["affiliate_url"] = coupang_url

        if not product_name:
            if not await ensure_browser("product_analysis"):
                return report
            try:
                product = await scrape_product(browser, coupang_url) or {}
            except Exception as exc:
                logger.warning("[PlatformPipeline] 상품 스크랩 실패: %s", exc)
                product_error = type(exc).__name__
                product = {}
            product_name = str(product.get("name") or product.get("title") or "").strip()

        if not product_name:
            report["failure"] = _failure(
                "coupang_product_unavailable",
                (
                    "쿠팡 상품 페이지가 삭제·차단되었거나 응답을 읽지 못했습니다"
                    + (f" ({product_error})" if product_error else "")
                    + "."
                ),
                "저장된 상품 정보가 생기면 자동으로 재시도하며, 현재 큐는 다음 상품으로 진행합니다.",
            )
            report["error"] = format_failure_message(
                "쿠팡 상품 확인에 실패했어요.", report["failure"]
            )
            report["blocked_stages"] = list(report["failure"]["blocked_stages"])
            _emit(progress, "product_analysis", report["error"], 0.0)
            return report

        product = dict(product or {})
        product["name"] = product_name
        product.setdefault("url", coupang_url)
        report["product_info"] = product
        _emit(progress, "product_analysis", f"상품: {product_name[:40]}", 1.0)

        # ── 2) 구매 링크 결정(수동 링크 최우선 — API 키 불필요) ──
        _emit(progress, "deep_link", "구매 링크 확인 중...", 0.0)
        link_info = _resolve_purchase_link(coupang_url)
        report["deep_link"] = link_info["deep_link"]
        report["purchase_url"] = link_info["purchase_url"]
        report["purchase_link_source"] = link_info["source"]
        if link_info.get("warning"):
            report["purchase_link_warning"] = str(link_info["warning"])
        _label = {"manual": "수동 링크 사용", "api": "API 딥링크 생성", "original": "원본 링크 사용"}
        _emit(progress, "deep_link", _label.get(link_info["source"], "링크 준비 완료"), 1.0)

        # ── 3) 키워드 변환(Gemini→룰) ──
        _emit(progress, "keyword_convert", "키워드 변환 중...", 0.0)
        keywords = await _convert_keywords(product_name, gemini_client)
        queries = build_queries(product_name, keywords)
        report["keywords"], report["queries"] = keywords, queries
        relevance_references = [
            product_name,
            str(keywords.get("chinese") or ""),
            str(keywords.get("english") or ""),
        ]
        from core.sourcing.product_searcher import _category_terms_for_keyword

        category_terms = _category_terms_for_keyword(
            str(keywords.get("english") or ""),
            reference_name=product_name,
            keyword_cn=str(keywords.get("chinese") or ""),
        )
        _emit(progress, "keyword_convert",
              f"검색어: {' / '.join(q[:14] for q in queries[:3])}", 1.0)

        # ── 4) 안전 캐시 → 3채널 검색·다운로드(소스 중복 스킵) ──
        _emit(progress, "overseas_search", "검증된 이전 영상 확인 중...", 0.05)
        skip_ids = set()
        try:
            from managers.uploaded_registry import get_uploaded_registry
            skip_ids = get_uploaded_registry().used_source_ids()
        except Exception as exc:
            report["error"] = f"중복 업로드 기록을 확인할 수 없어 자동 제작을 중단했어요: {exc}"
            _emit(progress, "overseas_search", report["error"], 0.0)
            return report
        relevance_threshold = _platform_relevance_threshold(
            min_similarity_score,
            required_score=platform_min_relevance_score,
        )
        from core.sourcing.pipeline import find_cached_publish_safe_video

        try:
            hit = find_cached_publish_safe_video(
                coupang_url=coupang_url,
                product_info=product,
                output_dir=out_dir,
                used_source_ids=skip_ids,
                min_similarity_score=relevance_threshold,
            )
        except Exception as exc:
            logger.warning("[PlatformPipeline] 안전 영상 캐시 확인 실패: %s", exc)
            report["cache_warning"] = f"{type(exc).__name__}: {exc}"
            hit = None
        if hit:
            hit = dict(hit)
            hit.setdefault("platform", str(hit.get("source") or "cached"))
            hit.setdefault("via", "verified_cache")
            report["source_kind"] = "cached_marketplace_video"
            report["cache_hit"] = True
            _emit(progress, "overseas_search", "검증된 이전 영상 재사용", 1.0)
        else:
            if not await ensure_browser("overseas_search"):
                browser_failure = dict(report.get("failure") or {})
                if await try_review_image_fallback(browser_failure):
                    return report
                return report

            _emit(
                progress,
                "overseas_search",
                f"'{product_name[:20]}' 중국어로 3채널 검색 중...",
                0.1,
            )
            search_diagnostics: Dict[str, Any] = {}
            try:
                hit = await search_platform_shorts(
                    browser,
                    queries,
                    out_dir,
                    platforms=platforms,
                    skip_source_ids=skip_ids,
                    relevance_references=relevance_references,
                    min_relevance_score=relevance_threshold,
                    category_terms=category_terms,
                    # A related product-family clip is sufficient. Later platforms are
                    # fallbacks, not a contest for an identical-listing score.
                    prefer_best=False,
                    diagnostics=search_diagnostics,
                )
            except (ConnectionError, BrokenPipeError) as exc:
                search_failure = _failure(
                    "browser_session_failed",
                    f"자동 검색 브라우저 연결이 실행 중 종료되었습니다 ({type(exc).__name__}).",
                    "현재 상품은 대체 소스를 확인하고 다음 실행에서 브라우저를 새로 시작합니다.",
                    diagnostics=search_diagnostics,
                )
                report["search_diagnostics"] = search_diagnostics
                report["failure"] = search_failure
                report["error"] = format_failure_message(
                    "상품 영상 검색 연결이 끊겼어요.", search_failure
                )
                report["blocked_stages"] = list(search_failure["blocked_stages"])
                _emit(progress, "overseas_search", report["error"], 0.0)
                if await try_review_image_fallback(search_failure):
                    return report
                return report
            except Exception as exc:
                search_failure = _failure(
                    "platform_search_failed",
                    f"플랫폼 검색 처리 중 오류가 발생했습니다 ({type(exc).__name__}).",
                    "현재 상품은 건너뛰고 다음 예약 상품을 계속 처리합니다.",
                    diagnostics=search_diagnostics,
                )
                report["search_diagnostics"] = search_diagnostics
                report["failure"] = search_failure
                report["error"] = format_failure_message(
                    "상품 영상 검색 처리에 실패했어요.", search_failure
                )
                report["blocked_stages"] = list(search_failure["blocked_stages"])
                _emit(progress, "overseas_search", report["error"], 0.0)
                if await try_review_image_fallback(search_failure):
                    return report
                return report
            report["search_diagnostics"] = search_diagnostics
            if not hit:
                search_failure = describe_platform_search_failure(search_diagnostics)
                report["failure"] = search_failure
                report["error"] = format_failure_message(
                    "상품 영상 검색에 실패했어요.", search_failure
                )
                report["blocked_stages"] = list(search_failure["blocked_stages"])
                _emit(progress, "overseas_search", report["error"], 0.0)
                if await try_review_image_fallback(search_failure):
                    return report
                return report
            report["source_kind"] = "platform_video"

        report["hit"] = hit
        report["selected_source_url"] = str(hit.get("video_url") or "")
        from managers.uploaded_registry import normalize_source_id
        report["selected_source_id"] = normalize_source_id(
            report["selected_source_url"]
        )
        _emit(progress, "overseas_search", f"{hit['platform']}에서 영상 확보", 1.0)
        _emit(progress, "video_download", f"{hit['platform']} 영상 {hit.get('size_mb', 0)}MB", 1.0)

        # 실검색 점검은 원본 파일·소스 URL·관련도만 확인한다.
        # 일반 UI/풀자동화는 기본값 False로 재편집을 계속한다.
        if download_only:
            report["ok"] = True
            report["download_only"] = True
            report["downloaded_video"] = str(hit.get("video_file") or "")
            report["auto_publish_safe"] = bool(hit.get("auto_publish_safe", True))
            report["requires_review"] = bool(hit.get("requires_review", False))
            report["fallback_reason"] = str(hit.get("fallback_reason") or "")
            report["render_integrity"] = {
                "ok": True,
                "source": "platform_video_download",
                "platform": hit.get("platform", ""),
                "via": hit.get("via", ""),
            }
            return report

        # ── 5) 쇼츠 규격 재편집 ──
        _emit(progress, "video_create", "재편집 중(9:16·속도·오디오 옵션 적용)...", 0.1)
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
            min_duration=10.0,
        )
        if not ok or not os.path.exists(edited):
            report["error"] = "재편집에 실패했어요."
            _emit(progress, "video_create", report["error"], 0.0)
            return report
        if before_commit is not None:
            try:
                before_commit(edited)
            except Exception as exc:
                report["error"] = f"완성 영상의 사용량을 확정하지 못했어요: {exc}"
                _emit(progress, "video_create", report["error"], 1.0)
                return report
        report["final_video"] = edited
        report["auto_publish_safe"] = True
        report["requires_review"] = False
        report["fallback_reason"] = str(hit.get("fallback_reason") or "")
        report["render_integrity"] = {"ok": True, "source": "platform_video",
                                      "platform": hit["platform"], "via": hit.get("via", "")}
        _emit(progress, "video_create", "재편집 완료", 1.0)

        # ── 6) 원본 정리 ──
        # 소스 사용 기록은 실제 원격 업로드 성공과 같은 트랜잭션에서 확정한다.
        if not hit.get("cached_from_report"):
            try:
                os.remove(hit["video_file"])
            except OSError:
                pass

        report["ok"] = True
        report["blocked_stages"] = []
        return report
    finally:
        _persist_platform_run_report(out_dir, report)
        if own_browser:
            try:
                await browser.stop()
            except Exception:
                pass
