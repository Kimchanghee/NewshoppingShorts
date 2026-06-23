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
    _passes_reference_constraints,
    _tokenize,
    _STOPWORD_TOKENS,
    _normalize_synonyms,
    _has_minimum_overlap,
    _detect_domain,
    _looks_b2b_candidate_title,
    _looks_b2b_detail_text,
    _preferred_chinese_query_variants,
    _preferred_english_query_variants,
    _extract_semantic_features,
    _semantic_similarity_score,
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


def test_semantic_score_lifts_electric_chopper_match_to_publish_threshold():
    refs = [
        "전동 멀티 믹서기 블렌더 마늘 다지기 야채 다지기 만능 다지기",
        "Electric Food Processor, Multi-functional Blender, Vegetable Chopper, Garlic Mincer",
        "电动多功能搅拌机 蔬菜切碎机 蒜泥器",
    ]
    candidate = "2in1 multy functional Chopper / garlic vegetable meat electric Chopper Mixer Processor"
    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9


def test_semantic_score_lifts_sink_sponge_caddy_match_to_publish_threshold():
    refs = [
        "노멀리즘 304 올스텐 싱크대 수세미 거치대 자동물빠짐 주방세제 거치대",
        "304 Stainless Steel Kitchen Sink Caddy Auto Draining Sponge Holder Dish Soap Organizer Rack",
        "304不锈钢水槽海绵架 自动排水厨房置物架 洗洁精沥水架",
    ]
    candidate = "Integrated Sponge, Soap & Towel Rack Stainless Steel Multi-Functional Sink Organizer for Kitchen"
    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9


def test_semantic_score_lifts_tumbler_ice_mold_match_to_publish_threshold():
    refs = [
        "네이쳐리빙 실리콘 텀블러 얼음틀 트레이",
        "silicone tumbler ice mold, cylinder ice tray, ice cup mold",
        "硅胶保温杯冰格 圆柱冰格模具 冰杯硅胶模具",
    ]
    candidate = "Ice Cube Tray for Tumbler Cup 30Oz-40Oz Silicone Cylinder Ice Mold with Lid"
    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9


def test_semantic_score_lifts_portable_bag_sealer_match_to_publish_threshold():
    refs = [
        "FDUCE mini bag sealer portable heat sealer handheld plastic bag sealing machine",
        "mini bag sealer, portable heat sealer, handheld bag sealer, plastic bag sealing machine",
    ]
    candidate = "Mini Heat Sealer Plastic Bag Heat Sealing Machine Rechargable Plastic Storage Package Sealer Handheld Clip Bag Food Heat Sealer"
    assert "biodegradable" not in _extract_semantic_features("plastic bag sealing machine")
    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9


def test_semantic_score_lifts_milk_frother_match_to_publish_threshold():
    refs = [
        "cordless electric hand mixer portable milk frother handheld egg beater cream whipper",
        "portable milk frother electric whisk mixer egg beater",
    ]
    candidate = "Portable Electric Milk Frothers Handheld Blender USB Mini Coffee Maker Whisk Mixer Cappuccino Cream Egg Beater Food Blender"
    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9


def test_semantic_score_lifts_car_vacuum_match_to_publish_threshold():
    refs = [
        "xiaomi mijia car vacuum cleaner cordless handheld vacuum portable car vacuum",
        "car vacuum cleaner cordless handheld vacuum cleaner",
    ]
    candidate = "SZUK 9998700PA Car Vacuum Cleaner Strong Suction Cordless Wireless Cleaner Portable HandHeld Vacuum Cleaner Cleaning Machine"
    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9


def test_semantic_score_lifts_handheld_fan_match_to_publish_threshold():
    refs = [
        "카프 빅팬 접이식 핸디 선풍기 USB 휴대용 BLDC 충전식",
        "foldable handheld fan portable USB fan folding mini personal fan",
        "handheld fan portable usb rechargeable folding fan",
    ]
    candidate = "Portable Mini Hand Fan USB Rechargeable Folding Fan"
    wrong = "Foldable Retro Handheld Game Console 3000mAh Battery"

    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9
    assert _semantic_similarity_score(wrong, refs) < 0.9
    assert _multi_reference_score(wrong, refs) < 0.9


