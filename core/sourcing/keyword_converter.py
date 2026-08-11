"""
Korean → Chinese/English keyword conversion for product sourcing.
Uses Gemini API when available, falls back to rule-based mapping.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Dict, List, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

# Compound priority dictionary: kept first because compound terms produce far better
# search results than the sum of their parts. Every entry here is a literal substring
# scan against the Korean product title — if it hits, we use ONLY the compound terms.
_COMPOUND_MAP = {
    # Live platform-video families. Keep the native Chinese shopping phrase as
    # one token so exact translated intent is the first Douyin/XHS/Kuaishou
    # query even when Gemini is unavailable or quota-limited.
    "휴대용 믹서기": {"cn": "便携式无线榨汁杯 搅拌机", "en": "portable wireless blender cup"},
    "텀블러 믹서기": {"cn": "便携式无线榨汁杯 搅拌机", "en": "portable wireless blender cup"},
    "자동 디스펜서": {"cn": "自动泡沫洗手机 自动皂液器", "en": "automatic foam soap dispenser"},
    "거품비누 손세정기": {"cn": "自动泡沫洗手机 自动皂液器", "en": "automatic foam soap dispenser"},
    "휴대용 핸디형 스팀다리미": {"cn": "手持挂烫机 便携式蒸汽熨斗", "en": "portable handheld garment steamer"},
    "핸디형 스팀다리미": {"cn": "手持挂烫机 便携式蒸汽熨斗", "en": "handheld garment steamer"},
    "미니 가습기": {"cn": "迷你加湿器", "en": "mini humidifier"},
    "전동 와인 오프너": {"cn": "电动红酒开瓶器", "en": "electric wine opener"},
    "마늘 야채": {"cn": "无线电动蒜泥器 食物绞肉机", "en": "wireless garlic food chopper"},
    "모션 센서등": {"cn": "人体感应灯 充电式LED灯", "en": "motion sensor rechargeable light"},
    "동작감지 스마트 조명": {"cn": "人体感应灯 充电式LED灯", "en": "motion sensor rechargeable light"},
    "반려동물 스팀 브러쉬": {"cn": "宠物蒸汽梳 猫狗除毛刷", "en": "pet steam brush"},
    "스팀 강아지 고양이": {"cn": "宠物蒸汽梳 猫狗除毛刷", "en": "pet steam brush"},
    "반려동물 빗": {"cn": "宠物蒸汽梳 猫狗除毛刷", "en": "pet steam brush"},
    "접이식 노트북 거치대": {"cn": "折叠笔记本电脑支架", "en": "foldable laptop stand"},
    "목걸이 선풍기": {"cn": "挂脖风扇", "en": "neck fan"},
    "목 선풍기": {"cn": "挂脖风扇", "en": "neck fan"},
    # 실제 원본 탐색에 자주 쓰이는 전자 소형가전. 한국 판매자가 붙인 브랜드는
    # 아래 identity-token 단계에서 보존하고, 여기서는 중국 판매자 핵심명으로 번역한다.
    "욕실 청소기": {"cn": "电动浴室清洁刷", "en": "electric bathroom cleaning brush"},
    "화장실 청소기": {"cn": "电动浴室清洁刷", "en": "electric bathroom cleaning brush"},
    "휴대용 선풍기": {"cn": "便携式手持风扇", "en": "portable handheld fan"},
    "우유 거품기": {"cn": "电动奶泡器", "en": "electric milk frother"},
    "전동 휘핑기": {"cn": "电动打蛋器", "en": "electric whisk"},
    "무선 미니 청소기": {"cn": "无线迷你吸尘器", "en": "cordless mini vacuum cleaner"},
    "에어건 진공": {"cn": "吹吸一体吸尘器", "en": "vacuum cleaner air duster 2 in 1"},
    # 주방 — 수세미 / 식기 류
    "물빠짐 수세미": {"cn": "海绵架 沥水架", "en": "sponge holder kitchen sink"},
    "수세미거치대": {"cn": "海绵架 沥水架", "en": "sponge holder kitchen sink"},
    "수세미 거치대": {"cn": "海绵架 沥水架", "en": "sponge holder kitchen sink"},
    "수세미걸이": {"cn": "海绵架", "en": "sponge holder"},
    "수세미 받침": {"cn": "海绵沥水架", "en": "sponge drainer"},
    "수세미": {"cn": "海绵刷", "en": "dish sponge"},
    "음식물 거름망": {"cn": "水槽过滤网 架", "en": "sink strainer holder"},
    "거름망 거치대": {"cn": "水槽过滤网架", "en": "sink strainer holder"},
    "씽크대거름망": {"cn": "水槽过滤网", "en": "sink strainer"},
    "싱크대거름망": {"cn": "水槽过滤网", "en": "sink strainer"},
    "싱크대 거름망": {"cn": "水槽过滤网", "en": "sink strainer"},
    "주방 수전": {"cn": "厨房水龙头", "en": "kitchen faucet"},
    "주방 선반": {"cn": "厨房置物架", "en": "kitchen shelf"},
    "주방용품": {"cn": "厨房用品", "en": "kitchen tool"},
    "식기 정리": {"cn": "餐具沥水架", "en": "dish drying rack"},
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

    # 여름 / 야외 / 해충 (풀자동화 여름 큐 카테고리)
    "모기 퇴치기": {"cn": "灭蚊灯", "en": "mosquito killer lamp"},
    "모기퇴치기": {"cn": "灭蚊灯", "en": "mosquito killer lamp"},
    "포충기": {"cn": "灭蚊灯 捕虫器", "en": "bug zapper"},
    "해충퇴치기": {"cn": "驱虫器", "en": "pest repeller"},
    "해충퇴치": {"cn": "驱虫", "en": "pest control"},
    "모기장": {"cn": "蚊帐", "en": "mosquito net"},
    "모기채": {"cn": "电蚊拍", "en": "electric mosquito swatter"},
    "벌레퇴치": {"cn": "驱虫", "en": "bug repellent"},
    "쿨토시": {"cn": "冰袖", "en": "cooling arm sleeves"},
    "팔토시": {"cn": "冰袖 防晒袖套", "en": "arm sleeves uv protection"},
    "쿨링 셔츠": {"cn": "凉感T恤", "en": "cooling shirt"},
    "냉감 셔츠": {"cn": "凉感T恤", "en": "cooling shirt"},
    "쿨링 티셔츠": {"cn": "凉感T恤 速干", "en": "cooling t-shirt quick dry"},
    "냉감 티셔츠": {"cn": "凉感T恤 速干", "en": "cooling t-shirt quick dry"},
    "쿨링 반팔": {"cn": "凉感T恤 短袖", "en": "cooling short sleeve"},
    "기능성 티셔츠": {"cn": "速干T恤", "en": "quick dry shirt"},
    "쿨매트": {"cn": "凉席 冰垫", "en": "cooling mat"},
    "아이스 조끼": {"cn": "降温背心", "en": "cooling vest"},

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

_MODIFIER_MAP = {
    "304": {"cn": "304 不锈钢", "en": "304 stainless steel"},
    "스테인리스": {"cn": "不锈钢", "en": "stainless steel"},
    "스테인레스": {"cn": "不锈钢", "en": "stainless steel"},
    "올스텐": {"cn": "全不锈钢", "en": "stainless steel"},
    "스텐": {"cn": "不锈钢", "en": "stainless steel"},
    "접착식": {"cn": "粘贴式 免打孔", "en": "adhesive wall mounted"},
    "접착": {"cn": "粘贴式", "en": "adhesive"},
    "다용도": {"cn": "多功能", "en": "multipurpose"},
    "실버": {"cn": "银色", "en": "silver"},
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


def _identity_tokens(product_name: str, language: str) -> List[str]:
    """Keep brand/model/spec/option tokens that identify the exact SKU.

    Chinese marketplace originals are often found by a translated family noun
    plus an unchanged private-label/model token.  Counts and generations are
    also product options, not disposable marketing words.
    """
    text = str(product_name or "")
    out: List[str] = []

    def add(value: str) -> None:
        value = " ".join(str(value or "").split())
        if value and value.lower() not in {item.lower() for item in out}:
            out.append(value)

    for token in re.findall(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9-]{1,})(?![A-Za-z0-9])", text):
        add(token)

    patterns = (
        (r"(?<!\d)(\d+)\s*세대", lambda n: f"{n}代" if language == "cn" else f"{n}nd-generation"),
        (r"(?<!\d)(\d+)\s*단(?!\w)", lambda n: f"{n}档" if language == "cn" else f"{n}-speed"),
        (r"(?<!\d)(\d+)\s*(?:개입|매입)(?!\w)", lambda n: f"{n}个装" if language == "cn" else f"{n}pcs"),
        (r"(?<!\d)(\d+)\s*in\s*1(?!\d)", lambda n: f"{n}合1" if language == "cn" else f"{n}-in-1"),
    )
    for pattern, render in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            add(render(match.group(1)))

    for value, unit in re.findall(
        r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mah|ah|v|w|ml|l|cm|mm)(?!\w)",
        text,
        re.IGNORECASE,
    ):
        add(f"{value}{unit.upper()}")
    return out


def _append_identity_tokens(base: str, product_name: str, language: str) -> str:
    result = " ".join(str(base or "").split())
    for token in _identity_tokens(product_name, language):
        if token.lower() not in result.lower():
            result = f"{result} {token}".strip()
    return result


def _sanitize_search_phrase(value: str) -> str:
    """Remove Korean annotations Gemini sometimes echoes beside translations."""
    without_hangul = re.sub(r"[가-힣]+", " ", str(value or ""))
    return " ".join(without_hangul.split()).strip(" ,;/")


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

    # Pass 3: attribute modifiers always apply, even when a compound matched.
    # This keeps "수세미거치대" from losing critical qualifiers like
    # "304 스텐" or "접착식", which otherwise allows broad silicone tray videos.
    for kr, tr in _MODIFIER_MAP.items():
        if kr in product_name:
            if tr["cn"]:
                cn_parts.append(tr["cn"])
            if tr["en"]:
                en_parts.append(tr["en"])

    # De-duplicate at TOKEN level while preserving order — 여러 컴파운드가 같은
    # 단어를 공유하면("灭蚊灯" + "灭蚊灯 捕虫器") 그대로 join 시 중복 토큰이 생겨
    # 검색 쿼리가 과잉·중복돼 결과가 나빠진다. 토큰 수도 검색 친화적으로 제한.
    def _uniq_join(items, max_tokens: int = 4):
        seen, out = set(), []
        for it in items:
            for tok in str(it or "").split():
                if tok and tok not in seen:
                    out.append(tok)
                    seen.add(tok)
                if len(out) >= max_tokens:
                    break
            if len(out) >= max_tokens:
                break
        return " ".join(out).strip()

    cn = _sanitize_search_phrase(
        _append_identity_tokens(_uniq_join(cn_parts, max_tokens=8), product_name, "cn")
    )
    en = _sanitize_search_phrase(_append_identity_tokens(
        _uniq_join(en_parts, max_tokens=10) or _extract_latin_tokens(product_name),
        product_name,
        "en",
    ))

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

        model_name = getattr(config, "GEMINI_TEXT_MODEL", "gemini-3.5-flash")
        loop = asyncio.get_running_loop()

        def _build_model_fallback_chain(primary: str) -> List[str]:
            chain: List[str] = []

            def _add(name: str):
                n = (name or "").strip()
                if n and n not in chain:
                    chain.append(n)

            _add(primary)
            # Optional env override for emergency rollout without code edit.
            for env_name in os.getenv("GEMINI_TEXT_MODEL_FALLBACKS", "").split(","):
                _add(env_name)
            # Fallback chain for current + previous stable/preview generations.
            _add("gemini-3.5-flash")
            _add("gemini-3.1-pro-preview")
            _add("gemini-3.1-flash-lite")
            _add("gemini-2.5-pro")
            _add("gemini-2.5-flash")
            _add("gemini-flash-latest")
            return chain

        def _is_model_not_found_error(exc: Exception) -> bool:
            msg = str(exc).lower()
            return (
                ("404" in msg and "not_found" in msg)
                or "model not found" in msg
                or "no longer available to new users" in msg
            )

        model_chain = _build_model_fallback_chain(model_name)
        last_error: Optional[Exception] = None
        for idx, candidate_model in enumerate(model_chain, start=1):
            def _call(model: str = candidate_model):
                return models.generate_content(model=model, contents=prompt)

            try:
                response = await loop.run_in_executor(None, _call)
                text = str(getattr(response, "text", "") or "").strip()
                if candidate_model != model_name:
                    logger.info(
                        "[KeywordConverter] Gemini model fallback: %s -> %s",
                        model_name,
                        candidate_model,
                    )
                return text
            except Exception as e:
                last_error = e
                # Retry only when the model itself is unavailable.
                if idx < len(model_chain) and _is_model_not_found_error(e):
                    logger.warning(
                        "[KeywordConverter] Model unavailable (%s), trying next fallback model",
                        candidate_model,
                    )
                    continue
                break

        if last_error:
            raise last_error
        return ""

    if hasattr(gemini_client, "generate_content"):
        loop = asyncio.get_running_loop()
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
            f"다음 한국어 상품명을 중국 판매 사이트에서 원본 상품을 찾을 수 있도록 "
            f"간체 중국어와 영어의 고정밀 검색 문구로 번역해줘. "
            f"상품명: \"{product_name}\"\n\n"
            f"반드시 아래 형식으로만 답해:\n"
            f"chinese: [중국어 키워드]\n"
            f"english: [영어 키워드]\n\n"
            f"중국어는 상품 종류·세부 형태·기능을 직역하고, 브랜드/모델명, 세대, "
            f"숫자, 크기, 전압, 구성 수량(예: 500개입)은 절대 빼거나 바꾸지 마. "
            f"최고/인기 같은 판매 문구만 제외해."
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
            cn = _sanitize_search_phrase(_append_identity_tokens(cn, product_name, "cn"))
            en = _sanitize_search_phrase(_append_identity_tokens(en, product_name, "en"))
            logger.info("[KeywordConverter] Gemini: cn=%s en=%s", cn[:40], en[:40])
            return {"chinese": cn, "english": en}

        logger.warning("[KeywordConverter] Gemini response parse failed, fallback to rules")
        return convert_keywords_rule_based(product_name)

    except Exception as e:
        logger.warning("[KeywordConverter] Gemini error: %s, fallback to rules", e)
        return convert_keywords_rule_based(product_name)
