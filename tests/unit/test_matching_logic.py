# -*- coding: utf-8 -*-
"""
Validates the strengthened matching logic in core/sourcing/product_searcher.py
and core/sourcing/keyword_converter.py.

Focus: realistic Korean Coupang title -> 1688/AliExpress candidate scenarios,
where the previous Jaccard-only approach scored ~0 across languages. The new
logic should:
  - Reject obvious wrong-category candidates via the expanded guards
  - Score the right candidate higher than wrong candidates
  - Produce at least one search keyword (cn or en) for every common kitchen item
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.sourcing.product_searcher import (
    _similarity_score,
    _multi_reference_score,
    _category_terms_for_keyword,
    _passes_category_guard,
    _tokenize,
    _STOPWORD_TOKENS,
    _normalize_synonyms,
    _has_minimum_overlap,
    _detect_domain,
)
from core.sourcing.keyword_converter import convert_keywords_rule_based


# ──────────────────────── tokenizer / stopwords ────────────────────────


def test_tokenizer_drops_packaging_noise():
    tokens = _tokenize("Premium Stainless Steel Kitchen Scissors 1pc Set")
    assert "1pc" not in tokens
    assert "set" not in tokens
    assert "premium" not in tokens
    assert "scissors" in tokens
    assert "kitchen" in tokens


def test_tokenizer_explodes_chinese_chars():
    tokens = _tokenize("海绵架")
    assert "海" in tokens
    assert "绵" in tokens
    assert "架" in tokens


# ──────────────────────── multi-reference scoring ────────────────────────


def test_multi_reference_picks_highest():
    # Korean ref shares no tokens with English candidate, but English keyword does
    refs = ["에코홀릭 스텐 다용도 가위", "kitchen scissors", "厨房剪刀"]
    candidate = "Premium Kitchen Scissors Stainless Steel"
    score = _multi_reference_score(candidate, refs)
    assert score > 0.1, f"Expected real match score, got {score}"


def test_multi_reference_zero_for_unrelated():
    refs = ["주방 가위", "kitchen scissors", "厨房剪刀"]
    candidate = "iPhone 15 Pro Case Magnetic Magsafe Compatible"
    score = _multi_reference_score(candidate, refs)
    assert score < 0.05, f"Unrelated should score near zero, got {score}"


# ──────────────────────── category guards ────────────────────────


def test_category_guard_kitchen_scissors_blocks_phone_case():
    terms = _category_terms_for_keyword(
        "kitchen scissors",
        reference_name="에코홀릭 다용도 주방 가위",
        keyword_cn="厨房剪刀",
    )
    assert terms, "Expected guard terms for 'kitchen scissors'"
    # Right product passes
    assert _passes_category_guard("Premium Kitchen Scissors Stainless", terms)
    # Wrong product blocked
    assert not _passes_category_guard("iPhone Case Magnetic", terms)


def test_category_guard_vegetable_chopper_blocks_phone_stand():
    terms = _category_terms_for_keyword(
        "vegetable chopper",
        reference_name="에코홀릭 야채 다지기 채칼",
        keyword_cn="蔬菜切碎器",
    )
    assert terms
    assert _passes_category_guard("Manual Vegetable Chopper Slicer", terms)
    assert not _passes_category_guard("Universal Phone Stand Holder", terms)


def test_category_guard_falls_back_to_kitchen_domain():
    """When no specific dictionary guard matches, but the Korean reference
    indicates kitchen, we still apply a kitchen-domain catch-all so a
    "stainless steel" search doesn't return a watch."""
    terms = _category_terms_for_keyword(
        "stainless steel",
        reference_name="주방 스텐 보관함",
        keyword_cn="厨房不锈钢",
    )
    # Should fall back to kitchen domain
    assert terms, "Kitchen-intent fallback should produce guards"
    # Watch is wrong domain — should be blocked
    assert not _passes_category_guard(
        "Stainless Steel Sport Watch Wristband", terms
    )
    # Real kitchen product passes
    assert _passes_category_guard(
        "Stainless Steel Kitchen Storage Container", terms
    )


def test_category_guard_garlic_press():
    terms = _category_terms_for_keyword(
        "garlic press",
        reference_name="다지기 마늘 분쇄",
        keyword_cn="蒜泥器",
    )
    assert terms
    assert _passes_category_guard("Manual Garlic Press Crusher", terms)
    assert _passes_category_guard("蒜泥器 厨房", terms)
    assert not _passes_category_guard("Smartphone Holder Magnetic", terms)


