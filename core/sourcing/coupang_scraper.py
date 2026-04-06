# -*- coding: utf-8 -*-
"""
Coupang product page scraper using zendriver (CDP).
Extracts product name, thumbnail, price from a Coupang product URL.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 2
PAGE_LOAD_TIMEOUT = 15  # seconds


async def scrape_product(browser: Any, product_url: str) -> Optional[Dict[str, str]]:
    """
    Navigate to a Coupang product page and extract key info.

    Args:
        browser: zendriver Browser instance (already started).
        product_url: Full Coupang product URL.

    Returns:
        Dict with keys: name, image, price, url.  None on failure.
    """
    if "coupang.com" not in product_url:
        logger.warning("[CoupangScraper] Not a Coupang URL: %s", product_url)
        return None

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tab = await browser.get(product_url)
            if tab is None:
                logger.warning("[CoupangScraper] Failed to open tab (attempt %d/%d)", attempt, MAX_RETRIES)
                await asyncio.sleep(2)
                continue

            # Wait for page with timeout
            await asyncio.wait_for(tab.sleep(6), timeout=PAGE_LOAD_TIMEOUT)

            data = await tab.evaluate("""
                (() => {
                    const h1 = document.querySelector(
                        'h1.prod-buy-header__title, h2.prod-buy-header__title, .prod-buy-header__title'
                    );
                    const ogTitle = document.querySelector('meta[property="og:title"]');
                    const ogImage = document.querySelector('meta[property="og:image"]');
                    const price = document.querySelector('.total-price strong');
                    return {
                        name: h1
                            ? h1.textContent.trim()
                            : (ogTitle ? ogTitle.content.replace(/ \\| 쿠팡$/, '') : null),
                        image: ogImage ? ogImage.content : null,
                        price: price ? price.textContent.trim() : null,
                        url: window.location.href
                    };
                })()
            """)

            if not data or not data.get("name"):
                logger.warning("[CoupangScraper] Failed to extract product info (attempt %d/%d)", attempt, MAX_RETRIES)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2)
                    continue
                return None

            # Clean up name
            name = re.sub(r'\s*\|\s*쿠팡\s*$', '', data["name"]).strip()
            data["name"] = name

            logger.info("[CoupangScraper] Product: %s", name[:60])
            return data

        except asyncio.TimeoutError:
            last_error = "페이지 로딩 시간 초과"
            logger.warning("[CoupangScraper] Page load timeout (attempt %d/%d)", attempt, MAX_RETRIES)
        except Exception as e:
            last_error = str(e)
            logger.error("[CoupangScraper] Error (attempt %d/%d): %s", attempt, MAX_RETRIES, e)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(2)

    logger.error("[CoupangScraper] All %d attempts failed. Last error: %s", MAX_RETRIES, last_error)
    return None
