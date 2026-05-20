"""
Full automation pipeline: Coupang link → sourcing → deep link → video → publish → upload.

This module orchestrates the entire Mode 3 flow.
"""
from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

MIN_TRUSTED_VIDEO_SCORE = float(os.getenv("SSMAKER_MIN_TRUSTED_VIDEO_SCORE", "0.10"))
# Default behavior: keep real marketplace videos once downloaded.
# Set SSMAKER_REPLACE_LOW_CONFIDENCE_WITH_IMAGE=1 to restore strict replacement.
REPLACE_LOW_CONFIDENCE_WITH_IMAGE = (
    os.getenv("SSMAKER_REPLACE_LOW_CONFIDENCE_WITH_IMAGE", "0").strip() == "1"
)
MARKETPLACE_VIDEO_INITIAL_MAX_TRY_WITH_IMAGE = 3
MARKETPLACE_VIDEO_EXPANDED_MAX_TRY_WITH_IMAGE = 12


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
        """Start zendriver browser with error handling.

        Tries common Chrome / Chromium / Edge locations on macOS, Linux, and
        Windows so the pipeline works on machines where the browser isn't on
        PATH (which is the default on macOS).
        """
        import os
        import sys
        import zendriver as zd

        # Probe known browser binaries by platform.
        candidates: list[str] = []
        if sys.platform == "darwin":
            candidates = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
                "/Applications/Google Chrome Dev.app/Contents/MacOS/Google Chrome Dev",
                "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "/Applications/Arc.app/Contents/MacOS/Arc",
            ]
        elif sys.platform.startswith("linux"):
            candidates = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
            ]
        elif sys.platform.startswith("win"):
            candidates = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            ]

        executable = next((p for p in candidates if os.path.isfile(p)), None)
        if executable:
            logger.info("[Pipeline] Using browser: %s", executable)

        # Persist profile across runs so login/session state survives
        # (important for 1688/taobao anti-bot and login-gated flows).
        default_profile = os.path.join(str(Path.home()), ".ssmaker", "zendriver_profile")
        user_data = os.getenv("SSMAKER_ZENDRIVER_PROFILE", default_profile)
        os.makedirs(user_data, exist_ok=True)

        kwargs: dict = {
            "headless": False,
            "sandbox": False,                        # macOS user install + already-running Chrome → sandbox init flakes
            "user_data_dir": user_data,              # isolated profile
            "browser_args": [
                "--window-size=1400,900",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                # Force English UI/Accept-Language at the Chrome process level
                # so AliExpress doesn't auto-redirect to ko.aliexpress.com.
                "--lang=en-US",
                "--accept-lang=en-US,en;q=0.9",
            ],
            "browser_connection_timeout": 1.5,       # default 0.25s is too short for cold launches
            "browser_connection_max_tries": 30,      # default 10 → up to 45s instead of 2.5s
        }
        if executable:
            kwargs["browser_executable_path"] = executable

        async def _start_with_geo_cookies():
            """Start zendriver and seed AliExpress geo-routing cookies BEFORE
            any navigation, so the very first request to aliexpress.com gets
            served the US storefront (which keeps the seller video player)
            instead of getting redirected to ko.aliexpress.com.

            The cookie shape was reverse-engineered from how AliExpress's own
            "ship-to" picker writes the storefront preference.
            """
            br = await zd.start(**kwargs)
            try:
                # Open ANY aliexpress page first so the cookie domain is valid.
                tab = await br.get("https://www.aliexpress.com/about/blank.html")
                await tab.sleep(2)
                await tab.evaluate("""
                    (() => {
                        const set = (k, v) => {
                            // Try every plausible apex domain — AliExpress
                            // shares some cookies across .com / .us / ko.com.
                            for (const d of ['.aliexpress.com', '.aliexpress.us', 'aliexpress.com']) {
                                try {
                                    document.cookie = k + '=' + v +
                                        '; domain=' + d +
                                        '; path=/; max-age=86400';
                                } catch(e) {}
                            }
                        };
                        // site=usa locks the storefront, region=US the geo,
                        // c_tp=USD the currency, x_alimid is a noise field
                        // AliExpress also writes — empty value works fine.
                        set('aep_usuc_f', 'site=usa&region=US&c_tp=USD&b_locale=en_US&x_alimid=');
                        set('intl_locale', 'en_US');
                        set('xman_us_f', 'x_l=0&x_locale=en_US&site=usa');
                        set('xman_t', '');
                        set('aep_common_f', '1');
                        // Block the gateway-adapt redirect that strips video
                        set('aep_history_currency', 'USD');
                    })()
                """)
            except Exception as e:
                logger.warning("[Pipeline] geo-cookie seed failed: %s", e)
            return br

        try:
            return await _start_with_geo_cookies()
        except Exception as e:
            logger.error("[Pipeline] Browser start failed: %s", e)
            # Retry once in headless mode — bypasses any window-server collision.
            kwargs["headless"] = True
            try:
                logger.info("[Pipeline] Retrying browser launch in headless mode")
                return await _start_with_geo_cookies()
            except Exception as ee:
                logger.error("[Pipeline] Headless retry also failed: %s", ee)
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
            search_1688_by_image,
            search_aliexpress_by_image,
            find_products_with_video,
            _category_terms_for_keyword,
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
            cn_kw = (self.keywords or {}).get("chinese", "").strip()
            en_kw = (self.keywords or {}).get("english", "").strip()
            if not cn_kw and not en_kw:
                # Both empty → cannot search either marketplace. Most common cause:
                # no Gemini client configured AND no rule-based / Latin tokens in the title.
                self.error = (
                    "키워드 변환에 실패했습니다. Gemini API 키를 설정하거나 "
                    "상품명에 영문/규격이 포함된 다른 쿠팡 링크를 사용해주세요."
                )
                self._progress("keyword_convert", self.error, 1.0)
                return False
            self._progress(
                "keyword_convert",
                f"CN: {cn_kw[:30] or '(없음)'} / EN: {en_kw[:30] or '(없음)'}",
                1.0,
            )

            # ── Step 4: Overseas search ──
            self._progress("overseas_search", "해외 상품 검색 중...", 0.0)

            # Coupang product image (used for image-first search)
            coupang_image = (self.product_info or {}).get("image") or ""
            # Normalize protocol-relative URLs (//image.coupangcdn.com/... → https://...)
            if coupang_image.startswith("//"):
                coupang_image = "https:" + coupang_image
            print(f"[Pipeline] Coupang image URL: {coupang_image[:100] or '(none)'}")

            # 1688 image-first search
            candidates_1688_img: List[Dict] = []
            if coupang_image.startswith("http"):
                self._progress("overseas_search", "1688 이미지 검색(우선) 중...", 0.08)
                try:
                    candidates_1688_img = await search_1688_by_image(
                        browser,
                        coupang_image,
                        self.product_info["name"],
                        cn_kw,
                        en_kw,
                    )
                except Exception as e:
                    logger.warning("[Pipeline] 1688 image-first search failed: %s", e)

            # AliExpress image-first search: prioritize visual match before text keyword matching.
            candidates_ali_img: List[Dict] = []
            if coupang_image.startswith("http"):
                self._progress("overseas_search", "AliExpress 이미지 검색(우선) 중...", 0.15)
                try:
                    candidates_ali_img = await search_aliexpress_by_image(
                        browser, coupang_image,
                        self.product_info["name"], en_kw, cn_kw,
                    )
                except Exception as e:
                    logger.warning("[Pipeline] Image-first search failed: %s", e)

            # 1688 keyword search (augmentation for image-first mode)
            candidates_1688_text: List[Dict] = []
            should_run_1688_text = len(candidates_1688_img) < 12
            if should_run_1688_text and cn_kw:
                candidates_1688_text = await search_1688(
                    browser, cn_kw, self.product_info["name"]
                )
            elif not cn_kw:
                logger.info("[Pipeline] Skipping 1688 text search: no Chinese keyword")

            # Merge with image-search priority (image candidates first).
            candidates_1688: List[Dict] = []
            seen_1688_ids = set()
            for pool in (candidates_1688_img, candidates_1688_text):
                for c in pool:
                    cid = c.get("id")
                    if cid and cid in seen_1688_ids:
                        continue
                    if cid:
                        seen_1688_ids.add(cid)
                    candidates_1688.append(c)

            self._progress(
                "overseas_search",
                f"1688: {len(candidates_1688)}개 발견 (이미지 {len(candidates_1688_img)} + 텍스트 {len(candidates_1688_text)})",
                0.3,
            )

            # AliExpress (English keyword required)
            candidates_ali_text: List[Dict] = []
            # Image-first mode still runs text search to widen coverage when
            # image candidates are too few.
            should_run_ali_text = len(candidates_ali_img) < 12
            if should_run_ali_text and en_kw:
                candidates_ali_text = await search_aliexpress(
                    browser, en_kw,
                    self.product_info["name"], cn_kw,
                )
            elif not en_kw:
                logger.info("[Pipeline] Skipping AliExpress text search: no English keyword")

            # Merge with image-search priority (image candidates first).
            candidates_ali: List[Dict] = []
            seen_ali_ids = set()
            for pool in (candidates_ali_img, candidates_ali_text):
                for c in pool:
                    cid = c.get("id")
                    if cid and cid in seen_ali_ids:
                        continue
                    if cid:
                        seen_ali_ids.add(cid)
                    candidates_ali.append(c)

            self._progress(
                "overseas_search",
                f"AliExpress: {len(candidates_ali)}개 발견 (이미지 {len(candidates_ali_img)} + 텍스트 {len(candidates_ali_text)})",
                0.7,
            )

            # Image-based search FALLBACK — when text search yields very few
            # candidates the Coupang product image is a much stronger query
            # because it bypasses translation/synonym variance entirely. We
            # merge image-search candidates into the text-search pool so the
            # find_products_with_video stage gets to pick from the union.
            if (
                len(candidates_1688) + len(candidates_ali) < 8
                and coupang_image.startswith("http")
            ):
                msg = "[Pipeline] Few candidates — adding image-search fallback"
                print(msg)
                logger.info(msg)
                try:
                    img_candidates = await search_aliexpress_by_image(
                        browser, coupang_image,
                        self.product_info["name"], en_kw, cn_kw,
                    )
                    if img_candidates:
                        # Merge by ID — don't double-count items already in pool
                        existing_ids = {c.get("id") for c in candidates_ali}
                        for ic in img_candidates:
                            if ic.get("id") and ic["id"] not in existing_ids:
                                candidates_ali.append(ic)
                        self._progress(
                            "overseas_search",
                            f"이미지검색 추가: AliExpress {len(candidates_ali)}개",
                            0.85,
                        )
                except Exception as e:
                    logger.warning("[Pipeline] Image search fallback failed: %s", e)

            if not candidates_1688 and not candidates_ali:
                self.error = "해외 상품을 찾지 못했습니다."
                self._progress("overseas_search", self.error, 1.0)
                return False

            self._progress("overseas_search", "검색 완료", 1.0)

            # ── Step 5: Find products with video + download ──
            self._progress("video_download", "영상 있는 상품 탐색 중...", 0.0)

            # Build category guard from English keyword — rejects wrong-category
            # candidates before we even try them, lifting matching accuracy.
            # Pass reference_name + cn_kw so the guard can fall back to a
            # domain-level catch-all when no specific dictionary entry matches.
            category_terms = _category_terms_for_keyword(
                en_kw,
                reference_name=self.product_info["name"],
                keyword_cn=cn_kw,
            )
            # References passed to the overlap safety net during the relaxed
            # 0.0-threshold fallback. We compose them once here so they're
            # available to every find_products_with_video call below.
            overlap_refs = [
                self.product_info["name"],
                en_kw,
                cn_kw,
            ]
            # Use print() so the .command tee captures these alongside the
            # progress bar lines; logger.info goes to a file the batch script
            # doesn't always tail.
            if category_terms:
                msg = f"[Pipeline] Category guard active ({len(category_terms)} terms): {', '.join(category_terms[:6])}..."
                print(msg)
                logger.info(msg)
            else:
                msg = "[Pipeline] No category guard — relying on score + overlap safety net"
                print(msg)
                logger.info(msg)

            need_from_ali = 2 if not candidates_1688 else 1
            need_from_1688 = 2 - need_from_ali

            # 1688
            if need_from_1688 > 0 and candidates_1688:
                found_1688 = await find_products_with_video(
                    browser, candidates_1688, self.output_dir, "1688",
                    count=need_from_1688, category_terms=category_terms,
                    overlap_references=overlap_refs,
                )
                self.sourced_products.extend(found_1688)
                if len(found_1688) < need_from_1688:
                    need_from_ali += (need_from_1688 - len(found_1688))

            self._progress("video_download", f"1688: {sum(1 for p in self.sourced_products if p['source']=='1688')}개", 0.4)

            # AliExpress
            if candidates_ali:
                ali_max_try = (
                    MARKETPLACE_VIDEO_INITIAL_MAX_TRY_WITH_IMAGE
                    if coupang_image.startswith("http")
                    else 15
                )
                found_ali = await find_products_with_video(
                    browser, candidates_ali, self.output_dir, "aliexpress",
                    count=need_from_ali,
                    max_try=ali_max_try,
                    category_terms=category_terms,
                    overlap_references=overlap_refs,
                )
                self.sourced_products.extend(found_ali)
                # If quick scan missed everything, keep scanning deeper candidates
                # before giving up to image fallback.
                if (
                    not found_ali
                    and coupang_image.startswith("http")
                    and len(candidates_ali) > ali_max_try
                    and need_from_ali > 0
                ):
                    self._progress(
                        "video_download",
                        "초기 후보에서 영상 미발견 — AliExpress 추가 후보 탐색 중...",
                        0.58,
                    )
                    found_ali_extra = await find_products_with_video(
                        browser,
                        candidates_ali[ali_max_try:],
                        self.output_dir,
                        "aliexpress",
                        count=need_from_ali,
                        max_try=MARKETPLACE_VIDEO_EXPANDED_MAX_TRY_WITH_IMAGE,
                        category_terms=category_terms,
                        overlap_references=overlap_refs,
                    )
                    self.sourced_products.extend(found_ali_extra)

            # FINAL fallback: if we have candidates but extracted 0 videos,
            # the text-search candidates simply don't carry videos. Try
            # image-based search — it surfaces a different candidate set,
            # often heavily visual demo-driven sellers who DO ship videos.
            if (
                not self.sourced_products
                and coupang_image.startswith("http")
                and not any(c.get("image_search") for c in candidates_ali)
            ):
                msg = "[Pipeline] 0 videos from text search — last-resort image search"
                print(msg)
                logger.info(msg)
                try:
                    img_candidates = await search_aliexpress_by_image(
                        browser, coupang_image,
                        self.product_info["name"], en_kw, cn_kw,
                    )
                    if img_candidates:
                        found_img = await find_products_with_video(
                            browser, img_candidates, self.output_dir,
                            "aliexpress", count=2, max_try=MARKETPLACE_VIDEO_EXPANDED_MAX_TRY_WITH_IMAGE,
                            min_score=0.0,
                            category_terms=category_terms,
                            overlap_references=overlap_refs,
                        )
                        self.sourced_products.extend(found_img)
                        msg2 = f"[Pipeline] Image-search fallback yielded {len(found_img)} video(s)"
                        print(msg2)
                        logger.info(msg2)
                except Exception as e:
                    logger.warning("[Pipeline] Last-resort image search failed: %s", e)

            # If live marketplace search cannot extract a fresh video, reuse a
            # previously sourced safe marketplace video for the same Coupang
            # product/link before falling back to a static product-image video.
            if not self.sourced_products:
                cached = self._find_cached_marketplace_video()
                if cached:
                    self._progress(
                        "video_download",
                        "실시간 영상 없음 — 이전 안전 자동 산출 영상 재사용",
                        0.88,
                    )
                    self.sourced_products.append(cached)

            # If nothing matched at the strict threshold, retry progressively looser.
            # Korean Coupang title vs Korean AliExpress title often scores < 0.05
            # because the marketplace gives translated/romanized titles, so we
            # fall through to threshold 0 (any candidate that has video) before
            # giving up. For products with a valid Coupang image, the exact
            # image-video fallback above will normally stop before this point.
            if not self.sourced_products and (candidates_ali or candidates_1688):
                for relaxed in (0.05, 0.0):
                    if self.sourced_products:
                        break
                    logger.warning(
                        "[Pipeline] No matches at previous threshold; retrying min_score=%.2f",
                        relaxed,
                    )
                    self._progress(
                        "video_download",
                        f"유사 후보 부족 — 검색 조건 완화 ({relaxed:.2f}) 재시도",
                        0.7,
                    )
                    if candidates_ali:
                        found_ali_loose = await find_products_with_video(
                            browser, candidates_ali, self.output_dir, "aliexpress",
                            count=2, min_score=relaxed, max_try=MARKETPLACE_VIDEO_EXPANDED_MAX_TRY_WITH_IMAGE,
                            category_terms=category_terms,
                            overlap_references=overlap_refs,
                        )
                        self.sourced_products.extend(found_ali_loose)

            # Final exact-product fallback: only after strict + relaxed
            # marketplace scans are exhausted.
            if not self.sourced_products and coupang_image.startswith("http"):
                self._progress(
                    "video_download",
                    "상품 영상 없음 — 쿠팡 상품 이미지로 대체 영상 생성 중...",
                    0.9,
                )
                fallback = await self._create_product_image_video(coupang_image)
                if fallback:
                    self.sourced_products.append(fallback)

            # Optional strict replacement mode:
            # if marketplace videos are too low-confidence, replace with exact
            # product-image fallback. Disabled by default to avoid blocking
            # auto-upload when valid marketplace videos were found.
            if (
                REPLACE_LOW_CONFIDENCE_WITH_IMAGE
                and self.sourced_products
                and coupang_image.startswith("http")
            ):
                best_score = max(
                    float((p.get("product") or {}).get("score") or 0.0)
                    for p in self.sourced_products
                )
                if best_score < MIN_TRUSTED_VIDEO_SCORE:
                    self._progress(
                        "video_download",
                        "후보 영상 유사도 낮음 — 쿠팡 상품 이미지 영상으로 대체 중...",
                        0.9,
                    )
                    fallback = await self._create_product_image_video(coupang_image)
                    if fallback:
                        logger.info(
                            "[Pipeline] Replaced low-confidence videos (best=%.3f) with product image fallback",
                            best_score,
                        )
                        self.sourced_products = [fallback]
            elif self.sourced_products:
                best_score = max(
                    float((p.get("product") or {}).get("score") or 0.0)
                    for p in self.sourced_products
                )
                if best_score < MIN_TRUSTED_VIDEO_SCORE:
                    logger.warning(
                        "[Pipeline] Keeping low-confidence marketplace videos (best=%.3f, threshold=%.3f) "
                        "because strict replacement is disabled",
                        best_score,
                        MIN_TRUSTED_VIDEO_SCORE,
                    )

            self._progress(
                "video_download",
                f"총 {len(self.sourced_products)}개 영상 다운로드 완료",
                1.0,
            )

            if not self.sourced_products:
                self.error = (
                    "영상이 있는 상품을 찾지 못했습니다. "
                    "더 구체적인 쿠팡 상품 URL을 시도해주세요."
                )
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
                from core.sourcing.keyword_converter import generate_content_text

                prompt = (
                    f"다음 상품에 대한 짧은 마케팅 설명을 한국어로 작성해줘 (2-3문장).\n"
                    f"상품명: {name}\n"
                    f"가격: {price or '미정'}\n"
                    f"SNS 숏폼 영상용 설명이야. 이모지 포함, 구매 유도 문구 넣어줘."
                )
                desc = await generate_content_text(self.gemini_client, prompt)
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

    async def _create_product_image_video(self, image_url: str) -> Optional[Dict[str, Any]]:
        """Create a short vertical MP4 from the real Coupang product image."""
        return await self._run_blocking_image_video_create(image_url)

    def _find_cached_marketplace_video(self) -> Optional[Dict[str, Any]]:
        """Find a previous safe marketplace video for the same Coupang target."""
        current_name = ((self.product_info or {}).get("name") or "").strip()
        current_url = (self.coupang_url or "").strip()
        output = Path(self.output_dir).expanduser()
        if not output.exists():
            return None

        reports = sorted(
            output.glob("report_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        def _same_target(report: Dict[str, Any]) -> bool:
            report_url = str(report.get("coupang_url") or "").strip()
            report_name = str((report.get("product_info") or {}).get("name") or "").strip()
            return bool(
                (current_url and report_url == current_url)
                or (current_name and report_name and report_name == current_name)
            )

        for report_path in reports:
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not _same_target(report):
                continue
            for item in report.get("sourced_products") or report.get("sourcing_results") or []:
                source = str(item.get("source") or "").lower()
                video_file = str(item.get("video_file") or "")
                if (
                    source == "coupang_image"
                    or item.get("requires_review") is True
                    or item.get("auto_publish_safe") is False
                    or not video_file
                    or not os.path.exists(video_file)
                ):
                    continue

                size_mb = item.get("video_size_mb")
                if size_mb is None:
                    try:
                        size_mb = round(os.path.getsize(video_file) / (1024 * 1024), 1)
                    except OSError:
                        size_mb = 0

                logger.info(
                    "[Pipeline] Reusing cached marketplace video from %s: %s",
                    report_path,
                    video_file,
                )
                product = {
                    "title": item.get("title") or current_name,
                    "url": item.get("url") or current_url,
                    "score": item.get("similarity") or 1.0,
                    "source": item.get("source") or source,
                    "cached_from_report": str(report_path),
                }
                return {
                    "source": item.get("source") or source,
                    "product": product,
                    "video_url": item.get("url") or "",
                    "video_file": video_file,
                    "size_mb": size_mb,
                    "fallback_reason": "cached_marketplace_video",
                    "auto_publish_safe": True,
                    "requires_review": False,
                }
        return None

    async def _run_blocking_image_video_create(self, image_url: str) -> Optional[Dict[str, Any]]:
        import asyncio

        return await asyncio.to_thread(self._create_product_image_video_sync, image_url)

    def _create_product_image_video_sync(self, image_url: str) -> Optional[Dict[str, Any]]:
        """Blocking implementation for the product-image fallback video."""
        import tempfile
        import hashlib
        from io import BytesIO

        import cv2
        import numpy as np
        import requests
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps

        try:
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                ),
                "Referer": "https://www.coupang.com/",
            }
            response = requests.get(image_url, headers=headers, timeout=20)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")

            width, height = 720, 1280
            fps, duration = 24, 8
            frame_count = fps * duration

            bg = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=26))
            bg = ImageEnhance.Brightness(bg).enhance(0.62)

            fg_base = image.copy()
            fg_base.thumbnail((620, 620), Image.Resampling.LANCZOS)

            os.makedirs(self.output_dir, exist_ok=True)
            name = (self.product_info or {}).get("name", "")
            digest = hashlib.sha1(
                f"{self.coupang_url}|{name}|{image_url}".encode("utf-8")
            ).hexdigest()[:10]
            stamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                self.output_dir,
                f"sourcing_coupang_image_{stamp}_{digest}_video.mp4",
            )
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp4", dir=self.output_dir)
            os.close(tmp_fd)

            writer = cv2.VideoWriter(
                tmp_path,
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (width, height),
            )
            if not writer.isOpened():
                raise RuntimeError("OpenCV VideoWriter를 열 수 없습니다.")

            for frame_idx in range(frame_count):
                t = frame_idx / max(1, frame_count - 1)
                zoom = 1.0 + 0.045 * t
                fg_size = (
                    max(1, int(fg_base.width * zoom)),
                    max(1, int(fg_base.height * zoom)),
                )
                fg = fg_base.resize(fg_size, Image.Resampling.LANCZOS)

                frame = bg.copy()
                shadow = Image.new("RGBA", (fg.width + 36, fg.height + 36), (0, 0, 0, 0))
                shadow_box = Image.new("RGBA", (fg.width, fg.height), (0, 0, 0, 145))
                shadow.paste(shadow_box, (18, 18))
                shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))

                x = (width - fg.width) // 2
                y = int(height * 0.36) - fg.height // 2
                frame.paste(shadow.convert("RGB"), (x - 18, y - 18), shadow)
                frame.paste(fg, (x, y))

                arr = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
                writer.write(arr)

            writer.release()
            os.replace(tmp_path, output_path)
            size_mb = round(os.path.getsize(output_path) / (1024 * 1024), 1)

            product = {
                "id": "coupang-image-fallback",
                "title": (self.product_info or {}).get("name", "쿠팡 상품 이미지 영상"),
                "price": (self.product_info or {}).get("price"),
                "image": image_url,
                "url": self.coupang_url,
                "score": 1.0,
                "source": "coupang_image",
                "fallback_reason": "no_marketplace_video",
            }
            logger.info("[Pipeline] Product image fallback video created: %s", output_path)
            return {
                "source": "coupang_image",
                "product": product,
                "video_url": image_url,
                "video_file": output_path,
                "size_mb": size_mb,
                "fallback_reason": "no_marketplace_video",
                "auto_publish_safe": False,
                "requires_review": True,
            }
        except Exception as exc:
            logger.warning("[Pipeline] Product image fallback failed: %s", exc)
            try:
                if "tmp_path" in locals() and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            return None

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
                "fallback_reason": p.get("fallback_reason") or p["product"].get("fallback_reason"),
                "auto_publish_safe": bool(p.get("auto_publish_safe", p["source"] != "coupang_image")),
                "requires_review": bool(p.get("requires_review", p["source"] == "coupang_image")),
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