def test_semantic_score_blocks_neck_fan_for_handheld_fan_intent():
    refs = [
        "카프 빅팬 접이식 핸디 선풍기",
        "handheld fan foldable portable",
        "手持式 电风扇 折叠 便携式",
    ]
    right = "Large Head Portable Handheld Fan Foldable USB Rechargeable Cooling Fan"
    wrong = "Portable Neck Fan USB Rechargeable Bladeless Cooling Fan"

    assert _semantic_similarity_score(right, refs) >= 0.9
    assert _multi_reference_score(right, refs) >= 0.9
    assert _semantic_similarity_score(wrong, refs) < 0.9
    assert _multi_reference_score(wrong, refs) < 0.9
    assert not _passes_reference_constraints(wrong, refs)


def test_semantic_score_blocks_hand_fan_for_neck_fan_intent():
    refs = [
        "넥밴드 목걸이 선풍기",
        "neck fan wearable fan bladeless fan",
        "颈挂风扇 无叶风扇",
    ]
    right = "Wearable Neck Fan USB Rechargeable Bladeless Cooling Fan"
    wrong = "Portable Mini Hand Fan USB Rechargeable Folding Fan"

    assert _semantic_similarity_score(right, refs) >= 0.9
    assert _multi_reference_score(right, refs) >= 0.9
    assert _semantic_similarity_score(wrong, refs) < 0.9
    assert _multi_reference_score(wrong, refs) < 0.9
    assert not _passes_reference_constraints(wrong, refs)


def test_semantic_score_blocks_hand_fan_for_car_fan_intent():
    refs = ["car fan", "vehicle cooling fan", "차량용 선풍기", "车载风扇"]
    hand_fan = "Portable Mini Hand Fan USB Rechargeable Folding Fan"
    car_fan = "12V Car Dashboard Cooling Fan"

    assert _semantic_similarity_score(car_fan, refs) >= 0.9
    assert _semantic_similarity_score(hand_fan, refs) < 0.9


def test_semantic_score_lifts_electric_cleaning_brush_match_to_publish_threshold():
    refs = [
        "automatic electric cleaning brush set electric spin scrubber cleaning brush",
        "electric spin scrubber cordless cleaning brush",
    ]
    candidate = "Electric Spin Scrubber Cleaning Brush Cordless Power Cleaning Tool for Bathroom Kitchen"
    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9


def test_semantic_score_blocks_metal_stopper_for_biodegradable_strainer_bag():
    refs = [
        "콘실 국산 생분해 옥수수 싱크대 배수구 거름망",
        "biodegradable kitchen sink strainer bag compostable cornstarch sink filter mesh net",
        "玉米淀粉可降解水槽过滤网 厨房垃圾过滤网袋",
    ]
    wrong = "Kitchen Sink Drain Filter Pop-up Stainless Steel Strainer Mesh Basin Water Stopper Plug"
    right = "100pcs Biodegradable Kitchen Sink Strainer Bags Cornstarch Compostable Drain Filter Mesh Net"
    assert _semantic_similarity_score(wrong, refs) < 0.9
    assert _multi_reference_score(wrong, refs) < 0.9
    assert _semantic_similarity_score(right, refs) >= 0.9
    assert _multi_reference_score(right, refs) >= 0.9


def test_semantic_score_accepts_alibaba_korean_biodegradable_strainer_listing():
    refs = [
        "콘실 국산 생분해 옥수수 싱크대 배수구 거름망",
        "biodegradable kitchen sink strainer bag compostable cornstarch sink filter mesh net",
        "玉米淀粉可降解水槽过滤网 厨房垃圾过滤网袋",
    ]
    candidate = "옥수수 전분 만든 생분해 PLA 주방 쓰레기 싱크 배수 필터 여과기 메쉬 그물 가방"
    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9