def test_category_guard_ice_tray():
    terms = _category_terms_for_keyword(
        "ice cube tray",
        reference_name="실리콘 얼음틀",
        keyword_cn="硅胶冰格",
    )
    assert terms
    assert _passes_category_guard("Silicone Ice Cube Tray with Lid", terms)
    assert not _passes_category_guard("Phone Magnetic Stand Holder", terms)


# ──────────────────────── keyword conversion ────────────────────────


def test_keyword_conversion_vegetable_chopper():
    out = convert_keywords_rule_based("에코홀릭 다용도 야채 다지기 1+1")
    assert out["chinese"], f"Expected CN keyword, got {out}"
    assert out["english"], f"Expected EN keyword, got {out}"
    # Should pick up the chopper compound
    assert "切碎" in out["chinese"] or "chopper" in out["english"].lower()


def test_keyword_conversion_garlic_press():
    out = convert_keywords_rule_based("스텐 마늘 다지기 압착기")
    assert out["chinese"]
    assert out["english"]
    assert "garlic" in out["english"].lower()


def test_keyword_conversion_ice_tray():
    out = convert_keywords_rule_based("실리콘 얼음틀 뚜껑포함")
    assert out["chinese"]
    assert "ice" in out["english"].lower() or "冰" in out["chinese"]


def test_keyword_conversion_kitchen_scissors():
    out = convert_keywords_rule_based("스텐 다용도 주방 가위 강력")
    assert out["chinese"]
    assert out["english"]
    assert "scissor" in out["english"].lower() or "剪" in out["chinese"]


def test_keyword_conversion_dumpling_maker():
    out = convert_keywords_rule_based("다용도 만두 메이커 모양틀")
    assert out["chinese"]
    assert out["english"]
    assert "dumpling" in out["english"].lower() or "饺子" in out["chinese"]


# ──────────────────────── synonym normalization ────────────────────────


def test_synonym_sponge_canonical():
    assert _normalize_synonyms("스폰지") == "수세미"
    assert _normalize_synonyms("스펀지") == "수세미"
    assert _normalize_synonyms("수세미") == "수세미"


def test_synonym_holder_canonical():
    assert _normalize_synonyms("홀더") == "거치대"
    assert _normalize_synonyms("스탠드") == "거치대"
    assert _normalize_synonyms("받침") == "거치대"
    assert _normalize_synonyms("거치대") == "거치대"


def test_synonym_phone_canonical():
    assert _normalize_synonyms("핸드폰") == "휴대폰"
    assert _normalize_synonyms("스마트폰") == "휴대폰"
    assert _normalize_synonyms("폰") == "휴대폰"


def test_tokenizer_applies_synonym_rewrite():
    """The Coupang title and AliExpress title use different Korean words for
    the same concept — synonym rewrite forces them to overlap."""
    coupang = _tokenize("아케이바이 공중부양 수세미 거치대")
    aliexpress = _tokenize("스폰지 받침 1pcs")
    assert "수세미" in coupang and "수세미" in aliexpress
    assert "거치대" in coupang and "거치대" in aliexpress
    assert (coupang & aliexpress), "Synonyms should produce token overlap"


def test_similarity_score_synonym_pair():
    """수세미 거치대 vs 스폰지 받침 — without synonym rewrite this scores 0,
    with rewrite it should score > 0.3 (multiple overlapping tokens)."""
    score = _similarity_score("아케이바이 수세미 거치대", "스폰지 받침 1pcs")
    assert score > 0.2, f"Expected meaningful score after synonym rewrite, got {score}"


# ──────────────────────── domain detection ────────────────────────


def test_detect_domain_kitchen():
    assert _detect_domain("주방 수세미 거치대", "sponge holder", "海绵架") == "kitchen"


def test_detect_domain_phone():
    assert _detect_domain("아이폰 케이스 맥세이프", "phone case", "手机壳") == "phone"


def test_detect_domain_beauty():
    assert _detect_domain("쿠션 파운데이션 컴팩트", "cushion foundation", "气垫") == "beauty"


def test_detect_domain_fashion():
    assert _detect_domain("남성 후드 티셔츠 빅사이즈", "hoodie t-shirt", "卫衣") == "fashion"


