"""
Korean → Chinese/English keyword conversion for product sourcing.
Uses Gemini API when available, falls back to rule-based mapping.
"""
from __future__ import annotations

from typing import Dict, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

# Rule-based fallback mapping
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
    "거치대": {"cn": "支架", "en": "stand"},
    "삼각대": {"cn": "三脚架", "en": "tripod"},
    "수납": {"cn": "收纳", "en": "storage"},
    "정리": {"cn": "整理", "en": "organizer"},
    "방수": {"cn": "防水", "en": "waterproof"},
    "접이식": {"cn": "折叠", "en": "foldable"},
    "휴대용": {"cn": "便携式", "en": "portable"},
}


def convert_keywords_rule_based(product_name: str) -> Dict[str, str]:
    """Rule-based keyword conversion from Korean product name."""
    cn_parts, en_parts = [], []
    for kr, tr in _KEYWORD_MAP.items():
        if kr in product_name:
            if tr["cn"]:
                cn_parts.append(tr["cn"])
            if tr["en"]:
                en_parts.append(tr["en"])

    if not cn_parts or not en_parts:
        # No keyword match — use product name directly as search term
        logger.warning("[KeywordConverter] No rule-based match for: %s", product_name)
        return {
            "chinese": " ".join(cn_parts) if cn_parts else product_name,
            "english": " ".join(en_parts) if en_parts else product_name,
        }

    return {
        "chinese": " ".join(cn_parts),
        "english": " ".join(en_parts),
    }


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

        response = await gemini_client.generate_content_async(prompt)
        text = response.text.strip()

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
