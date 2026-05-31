"""
Gemini-only helper for sourcing fallback query planning.

This module intentionally avoids any Codex/CLI bridge path. It uses the
already-initialized Gemini client (user API key) to generate additional
marketplace search queries when default sourcing recall is low.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from utils.logging_config import get_logger
from core.sourcing.keyword_converter import generate_content_text

logger = get_logger(__name__)


def _normalize_query(text: str, max_chars: int = 48) -> str:
    raw = " ".join(str(text or "").replace("\n", " ").split()).strip()
    if not raw:
        return ""
    cleaned = re.sub(r"[\"'`{}\[\]]", "", raw)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;:/")
    if len(cleaned) <= max_chars:
        return cleaned
    clipped = cleaned[:max_chars].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0].strip()
    return clipped or cleaned[:max_chars]


def _split_query_keywords(text: str, *, max_terms: int = 6) -> List[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]+|[\uac00-\ud7af]+|[a-zA-Z0-9]+", str(text or ""))
    out: List[str] = []
    seen = set()
    for token in tokens:
        q = _normalize_query(token, max_chars=24)
        if not q:
            continue
        lk = q.lower()
        if lk in seen:
            continue
        seen.add(lk)
        out.append(q)
        if len(out) >= max_terms:
            break
    return out


def _fallback_queries(product_name: str, keyword_cn: str, keyword_en: str) -> Dict[str, List[str]]:
    cn_seed = _normalize_query(keyword_cn, max_chars=48)
    en_seed = _normalize_query(keyword_en, max_chars=48)

    cn_parts = _split_query_keywords(keyword_cn, max_terms=8)
    en_parts = _split_query_keywords(keyword_en, max_terms=8)
    name_parts = _split_query_keywords(product_name, max_terms=6)

    aliexpress: List[str] = []
    aliexpress.extend([en_seed] if en_seed else [])
    if len(en_parts) >= 2:
        aliexpress.append(_normalize_query(" ".join(en_parts[:2]), max_chars=48))
    if len(en_parts) >= 3:
        aliexpress.append(_normalize_query(" ".join(en_parts[:3]), max_chars=48))
    if name_parts:
        aliexpress.append(_normalize_query(" ".join(name_parts[:2]), max_chars=48))

    market1688: List[str] = []
    market1688.extend([cn_seed] if cn_seed else [])
    if len(cn_parts) >= 2:
        market1688.append(_normalize_query(" ".join(cn_parts[:2]), max_chars=48))
    if len(cn_parts) >= 3:
        market1688.append(_normalize_query(" ".join(cn_parts[:3]), max_chars=48))
    if name_parts:
        market1688.append(_normalize_query(" ".join(name_parts[:2]), max_chars=48))

    def _uniq(values: List[str], max_count: int = 4) -> List[str]:
        out: List[str] = []
        seen = set()
        for value in values:
            q = _normalize_query(value, max_chars=48)
            if not q:
                continue
            lk = q.lower()
            if lk in seen:
                continue
            seen.add(lk)
            out.append(q)
            if len(out) >= max_count:
                break
        return out

    return {
        "aliexpress": _uniq(aliexpress),
        "1688": _uniq(market1688),
    }


def _parse_json_block(text: str) -> Optional[Dict[str, List[str]]]:
    raw = str(text or "").strip()
    if not raw:
        return None

    obj = None
    try:
        obj = json.loads(raw)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return None
        try:
            obj = json.loads(match.group(0))
        except Exception:
            return None

    if not isinstance(obj, dict):
        return None

    ali = obj.get("aliexpress_queries") or obj.get("aliexpress") or []
    cn = obj.get("search_1688_queries") or obj.get("queries_1688") or obj.get("1688") or []
    if not isinstance(ali, list):
        ali = []
    if not isinstance(cn, list):
        cn = []

    return {
        "aliexpress": [str(x) for x in ali if str(x or "").strip()],
        "1688": [str(x) for x in cn if str(x or "").strip()],
    }


async def build_gemini_computer_use_queries(
    *,
    gemini_client: object,
    product_name: str,
    keyword_cn: str,
    keyword_en: str,
    max_queries_each: int = 4,
) -> Dict[str, List[str]]:
    """
    Build fallback search query sets using Gemini (user API key path).

    Returns:
        {"aliexpress": [...], "1688": [...]}
    """
    fallback = _fallback_queries(product_name, keyword_cn, keyword_en)
    if not gemini_client:
        return fallback

    prompt = (
        "너는 해외 마켓 상품 소싱 검색을 돕는 에이전트다.\n"
        "목표: 원본 상품과 가장 유사한 판매 페이지를 찾을 수 있는 검색 쿼리 생성.\n"
        "주의: 장식 문구/감탄사/문장형 금지, 짧은 명사구만 출력.\n\n"
        f"원본 상품명(KR): {product_name}\n"
        f"기존 CN 키워드: {keyword_cn}\n"
        f"기존 EN 키워드: {keyword_en}\n\n"
        "다음 JSON 형식으로만 답해:\n"
        "{\n"
        '  "aliexpress_queries": ["..."],\n'
        '  "search_1688_queries": ["..."]\n'
        "}\n"
        "각 배열은 2~4개, 중복 금지."
    )

    try:
        text = await generate_content_text(gemini_client, prompt)
        parsed = _parse_json_block(text)
        if not parsed:
            logger.warning("[GeminiComputerUse] Query JSON parse failed, using fallback set")
            return fallback

        def _uniq(values: List[str]) -> List[str]:
            out: List[str] = []
            seen = set()
            for value in values:
                q = _normalize_query(value, max_chars=48)
                if not q:
                    continue
                lk = q.lower()
                if lk in seen:
                    continue
                seen.add(lk)
                out.append(q)
                if len(out) >= max_queries_each:
                    break
            return out

        ali = _uniq(parsed.get("aliexpress", [])) or fallback.get("aliexpress", [])
        cn = _uniq(parsed.get("1688", [])) or fallback.get("1688", [])
        result = {"aliexpress": ali[:max_queries_each], "1688": cn[:max_queries_each]}
        logger.info(
            "[GeminiComputerUse] Query plan ready (AliExpress=%s, 1688=%s)",
            result["aliexpress"],
            result["1688"],
        )
        return result
    except Exception as exc:
        logger.warning("[GeminiComputerUse] Query generation failed, fallback: %s", exc)
        return fallback

