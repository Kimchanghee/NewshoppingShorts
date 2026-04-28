"""
Korean → Chinese/English keyword conversion for product sourcing.
Uses Gemini API when available, falls back to rule-based mapping.
"""
from __future__ import annotations

import asyncio
from typing import Dict, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

# Compound priority dictionary: kept first because compound terms produce far better
# search results than the sum of their parts. Every entry here is a literal substring
# scan against the Korean product title — if it hits, we use ONLY the compound terms.
_COMPOUND_MAP = {
    # 주방 — 수세미 / 식기 류
    "물빠짐 수세미": {"cn": "海绵架 沥水架", "en": "sponge holder kitchen sink"},
    "수세미거치대": {"cn": "海绵架 沥水架", "en": "sponge holder kitchen sink"},
    "수세미 거치대": {"cn": "海绵架 沥水架", "en": "sponge holder kitchen sink"},
    "수세미걸이": {"cn": "海绵架", "en": "sponge holder"},
    "수세미 받침": {"cn": "海绵沥水架", "en": "sponge drainer"},
    "수세미": {"cn": "海绵刷", "en": "dish sponge"},
    "주방 수전": {"cn": "厨房水龙头", "en": "kitchen faucet"},
    "주방 선반": {"cn": "厨房置物架", "en": "kitchen shelf"},
    "주방용품": {"cn": "厨房用品", "en": "kitchen tool"},
    "도마": {"cn": "砧板", "en": "cutting board"},
    "식기 정리": {"cn": "餐具沥水架", "en": "dish drying rack"},
    "식기건조대": {"cn": "碗碟架", "en": "dish drying rack"},
    "행주걸이": {"cn": "毛巾架", "en": "towel rack"},
    "물비누 디스펜서": {"cn": "皂液器", "en": "soap dispenser"},
    "양념 정리함": {"cn": "调味料收纳盒", "en": "spice rack"},

    # 정리 / 수납
    "수납 정리함": {"cn": "收纳整理盒", "en": "storage organizer"},
    "수납 박스": {"cn": "收纳盒", "en": "storage box"},
    "옷걸이": {"cn": "衣架", "en": "clothes hanger"},
    "신발 정리": {"cn": "鞋架", "en": "shoe rack"},
    "케이블 정리": {"cn": "理线器", "en": "cable organizer"},
    "서랍 정리": {"cn": "抽屉收纳", "en": "drawer organizer"},
    "냉장고 정리": {"cn": "冰箱收纳盒", "en": "fridge organizer"},
    "계란 정리": {"cn": "鸡蛋收纳盒", "en": "egg holder"},

    # 욕실
    "욕실 선반": {"cn": "浴室置物架", "en": "bathroom shelf"},
    "샤워기": {"cn": "花洒", "en": "shower head"},
    "샤워 거치대": {"cn": "花洒支架", "en": "shower holder"},
    "치약 짜개": {"cn": "牙膏挤压器", "en": "toothpaste squeezer"},
    "칫솔 살균": {"cn": "牙刷消毒", "en": "toothbrush sanitizer"},

    # 휴대폰 / 디지털 (phone stand 같은 동음이의 분리용)
    "휴대폰 거치대": {"cn": "手机支架", "en": "phone stand"},
    "차량 거치대": {"cn": "车载支架", "en": "car phone mount"},
    "태블릿 거치대": {"cn": "平板支架", "en": "tablet stand"},
    "맥세이프": {"cn": "MagSafe", "en": "magsafe"},
    "그립톡": {"cn": "手机指环", "en": "phone ring grip"},

    # 도마 / 칼 / 조리도구
    "양면 도마": {"cn": "双面砧板", "en": "double sided cutting board"},
    "스텐 도마": {"cn": "不锈钢砧板", "en": "stainless steel cutting board"},
    "실리콘 도마": {"cn": "硅胶砧板", "en": "silicone cutting board"},
    "나무 도마": {"cn": "木砧板", "en": "wooden cutting board"},
    "도마": {"cn": "砧板 切菜板", "en": "cutting board chopping board"},
    "조리도구": {"cn": "厨房工具", "en": "kitchen utensil set"},
    "주방칼": {"cn": "厨刀", "en": "kitchen knife"},
    "가위": {"cn": "厨房剪刀", "en": "kitchen scissors"},

    # 식기건조대 / 설거지
    "식기건조대 와이드": {"cn": "宽款碗碟架", "en": "wide dish drying rack"},
    "3단 식기건조대": {"cn": "三层碗碟架", "en": "3 tier dish drying rack"},
    "창문형 식기건조대": {"cn": "窗户型碗碟架", "en": "window dish rack"},
    "식기건조대": {"cn": "碗碟架 沥水架", "en": "dish drying rack"},
    "그릇 정리": {"cn": "碗碟收纳架", "en": "dish organizer"},

    # 양념통 / 조미료
    "양념통 세트": {"cn": "调味料盒套装", "en": "spice container set"},
    "조미료통": {"cn": "调味罐", "en": "seasoning jar"},
    "습기방지 양념통": {"cn": "防潮调味盒", "en": "airtight spice container"},
    "후추통": {"cn": "胡椒罐", "en": "pepper grinder"},

    # 후크 / 걸이
    "주방 후크": {"cn": "厨房挂钩", "en": "kitchen hook"},
    "강력 후크": {"cn": "强力粘钩", "en": "heavy duty hook"},

    # 주방 — 다지기 / 채칼 / 슬라이서 (cross-category trap heavy)
    "야채 다지기": {"cn": "蔬菜切碎器", "en": "vegetable chopper"},
    "야채 채칼": {"cn": "蔬菜切丝器", "en": "vegetable slicer grater"},
    "다용도 채칼": {"cn": "多功能切丝器", "en": "multi vegetable slicer"},
    "마늘 다지기": {"cn": "蒜泥器", "en": "garlic press"},
    "양파 다지기": {"cn": "洋葱切碎器", "en": "onion chopper"},
    "감자 채칼": {"cn": "土豆切丝器", "en": "potato slicer"},
    "스텐 채칼": {"cn": "不锈钢切丝器", "en": "stainless steel slicer"},
    "필러": {"cn": "削皮器", "en": "peeler"},
    "감자 필러": {"cn": "土豆削皮器", "en": "potato peeler"},
    "강판": {"cn": "刨丝器", "en": "grater"},
    "치즈 강판": {"cn": "奶酪刨丝器", "en": "cheese grater"},

    # 주방 — 가위 / 칼 / 숫돌
    "주방 가위": {"cn": "厨房剪刀", "en": "kitchen scissors"},
    "다용도 가위": {"cn": "多功能剪刀", "en": "multipurpose kitchen scissors"},
    "스텐 가위": {"cn": "不锈钢剪刀", "en": "stainless steel scissors"},
    "칼갈이": {"cn": "磨刀器", "en": "knife sharpener"},
    "숫돌": {"cn": "磨刀石", "en": "knife sharpening stone"},

    # 주방 — 거품기 / 뒤집개 / 주걱 / 집게
    "거품기": {"cn": "打蛋器", "en": "egg whisk"},
    "수동 거품기": {"cn": "手动打蛋器", "en": "manual whisk"},
    "전동 거품기": {"cn": "电动打蛋器", "en": "electric whisk"},
    "뒤집개": {"cn": "锅铲 煎铲", "en": "spatula turner"},
    "실리콘 주걱": {"cn": "硅胶刮刀", "en": "silicone spatula"},
    "스텐 주걱": {"cn": "不锈钢锅铲", "en": "stainless steel spatula"},
    "밥주걱": {"cn": "饭勺", "en": "rice scoop"},
    "국자": {"cn": "汤勺", "en": "ladle"},
    "집게": {"cn": "食物夹", "en": "kitchen tongs"},
    "밀대": {"cn": "擀面杖", "en": "rolling pin"},

    # 주방 — 만두 / 베이킹
    "만두 메이커": {"cn": "饺子模具", "en": "dumpling maker mold"},
    "만두피 메이커": {"cn": "饺子皮模具", "en": "dumpling skin maker"},
    "쿠키 커터": {"cn": "饼干模具", "en": "cookie cutter"},
    "케이크 몰드": {"cn": "蛋糕模具", "en": "cake mold"},
    "실리콘 몰드": {"cn": "硅胶模具", "en": "silicone mold"},

    # 주방 — 냄비 / 팬
    "프라이팬": {"cn": "煎锅 平底锅", "en": "frying pan"},
    "누룽지팬": {"cn": "锅巴煎锅", "en": "scorched rice pan"},
    "찜기": {"cn": "蒸锅", "en": "steamer pot"},
    "스텐 냄비": {"cn": "不锈钢锅", "en": "stainless steel pot"},
    "주방 냄비": {"cn": "厨房锅", "en": "kitchen pot"},
    "전기 주전자": {"cn": "电水壶", "en": "electric kettle"},

    # 주방 — 얼음 / 음료
    "얼음틀": {"cn": "冰格 制冰盒", "en": "ice cube tray"},
    "실리콘 얼음틀": {"cn": "硅胶冰格", "en": "silicone ice tray"},
    "텀블러": {"cn": "随行杯", "en": "tumbler cup"},
    "물병": {"cn": "水壶 水瓶", "en": "water bottle"},
    "보온병": {"cn": "保温瓶", "en": "thermos bottle"},

    # 주방 — 수동 착즙 / 분쇄
    "수동 착즙기": {"cn": "手动榨汁机", "en": "manual juicer"},
    "착즙기": {"cn": "榨汁机", "en": "juicer"},
    "후추 그라인더": {"cn": "胡椒研磨器", "en": "pepper grinder"},
    "그라인더": {"cn": "研磨器", "en": "grinder"},

    # 주방 — 식품 보관 / 도시락
    "밀폐 용기": {"cn": "密封盒", "en": "airtight food container"},
    "반찬통": {"cn": "保鲜盒", "en": "side dish container"},
    "유리 보관함": {"cn": "玻璃保鲜盒", "en": "glass food container"},
    "도시락통": {"cn": "便当盒", "en": "lunch box"},
    "도시락": {"cn": "便当盒", "en": "lunch box"},

    # 주방 — 청소 / 세정
    "주방 솔": {"cn": "厨房刷", "en": "kitchen brush"},
    "병 솔": {"cn": "瓶刷", "en": "bottle brush"},
    "배수구 거름망": {"cn": "下水道过滤网", "en": "drain strainer"},
    "싱크대 거름망": {"cn": "水槽过滤网", "en": "sink strainer"},

    # 냉장고 / 정리 (kitchen-adjacent)
    "냉장고 정리함": {"cn": "冰箱收纳盒", "en": "fridge organizer container"},
    "야채 보관함": {"cn": "蔬菜保鲜盒", "en": "vegetable storage container"},
    "양념 보관함": {"cn": "调料保鲜盒", "en": "spice storage container"},
}

