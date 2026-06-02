"""Utilities for reusing verified sourcing reports across runs."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple
from urllib.parse import unquote


REPORT_PATTERNS = (
    "**/report.json",
    "**/report_*.json",
    "**/sourcing_report.json",
    "**/summary.json",
)


def get_default_report_root() -> Path:
    configured = os.getenv("SSMAKER_SOURCING_CACHE_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(os.path.expanduser("~/.ssmaker/sourcing_output"))


def extract_coupang_product_id(url: str) -> str:
    text = unquote(str(url or ""))
    match = re.search(r"/products/(\d+)", text)
    if match:
        return match.group(1)
    match = re.search(r"(?:productId|product_id)=(\d+)", text, re.IGNORECASE)
    return match.group(1) if match else ""


def extract_coupang_partner_code(url: str) -> str:
    text = unquote(str(url or ""))
    match = re.search(r"link\.coupang\.com/a/([A-Za-z0-9_-]+)", text)
    return match.group(1) if match else ""


def normalize_image_url(url: str) -> str:
    if url and url.startswith("//"):
        return "https:" + url
    return url or ""


def normalize_product_name(name: str) -> str:
    return " ".join(str(name or "").lower().split())


def iter_report_payloads(
    root: Optional[Path | str] = None,
    *,
    limit: int = 240,
) -> Iterator[Tuple[Path, Dict[str, Any]]]:
    """Yield report-like payloads newest first.

    The app has produced several report layouts over time:
    root-level report_*.json, nested report.json files, and summary.json files
    whose `results` entries contain the actual report body. Search all of them
    so a verified source video from a previous run can be reused when live
    marketplace pages are blocked or slow.
    """
    base = Path(root).expanduser() if root is not None else get_default_report_root()
    if not base.is_dir():
        return

    paths: set[Path] = set()
    for pattern in REPORT_PATTERNS:
        paths.update(p for p in base.glob(pattern) if p.is_file() and p.stat().st_size > 0)

    sorted_paths = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    for path in sorted_paths[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if path.name == "summary.json" and isinstance(data.get("results"), list):
            for result in data.get("results") or []:
                report = _report_from_summary_result(result)
                if report:
                    yield path, report
            continue

        if isinstance(data, dict):
            yield path, data


def report_matches_target(
    report: Dict[str, Any],
    *,
    target_url: str = "",
    target_product_info: Optional[Dict[str, Any]] = None,
    target_name: str = "",
) -> bool:
    target_product_info = target_product_info or {}
    target_urls = [
        target_url,
        str(target_product_info.get("url") or ""),
        str(target_product_info.get("product_url") or ""),
    ]
    target_ids = {pid for pid in (extract_coupang_product_id(u) for u in target_urls) if pid}
    target_partners = {
        code for code in (extract_coupang_partner_code(u) for u in target_urls) if code
    }
    current_name = normalize_product_name(
        target_name or str(target_product_info.get("name") or "")
    )

    report_product = report.get("product_info") or {}
    report_urls = [
        str(report.get("coupang_url") or ""),
        str(report.get("url") or ""),
        str(report_product.get("url") or ""),
        str(report_product.get("product_url") or ""),
    ]
    report_ids = {pid for pid in (extract_coupang_product_id(u) for u in report_urls) if pid}
    report_partners = {
        code for code in (extract_coupang_partner_code(u) for u in report_urls) if code
    }
    report_name = normalize_product_name(
        str(report_product.get("name") or report.get("product_name") or "")
    )

    if target_ids and report_ids:
        return bool(target_ids & report_ids)
    if target_partners and report_partners:
        return bool(target_partners & report_partners)
    if (target_ids or target_partners) and (report_ids or report_partners):
        return False

    return bool(current_name and report_name and current_name == report_name)


def find_cached_product_info(product_url: str) -> Optional[Dict[str, Any]]:
    """Find previously scraped Coupang product info for a URL."""
    for _, report in iter_report_payloads():
        if not report_matches_target(report, target_url=product_url):
            continue

        product = report.get("product_info") or {}
        name = str(product.get("name") or report.get("product_name") or "").strip()
        if not name:
            continue

        report_url = str(report.get("coupang_url") or report.get("url") or "")
        product_url_cached = str(product.get("url") or "").strip()
        return {
            "name": name,
            "image": normalize_image_url(str(product.get("image") or "").strip()),
            "price": product.get("price"),
            "url": product_url_cached or report_url or product_url,
            "source": "cached_report",
        }
    return None


def _report_from_summary_result(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    url = result.get("url") or result.get("coupang_url") or ""
    items = (
        result.get("items")
        or result.get("sourced_products")
        or result.get("sourcing_results")
        or []
    )
    return {
        "coupang_url": url,
        "product_info": {
            "name": result.get("product_name") or result.get("name") or "",
            "url": url,
            "image": result.get("image") or "",
            "price": result.get("price"),
        },
        "sourced_products": items,
        "sourcing_results": list(items),
        "best_similarity": result.get("best_similarity"),
        "match_status": result.get("match_status"),
        "error": result.get("error"),
    }