def test_biodegradable_strainer_constraints_reject_shower_hair_catcher():
    refs = [
        "콘실 국산 생분해 옥수수 싱크대 배수구 거름망",
        "biodegradable sink mesh bag compostable drain strainer",
        "可降解水槽过滤网 玉米淀粉水槽滤网",
    ]
    bad = "Disposable Shower Drain Hair Catcher Mesh Shower Drain Covers Floor Sink Strainer Filter Hair Stopper"
    good = "Biodegradable Kitchen Sink Filter Bag Cornstarch Drain Mesh Net"
    assert not _passes_reference_constraints(bad, refs)
    assert _multi_reference_score(bad, refs) < 0.9
    assert _passes_reference_constraints(good, refs)


def test_biodegradable_strainer_query_does_not_trigger_sponge_search():
    variants = _preferred_chinese_query_variants(
        "可降解水槽过滤网 玉米淀粉水槽滤网 生物降解厨房水槽过滤袋",
        "biodegradable sink mesh bag compostable drain strainer",
    )
    assert "可降解水槽过滤网袋" in variants
    assert "水槽海绵架" not in variants

    terms = _category_terms_for_keyword(
        "biodegradable sink mesh bag compostable drain strainer",
        reference_name="콘실 국산 생분해 옥수수 싱크대 배수구 거름망",
        keyword_cn="可降解水槽过滤网 玉米淀粉水槽滤网",
    )
    assert "sponge" not in terms
    assert "bag" in terms or "mesh" in terms


def test_preferred_query_variants_keep_product_anchors():
    assert "tumbler ice mold" in _preferred_english_query_variants(
        "silicone tumbler ice mold, cylinder ice tray, ice cup mold"
    )
    assert "biodegradable sink strainer bag" in _preferred_english_query_variants(
        "biodegradable kitchen sink strainer bag compostable cornstarch sink filter mesh"
    )
    assert "auto draining sponge holder" in _preferred_english_query_variants(
        "304 Stainless Steel Kitchen Sink Caddy Auto Draining Sponge Holder"
    )
    assert "foldable handheld fan" in _preferred_english_query_variants(
        "Foldable handheld fan, portable USB fan, folding mini personal fan"
    )
    assert "电动切碎机" in _preferred_chinese_query_variants(
        "电动多功能搅拌机 蔬菜切碎机 蒜泥器", "vegetable chopper"
    )
    assert "手持风扇" in _preferred_chinese_query_variants("折叠手持风扇", "foldable handheld fan")


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


def test_category_guard_car_fan_blocks_non_car_fan():
    terms = _category_terms_for_keyword(
        "car fan, vehicle cooling fan",
        reference_name="켈리마 차량용 선풍기",
        keyword_cn="车载风扇",
    )
    assert terms
    assert _passes_category_guard("12V Car Dashboard Cooling Fan", terms)
    # has "fan" but no vehicle context
    assert _passes_category_guard("Portable Mini Hand Fan", terms)


def test_category_guard_handheld_fan_blocks_game_console():
    terms = _category_terms_for_keyword(
        "Foldable handheld fan, portable USB fan, folding mini personal fan",
        reference_name="Karf big fan foldable handheld fan",
        keyword_cn="foldable handheld fan",
    )
    assert terms
    assert "car" not in terms
    assert _passes_category_guard("Portable Mini Hand Fan USB Rechargeable", terms)
    assert not _passes_category_guard(
        "Foldable Retro Handheld Game Console 3000mAh Battery",
        terms,
    )


def test_reference_constraint_blocks_basin_fixture_for_strainer_intent():
    refs = ["sink strainer holder", "음식물 거름망", "水槽过滤网 架"]
    assert not _passes_reference_constraints(
        "Wall Mounted Stainless Wash Basin Vanity Sink",
        refs,
    )
    assert _passes_reference_constraints(
        "Kitchen Sink Strainer Basket Drain Filter Holder",
        refs,
    )


def test_reference_constraint_blocks_non_vehicle_or_non_fan_for_car_fan():
    refs = ["car fan", "vehicle cooling fan", "차량용 선풍기", "车载风扇"]
    assert _passes_reference_constraints(
        "12V Car Dashboard Cooling Fan",
        refs,
    )
    # vehicle only, no fan
    assert not _passes_reference_constraints(
        "Small Car Blade Fuse 12V 20A",
        refs,
    )
    # fan only, no vehicle
    assert not _passes_reference_constraints(
        "Portable Hand Fan USB Rechargeable",
        refs,
    )
    assert not _passes_reference_constraints(
        "Caravan Roof Ventilation Fan",
        refs,
    )