# Single-word fallback mapping
_KEYWORD_MAP = {
    "청소기": {"cn": "吸尘器", "en": "vacuum cleaner"},
    "무선": {"cn": "无线", "en": "wireless"},
    "핸디": {"cn": "手持式", "en": "handheld"},
    "미니": {"cn": "迷你", "en": "mini"},
    "차량용": {"cn": "车载", "en": "car"},
    "소형": {"cn": "小型", "en": "portable"},
    "충전": {"cn": "充电式", "en": "rechargeable"},
    "물걸레": {"cn": "拖把", "en": "mop"},
    "스틱": {"cn": "立式", "en": "stick"},
    "진공": {"cn": "真空", "en": "vacuum"},
    "로봇": {"cn": "机器人", "en": "robot"},
    "가습기": {"cn": "加湿器", "en": "humidifier"},
    "제습기": {"cn": "除湿机", "en": "dehumidifier"},
    "선풍기": {"cn": "电风扇", "en": "fan"},
    "에어컨": {"cn": "空调", "en": "air conditioner"},
    "냉풍기": {"cn": "冷风机", "en": "air cooler"},
    "공기청정기": {"cn": "空气净化器", "en": "air purifier"},
    "다리미": {"cn": "熨斗", "en": "iron"},
    "건조기": {"cn": "烘干机", "en": "dryer"},
    "전동": {"cn": "电动", "en": "electric"},
    "블렌더": {"cn": "搅拌机", "en": "blender"},
    "믹서기": {"cn": "搅拌机", "en": "mixer"},
    "커피머신": {"cn": "咖啡机", "en": "coffee machine"},
    "헤어드라이기": {"cn": "吹风机", "en": "hair dryer"},
    "면도기": {"cn": "剃须刀", "en": "shaver"},
    "마사지기": {"cn": "按摩器", "en": "massager"},
    "체중계": {"cn": "体重秤", "en": "scale"},
    "LED": {"cn": "LED", "en": "LED"},
    "조명": {"cn": "灯", "en": "light"},
    "스피커": {"cn": "音箱", "en": "speaker"},
    "이어폰": {"cn": "耳机", "en": "earphone"},
    "헤드셋": {"cn": "耳机", "en": "headset"},
    "키보드": {"cn": "键盘", "en": "keyboard"},
    "마우스": {"cn": "鼠标", "en": "mouse"},
    "충전기": {"cn": "充电器", "en": "charger"},
    "보조배터리": {"cn": "充电宝", "en": "power bank"},
    "케이스": {"cn": "保护壳", "en": "case"},
    "거치대": {"cn": "支架", "en": "holder"},
    "삼각대": {"cn": "三脚架", "en": "tripod"},
    "수납": {"cn": "收纳盒", "en": "storage"},
    "정리": {"cn": "整理", "en": "organizer"},
    "정리함": {"cn": "整理盒", "en": "organizer box"},
    "방수": {"cn": "防水", "en": "waterproof"},
    "접이식": {"cn": "折叠", "en": "foldable"},
    "휴대용": {"cn": "便携式", "en": "portable"},
    "스테인리스": {"cn": "不锈钢", "en": "stainless steel"},
    "올스텐": {"cn": "全不锈钢", "en": "stainless steel"},
    "스텐": {"cn": "不锈钢", "en": "stainless steel"},
    "물빠짐": {"cn": "沥水", "en": "drainage"},
    "걸이": {"cn": "挂钩", "en": "hook"},
    "받침": {"cn": "底座", "en": "tray"},
    "선반": {"cn": "置物架", "en": "shelf"},
    "주방": {"cn": "厨房", "en": "kitchen"},
    "욕실": {"cn": "浴室", "en": "bathroom"},
    "냉장고": {"cn": "冰箱", "en": "fridge"},
    "옷장": {"cn": "衣柜", "en": "wardrobe"},
    "후크": {"cn": "挂钩", "en": "hook"},
}