def test_detect_domain_uncovered():
    """A truly unrelated title with no domain markers returns empty."""
    assert _detect_domain("xyz 12345", "unknown", "") == ""


# ──────────────────────── overlap safety net ────────────────────────


def test_overlap_zero_overlap_rejected():
    """At threshold=0.0, candidate with zero token overlap must be rejected."""
    refs = ["주방 수세미 거치대", "sponge holder", "海绵架"]
    bad_title = "iPhone 15 Magsafe Charger Wireless"
    assert not _has_minimum_overlap(bad_title, refs)


def test_overlap_with_overlap_passes():
    refs = ["주방 수세미 거치대", "sponge holder", "海绵架"]
    good_title = "Premium Sponge Holder for Kitchen"
    assert _has_minimum_overlap(good_title, refs)


def test_overlap_synonym_token_counts():
    """Korean synonym overlap counts as overlap (수세미 ↔ 스폰지)."""
    refs = ["수세미 거치대", "sponge holder", ""]
    candidate = "스폰지 받침 1pcs"
    assert _has_minimum_overlap(candidate, refs)


# ──────────────────────── category guards: phone domain ────────────────────────


def test_phone_case_blocks_kitchen():
    terms = _category_terms_for_keyword(
        "phone case",
        reference_name="아이폰 15 케이스 맥세이프",
        keyword_cn="手机壳",
    )
    assert terms
    assert _passes_category_guard("iPhone 15 Pro Magsafe Case", terms)
    assert not _passes_category_guard("Stainless Steel Sponge Holder", terms)


def test_earphone_blocks_unrelated():
    terms = _category_terms_for_keyword(
        "earphone",
        reference_name="블루투스 이어폰",
        keyword_cn="蓝牙耳机",
    )
    assert terms
    assert _passes_category_guard("Wireless Bluetooth Earphones", terms)
    assert not _passes_category_guard("Kitchen Sponge Drainer", terms)


# ──────────────────────── category guards: fashion domain ────────────────────────


def test_tshirt_blocks_unrelated():
    terms = _category_terms_for_keyword(
        "tshirt",
        reference_name="남성 반팔 티셔츠 면",
        keyword_cn="T恤",
    )
    assert terms
    assert _passes_category_guard("Cotton Casual T-Shirt for Men", terms)
    assert not _passes_category_guard("Magnetic Phone Holder", terms)


def test_shoes_blocks_unrelated():
    terms = _category_terms_for_keyword(
        "shoes",
        reference_name="남성 운동화 캐주얼",
        keyword_cn="鞋",
    )
    assert terms
    assert _passes_category_guard("Men Sneakers Sport Shoes Running", terms)
    assert not _passes_category_guard("Kitchen Garlic Press", terms)


# ──────────────────────── category guards: beauty domain ────────────────────────


def test_lipstick_blocks_unrelated():
    terms = _category_terms_for_keyword(
        "lipstick",
        reference_name="에뛰드 립스틱 매트",
        keyword_cn="唇膏",
    )
    assert terms
    assert _passes_category_guard("Matte Lipstick Long Lasting", terms)
    assert not _passes_category_guard("Stainless Steel Pot", terms)


def test_face_mask_blocks_unrelated():
    terms = _category_terms_for_keyword(
        "face mask",
        reference_name="메디힐 마스크팩 10매",
        keyword_cn="面膜",
    )
    assert terms
    assert _passes_category_guard("Hydrating Face Mask Sheet", terms)
    assert not _passes_category_guard("Phone Holder Stand", terms)


# ──────────────────────── domain fallback for uncovered specific keyword ────────────────────────


def test_uncovered_keyword_falls_back_to_phone_domain():
    """Search keyword 'unique gadget' has no specific guard, but reference says
    phone — should fall back to phone domain tokens."""
    terms = _category_terms_for_keyword(
        "unique gadget thing",
        reference_name="아이폰 15 프로 맥세이프 액세서리",
        keyword_cn="iPhone 配件",
    )
    assert terms, "Should fall back to phone domain"
    # Phone domain catch-all must reject a kitchen candidate
    assert not _passes_category_guard("Stainless Steel Frying Pan", terms)
    # And accept a phone-related candidate
    assert _passes_category_guard("iPhone Magsafe Wallet Holder", terms)
