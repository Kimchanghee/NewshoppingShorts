"""
Full automation pipeline: Coupang link → sourcing → deep link → video → publish → upload.

This module orchestrates the entire Mode 3 flow.
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)


class SourcingPipeline:
    """
    Orchestrates: Coupang scrape → keyword convert → overseas search →
    video download → deep link → description → (hand off to batch for video creation).
    """

    # Step IDs for progress tracking
    STEPS = [
        ("product_analysis", "상품 분석"),
        ("deep_link", "파트너스 딥링크 생성"),
        ("keyword_convert", "키워드 변환"),
        ("overseas_search", "해외 상품 검색"),
        ("video_download", "영상 다운로드"),
        ("description_gen", "상품 설명 생성"),
        ("video_create", "영상 제작"),
        ("linktree_publish", "링크트리 발행"),
        ("upload", "업로드"),
    ]

    def __init__(
        self,
        coupang_url: str,
        output_dir: str,
        on_progress: Optional[Callable[[str, str, float], None]] = None,
        gemini_client: Optional[Any] = None,
    ):
        """
        Args:
            coupang_url: Coupang product URL.
            output_dir: Directory for downloaded videos and report.
            on_progress: Callback(step_id, message, progress_0_to_1).
            gemini_client: Optional Gemini API client for keyword conversion.
        """
        self.coupang_url = coupang_url
        self.output_dir = output_dir
        self.on_progress = on_progress
        self.gemini_client = gemini_client

        # Results populated during run
        self.product_info: Optional[Dict] = None
        self.deep_link: Optional[str] = None
        self.keywords: Optional[Dict[str, str]] = None
        self.sourced_products: List[Dict] = []
        self.description: str = ""
        self.error: Optional[str] = None

    def _progress(self, step_id: str, message: str, pct: float = 0.0):
        logger.info("[Pipeline] [%s] %s", step_id, message)
        if self.on_progress:
            try:
                self.on_progress(step_id, message, pct)
            except Exception:
                pass

    async def _start_browser(self):
        """Start zendriver browser with error handling."""
        import zendriver as zd
        try:
            browser = await zd.start(headless=False, browser_args=["--window-size=1400,900"])
            return browser
        except Exception as e:
            logger.error("[Pipeline] Browser start failed: %s", e)
            return None

    async def run_sourcing(self) -> bool:
        """
        Run steps 1-6 (sourcing phase).
        Returns True if at least one video was sourced.
        Video creation / upload is handled separately by the batch pipeline.
        """
        from core.sourcing.coupang_scraper import scrape_product
        from core.sourcing.keyword_converter import convert_keywords_gemini
        from core.sourcing.product_searcher import (
            search_aliexpress,
            search_1688,
            find_products_with_video,
        )

        os.makedirs(self.output_dir, exist_ok=True)

        browser = None
        try:
            browser = await self._start_browser()
            if browser is None:
                self.error = "브라우저를 시작할 수 없습니다. Chrome이 설치되어 있는지 확인해주세요."
                self._progress("product_analysis", self.error, 0.0)
                return False

            # ── Step 1: Product analysis ──
            self._progress("product_analysis", "쿠팡 상품 페이지 접속 중...", 0.0)
            self.product_info = await scrape_product(browser, self.coupang_url)
            if not self.product_info or not self.product_info.get("name"):
                self.error = "쿠팡 상품 정보를 추출할 수 없습니다."
                self._progress("product_analysis", self.error, 0.0)
                return False
            self._progress(
                "product_analysis",
                f"상품: {self.product_info['name'][:50]}",
                1.0,
            )

            # ── Step 2: Deep link ──
            self._progress("deep_link", "파트너스 딥링크 생성 중...", 0.0)
            try:
                from managers.coupang_manager import get_coupang_manager
                cm = get_coupang_manager()
                if cm.is_connected():
                    self.deep_link = cm.generate_deep_link(self.coupang_url)
                    if self.deep_link:
                        self._progress("deep_link", f"딥링크: {self.deep_link[:60]}", 1.0)
                    else:
                        self._progress("deep_link", "딥링크 생성 실패 (API 키 확인 필요)", 1.0)
                else:
                    self._progress("deep_link", "쿠팡파트너스 미연결 - 건너뜀", 1.0)
            except Exception as e:
                self._progress("deep_link", f"딥링크 오류: {e}", 1.0)

            # ── Step 3: Keyword conversion ──
            self._progress("keyword_convert", "키워드 변환 중...", 0.0)
            self.keywords = await convert_keywords_gemini(
                self.product_info["name"], self.gemini_client
            )
            if not self.keywords or not self.keywords.get("chinese") or not self.keywords.get("english"):
                self.error = "키워드 변환에 실패했습니다."
                self._progress("keyword_convert", self.error, 1.0)
                return False
            self._progress(
                "keyword_convert",
                f"CN: {self.keywords['chinese'][:30]} / EN: {self.keywords['english'][:30]}",
                1.0,
            )

            # ── Step 4: Overseas search ──
            self._progress("overseas_search", "해외 상품 검색 중...", 0.0)

            # 1688 (skip if login required)
            candidates_1688 = await search_1688(
                browser, self.keywords["chinese"], self.product_info["name"]
            )
            self._progress("overseas_search", f"1688: {len(candidates_1688)}개 발견", 0.3)

            # AliExpress
            candidates_ali = await search_aliexpress(
                browser, self.keywords["english"],
                self.product_info["name"], self.keywords["chinese"]
            )
            self._progress("overseas_search", f"AliExpress: {len(candidates_ali)}개 발견", 0.7)

            if not candidates_1688 and not candidates_ali:
                self.error = "해외 상품을 찾지 못했습니다."
                self._progress("overseas_search", self.error, 1.0)
                return False

            self._progress("overseas_search", "검색 완료", 1.0)

            # ── Step 5: Find products with video + download ──
            self._progress("video_download", "영상 있는 상품 탐색 중...", 0.0)

            need_from_ali = 2 if not candidates_1688 else 1
            need_from_1688 = 2 - need_from_ali

            # 1688
            if need_from_1688 > 0 and candidates_1688:
                found_1688 = await find_products_with_video(
                    browser, candidates_1688, self.output_dir, "1688", count=need_from_1688
                )
                self.sourced_products.extend(found_1688)
                if len(found_1688) < need_from_1688:
                    need_from_ali += (need_from_1688 - len(found_1688))

            self._progress("video_download", f"1688: {sum(1 for p in self.sourced_products if p['source']=='1688')}개", 0.4)

            # AliExpress
            if candidates_ali:
                found_ali = await find_products_with_video(
                    browser, candidates_ali, self.output_dir, "aliexpress", count=need_from_ali
                )
                self.sourced_products.extend(found_ali)

            self._progress(
                "video_download",
                f"총 {len(self.sourced_products)}개 영상 다운로드 완료",
                1.0,
            )

            if not self.sourced_products:
                self.error = "영상이 있는 상품을 찾지 못했습니다."
                return False

            # ── Step 6: Generate description ──
            self._progress("description_gen", "상품 설명 생성 중...", 0.0)
            self.description = await self._generate_description()
            self._progress("description_gen", "설명 생성 완료", 1.0)

            return True

        except Exception as e:
            self.error = f"소싱 파이프라인 오류: {e}"
            logger.error("[Pipeline] %s", self.error, exc_info=True)
            return False
        finally:
            if browser:
                try:
                    await browser.stop()
                except Exception:
                    pass

    async def _generate_description(self) -> str:
        """Generate marketing description for the product."""
        name = self.product_info.get("name", "") if self.product_info else ""
        price = self.product_info.get("price", "") if self.product_info else ""

        if self.gemini_client:
            try:
                prompt = (
                    f"다음 상품에 대한 짧은 마케팅 설명을 한국어로 작성해줘 (2-3문장).\n"
                    f"상품명: {name}\n"
                    f"가격: {price or '미정'}\n"
                    f"SNS 숏폼 영상용 설명이야. 이모지 포함, 구매 유도 문구 넣어줘."
                )
                response = await self.gemini_client.generate_content_async(prompt)
                desc = response.text.strip()
                if desc:
                    return desc
            except Exception as e:
                logger.warning("[Pipeline] Gemini description error: %s", e)

        # Fallback
        desc = f"지금 핫한 {name}!"
        if price:
            desc += f" 단돈 {price}원!"
        desc += " 링크 클릭해서 최저가로 구매하세요!"
        return desc

    def get_video_paths(self) -> List[str]:
        """Return list of downloaded video file paths."""
        return [p["video_file"] for p in self.sourced_products if os.path.exists(p.get("video_file", ""))]

    def get_report(self) -> Dict[str, Any]:
        """Return full sourcing report as dict."""
        items = [
            {
                "source": p["source"],
                "title": p["product"].get("title"),
                "url": p["product"].get("url"),
                "similarity": p["product"].get("score"),
                "video_file": p["video_file"],
                "video_size_mb": p["size_mb"],
            }
            for p in self.sourced_products
        ]
        return {
            "coupang_url": self.coupang_url,
            "product_info": self.product_info,
            "deep_link": self.deep_link,
            "keywords": self.keywords,
            "description": self.description,
            "sourced_products": items,
            # Backward compatibility for consumers still using the old key.
            "sourcing_results": list(items),
            "error": self.error,
        }