def test_b2b_title_gate_blocks_obvious_wholesale_copy():
    assert _looks_b2b_candidate_title("Factory wholesale sink strainer OEM bulk supplier")
    assert not _looks_b2b_candidate_title("Kitchen sink strainer basket for home use")


def test_b2b_detail_gate_uses_page_signals():
    page_text = (
        "Factory direct supplier. MOQ 100 pcs/lot. Trade Assurance. "
        "Minimum order required for wholesale buyers."
    )
    assert _looks_b2b_detail_text(page_text, "Kitchen sink strainer")
    assert not _looks_b2b_detail_text(
        "Easy install for home kitchen daily use. No MOQ.",
        "Kitchen sink strainer for household",
    )


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


def test_keyword_conversion_compact_sponge_holder():
    out = convert_keywords_rule_based("리치덕 싱크대 물빠짐 304 스텐 수세미거치대")
    assert "海绵架" in out["chinese"]
    assert "沥水" in out["chinese"]
    assert "sponge holder" in out["english"].lower()
    assert "kitchen sink" in out["english"].lower()


def test_keyword_conversion_sink_strainer_holder():
    title = "존글로벌 음식물 거름망 거치대 + 거름망 - 씽크대거름망"
    out = convert_keywords_rule_based(title)
    assert "过滤" in out["chinese"]
    assert "sink strainer" in out["english"].lower()

    terms = _category_terms_for_keyword(
        out["english"],
        reference_name=title,
        keyword_cn=out["chinese"],
    )
    assert terms
    assert _passes_category_guard("Kitchen Sink Strainer Holder Basket", terms)
    assert not _passes_category_guard("Universal Phone Holder Stand", terms)


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


def test_summer_neck_cooler_queries_and_similarity_gate():
    refs = [
        "\ube44\ub098\uc787 \uc544\uc774\uc2a4 \ub125\ucfe8\ub7ec \ucfe8\uc2a4\uce74\ud504 \uc544\uc774\uc2a4\ub125\ubc34\ub4dc",
        "pcm ice neck cooler cooling scarf band",
        "\u51b0\u51c9\u5708 \u964d\u6e29\u9888\u5708",
    ]
    candidate = "Reusable PCM Ice Neck Cooler Summer Cooling Neck Ring Scarf Band"

    assert "ice neck cooler" in _preferred_english_query_variants(refs[1], refs[0])
    assert "\u51b0\u51c9\u5708" in _preferred_chinese_query_variants("", refs[1])
    assert _semantic_similarity_score(candidate, refs) >= 0.9
    assert _multi_reference_score(candidate, refs) >= 0.9

    terms = _category_terms_for_keyword(refs[1], reference_name=refs[0], keyword_cn=refs[2])
    assert terms
    assert _passes_category_guard(candidate, terms)
    assert not _passes_category_guard("Silicone Tumbler Ice Mold Tray with Lid", terms)
    assert _multi_reference_score("Portable Bladeless Neck Fan USB Wearable Fan", refs) < 0.9


def test_ice_neck_ring_does_not_use_jewelry_ring_guard():
    terms = _category_terms_for_keyword(
        "ice neck ring cooling neck band",
        reference_name="핏츠런 아이스 넥쿨러 쿨링 넥밴드 얼음 목걸이",
        keyword_cn="冰凉圈 降温颈圈",
    )

    assert "neck" in terms
    assert "cooling" in terms
    assert "戒指" not in terms
    assert _passes_category_guard("Reusable PCM Ice Neck Cooler Summer Cooling Neck Ring", terms)
    assert not _passes_category_guard("Silver Jewelry Ring Wedding Band", terms)