def _extract_latin_tokens(name: str) -> str:
    """Pull ASCII / Latin tokens from a Korean product title.

    1688 is a Chinese site so Korean text is useless there, but AliExpress
    sometimes accepts Latin brand/spec tokens (e.g. "TWS earbuds 5.4").
    """
    import re
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]+", name)
    # Drop ultra-short noise tokens (e.g. "A", "x")
    tokens = [t for t in tokens if len(t) >= 2]
    return " ".join(tokens[:6]).strip()


def convert_keywords_rule_based(product_name: str) -> Dict[str, str]:
    """Rule-based keyword conversion from Korean product name.

    Strategy: compound matches WIN. If we find e.g. "수세미 거치대" we use only
    "sponge holder" — never fall through to single-word "거치대 → stand" which
    would catch phone stands. Falls back to single-word matches only if no
    compound term applies.

    Returns empty strings for the language(s) we couldn't resolve.
    """
    cn_parts, en_parts = [], []
    matched_compound = False

    # Pass 1: compound terms (literal substring scan, multiple may apply)
    for kr, tr in _COMPOUND_MAP.items():
        if kr in product_name:
            if tr["cn"]:
                cn_parts.append(tr["cn"])
            if tr["en"]:
                en_parts.append(tr["en"])
            matched_compound = True

    # Pass 2: single-word fallback only if no compound matched
    if not matched_compound:
        for kr, tr in _KEYWORD_MAP.items():
            if kr in product_name:
                if tr["cn"]:
                    cn_parts.append(tr["cn"])
                if tr["en"]:
                    en_parts.append(tr["en"])

    # De-duplicate while preserving order (compound terms may share words like 不锈钢)
    def _uniq_join(items):
        seen, out = set(), []
        for it in items:
            if it not in seen:
                out.append(it)
                seen.add(it)
        return " ".join(out).strip()

    cn = _uniq_join(cn_parts)
    en = _uniq_join(en_parts) or _extract_latin_tokens(product_name)

    if not cn or not en:
        logger.warning(
            "[KeywordConverter] Partial rule-based match (cn=%r en=%r) for: %s",
            cn, en, product_name,
        )
    else:
        logger.info(
            "[KeywordConverter] Rule-based hit (compound=%s) cn=%r en=%r",
            matched_compound, cn, en,
        )

    return {"chinese": cn, "english": en}