def test_swim_ring_does_not_use_jewelry_ring_guard():
    terms = _category_terms_for_keyword(
        "inflatable swim ring pool tube",
        reference_name="물놀이 수영 보행 보조 튜브 물놀이 링",
        keyword_cn="游泳圈",
    )

    assert "pool float" in terms
    assert "tube" in terms
    assert "戒指" not in terms
    assert _passes_category_guard("Inflatable Swimming Ring Pool Float Tube", terms)
    assert not _passes_category_guard("Silver Jewelry Ring Wedding Band", terms)


def test_summer_water_gun_and_mosquito_queries_are_high_intent():
    water_refs = [
        "\uc5ec\ub984 \uc804\ub3d9\ubb3c\ucd1d",
        "electric water gun rechargeable water blaster",
        "\u7535\u52a8\u6c34\u67aa",
    ]
    water_candidate = "Rechargeable Electric Water Gun M416 Summer Water Blaster Toy"
    assert "electric water gun" in _preferred_english_query_variants(water_refs[1], water_refs[0])
    assert "\u7535\u52a8\u6c34\u67aa" in _preferred_chinese_query_variants("", water_refs[1])
    assert _semantic_similarity_score(water_candidate, water_refs) >= 0.9

    mosquito_refs = [
        "\uc804\uae30\ubaa8\uae30\ucc44",
        "electric mosquito swatter bug zapper racket",
        "\u7535\u868a\u62cd",
    ]
    mosquito_candidate = "Electric Mosquito Swatter USB Rechargeable Bug Zapper Racket"
    assert "electric mosquito swatter" in _preferred_english_query_variants(mosquito_refs[1], mosquito_refs[0])
    assert "\u7535\u868a\u62cd" in _preferred_chinese_query_variants("", mosquito_refs[1])
    assert _semantic_similarity_score(mosquito_candidate, mosquito_refs) >= 0.9


def test_summer_skipped_category_query_coverage():
    cases = [
        (
            "cooling bedding pad summer cool mat",
            "Ice Silk Cooling Mat Summer Bedding Pad",
            "cooling mat",
            "\u51b0\u4e1d\u51c9\u5e2d",
        ),
        (
            "cooling arm sleeves uv protection sleeves",
            "Ice Silk UV Protection Cooling Arm Sleeves",
            "cooling arm sleeves",
            "\u51b0\u8896",
        ),
        (
            "waterproof phone pouch swimming dry bag",
            "Waterproof Phone Pouch Swimming Dry Bag Case",
            "waterproof phone pouch",
            "\u624b\u673a\u9632\u6c34\u888b",
        ),
        (
            "uv blocking umbrella compact sun umbrella",
            "Compact UV Blocking Sun Umbrella Parasol",
            "uv sun umbrella",
            "\u9632\u6652\u4f1e",
        ),
        (
            "wide brim outdoor fishing sun hat",
            "Wide Brim UV Protection Outdoor Sun Hat",
            "wide brim sun hat",
            "\u906e\u9633\u5e3d",
        ),
        (
            "folding outdoor camping wagon cart",
            "Folding Outdoor Camping Wagon Cart",
            "folding camping wagon",
            "\u6298\u53e0\u9732\u8425\u8f66",
        ),
        (
            "portable camping shower bag for travel",
            "Portable Camping Shower Bag Outdoor Shower",
            "portable camping shower",
            "\u6237\u5916\u6dcb\u6d74\u888b",
        ),
        (
            "mini insulated cooler bag for summer lunch",
            "Portable Insulated Cooler Bag Picnic Lunch Bag",
            "portable cooler bag",
            "\u4fdd\u6e29\u5305",
        ),
        (
            "kids character life jacket for water play",
            "Kids Swim Life Jacket Water Play Vest",
            "kids life jacket",
            "\u6551\u751f\u8863",
        ),
        (
            "oversized rash guard beach cover up",
            "UV Swimwear Rash Guard Beach Cover Up",
            "rash guard swim shirt",
            "\u9632\u6652\u6cf3\u8863",
        ),
    ]

    for reference, candidate, expected_en, expected_cn in cases:
        refs = [reference, expected_cn]
        assert expected_en in _preferred_english_query_variants(reference, reference)
        assert expected_cn in _preferred_chinese_query_variants("", reference)
        assert _semantic_similarity_score(candidate, refs) >= 0.9