async def generate_content_text(gemini_client: object, prompt: str) -> str:
    """Return text from either the app async wrapper or google-genai Client."""
    if not gemini_client:
        return ""

    if hasattr(gemini_client, "generate_content_async"):
        response = await gemini_client.generate_content_async(prompt)
        return str(getattr(response, "text", "") or "").strip()

    models = getattr(gemini_client, "models", None)
    if models is not None and hasattr(models, "generate_content"):
        import config

        model_name = getattr(config, "GEMINI_TEXT_MODEL", "gemini-2.0-flash")
        loop = asyncio.get_event_loop()

        def _call():
            return models.generate_content(model=model_name, contents=prompt)

        response = await loop.run_in_executor(None, _call)
        return str(getattr(response, "text", "") or "").strip()

    if hasattr(gemini_client, "generate_content"):
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: gemini_client.generate_content(prompt))
        return str(getattr(response, "text", "") or "").strip()

    return ""


async def convert_keywords_gemini(product_name: str, gemini_client: Optional[object] = None) -> Dict[str, str]:
    """
    Use Gemini API to convert Korean product name to Chinese + English search keywords.
    Falls back to rule-based if Gemini is unavailable.
    """
    if not gemini_client:
        logger.info("[KeywordConverter] No Gemini client, using rule-based conversion")
        return convert_keywords_rule_based(product_name)

    try:
        prompt = (
            f"다음 한국어 상품명을 중국어와 영어 검색 키워드로 변환해줘. "
            f"상품명: \"{product_name}\"\n\n"
            f"반드시 아래 형식으로만 답해:\n"
            f"chinese: [중국어 키워드]\n"
            f"english: [영어 키워드]\n\n"
            f"브랜드명은 제외하고 상품 카테고리/특성 위주로."
        )

        text = await generate_content_text(gemini_client, prompt)
        if not text:
            logger.warning("[KeywordConverter] Gemini client unsupported/empty, fallback to rules")
            return convert_keywords_rule_based(product_name)

        cn = ""
        en = ""
        for line in text.split("\n"):
            line = line.strip()
            if line.lower().startswith("chinese:"):
                cn = line.split(":", 1)[1].strip()
            elif line.lower().startswith("english:"):
                en = line.split(":", 1)[1].strip()

        if cn and en:
            logger.info("[KeywordConverter] Gemini: cn=%s en=%s", cn[:40], en[:40])
            return {"chinese": cn, "english": en}

        logger.warning("[KeywordConverter] Gemini response parse failed, fallback to rules")
        return convert_keywords_rule_based(product_name)

    except Exception as e:
        logger.warning("[KeywordConverter] Gemini error: %s, fallback to rules", e)
        return convert_keywords_rule_based(product_name)
