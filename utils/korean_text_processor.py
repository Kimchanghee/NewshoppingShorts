"""
Korean Text Processor - Converts numbers to natural Korean and ensures Hangul-only output

This module handles:
- Converting Arabic numerals to natural Korean words (7개 → 일곱 개)
- Removing/converting non-Hangul characters
- Ensuring TTS-friendly Korean text output
"""

import re
from typing import Optional

# 고유어 숫자 (하나, 둘, 셋...) - 개, 명, 마리, 번 등의 단위와 함께 사용
NATIVE_KOREAN_NUMBERS = {
    1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯",
    6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열",
    11: "열한", 12: "열두", 13: "열세", 14: "열네", 15: "열다섯",
    16: "열여섯", 17: "열일곱", 18: "열여덟", 19: "열아홉", 20: "스물",
    21: "스물한", 22: "스물두", 23: "스물세", 24: "스물네", 25: "스물다섯",
    26: "스물여섯", 27: "스물일곱", 28: "스물여덟", 29: "스물아홉", 30: "서른",
    31: "서른한", 32: "서른두", 33: "서른세", 34: "서른네", 35: "서른다섯",
    36: "서른여섯", 37: "서른일곱", 38: "서른여덟", 39: "서른아홉", 40: "마흔",
    41: "마흔한", 42: "마흔두", 43: "마흔세", 44: "마흔네", 45: "마흔다섯",
    46: "마흔여섯", 47: "마흔일곱", 48: "마흔여덟", 49: "마흔아홉", 50: "쉰",
    51: "쉰한", 52: "쉰두", 53: "쉰세", 54: "쉰네", 55: "쉰다섯",
    56: "쉰여섯", 57: "쉰일곱", 58: "쉰여덟", 59: "쉰아홉", 60: "예순",
    61: "예순한", 62: "예순두", 63: "예순세", 64: "예순네", 65: "예순다섯",
    66: "예순여섯", 67: "예순일곱", 68: "예순여덟", 69: "예순아홉", 70: "일흔",
    71: "일흔한", 72: "일흔두", 73: "일흔세", 74: "일흔네", 75: "일흔다섯",
    76: "일흔여섯", 77: "일흔일곱", 78: "일흔여덟", 79: "일흔아홉", 80: "여든",
    81: "여든한", 82: "여든두", 83: "여든세", 84: "여든네", 85: "여든다섯",
    86: "여든여섯", 87: "여든일곱", 88: "여든여덟", 89: "여든아홉", 90: "아흔",
    91: "아흔한", 92: "아흔두", 93: "아흔세", 94: "아흔네", 95: "아흔다섯",
    96: "아흔여섯", 97: "아흔일곱", 98: "아흔여덟", 99: "아흔아홉"
}

# 한자어 숫자 (일, 이, 삼...) - 원, 년, 월, 일(날짜), 퍼센트 등과 함께 사용
SINO_KOREAN_DIGITS = {
    0: "", 1: "일", 2: "이", 3: "삼", 4: "사", 5: "오",
    6: "육", 7: "칠", 8: "팔", 9: "구"
}

# 고유어 단위 (개수를 셀 때 사용하는 단위들)
NATIVE_KOREAN_COUNTERS = [
    "개", "명", "마리", "번", "살", "시", "잔", "병", "권", "장",
    "대", "채", "켤레", "벌", "송이", "자루", "그루", "포기", "줄",
    "가지", "군데", "곳", "바퀴", "번째", "분", "시간"
]

# 한자어 단위 (금액, 날짜, 퍼센트 등)
SINO_KOREAN_COUNTERS = [
    "원", "년", "월", "일", "호", "층", "번지", "퍼센트", "%",
    "센티", "미터", "킬로", "그램", "리터", "도", "점"
]


def _number_to_native_korean(num: int) -> str:
    """숫자를 고유어 한국어로 변환 (1-99)"""
    if num in NATIVE_KOREAN_NUMBERS:
        return NATIVE_KOREAN_NUMBERS[num]

    # 100 이상은 한자어로 처리
    return _number_to_sino_korean(num)


def _number_to_sino_korean(num: int) -> str:
    """숫자를 한자어 한국어로 변환"""
    if num == 0:
        return "영"

    result = []

    # 억 단위
    if num >= 100000000:
        eok = num // 100000000
        if eok > 1:
            result.append(_number_to_sino_korean(eok))
        result.append("억")
        num %= 100000000

    # 만 단위
    if num >= 10000:
        man = num // 10000
        if man > 1:
            result.append(_number_to_sino_korean(man))
        result.append("만")
        num %= 10000

    # 천 단위
    if num >= 1000:
        cheon = num // 1000
        if cheon > 1:
            result.append(SINO_KOREAN_DIGITS[cheon])
        result.append("천")
        num %= 1000

    # 백 단위
    if num >= 100:
        baek = num // 100
        if baek > 1:
            result.append(SINO_KOREAN_DIGITS[baek])
        result.append("백")
        num %= 100

    # 십 단위
    if num >= 10:
        sip = num // 10
        if sip > 1:
            result.append(SINO_KOREAN_DIGITS[sip])
        result.append("십")
        num %= 10

    # 일 단위
    if num > 0:
        result.append(SINO_KOREAN_DIGITS[num])

    return "".join(result)


def _convert_number_with_counter(match) -> str:
    """숫자+단위를 자연스러운 한국어로 변환"""
    num_str = match.group(1)
    counter = match.group(2)

    try:
        num = int(num_str)
    except ValueError:
        return match.group(0)  # 변환 실패 시 원본 반환

    # 단위에 따라 고유어/한자어 선택
    if counter in NATIVE_KOREAN_COUNTERS:
        # 고유어 사용 (99까지만, 그 이상은 한자어)
        if num <= 99:
            korean_num = _number_to_native_korean(num)
        else:
            korean_num = _number_to_sino_korean(num)
    else:
        # 한자어 사용
        korean_num = _number_to_sino_korean(num)

    # 퍼센트 기호 변환
    if counter == "%":
        counter = "퍼센트"

    return f"{korean_num} {counter}"


def _convert_standalone_number(match) -> str:
    """단독 숫자를 한국어로 변환"""
    num_str = match.group(0)

    try:
        num = int(num_str)
    except ValueError:
        return num_str

    # 큰 숫자는 한자어로
    return _number_to_sino_korean(num)


def convert_numbers_to_korean(text: str) -> str:
    """
    텍스트 내의 숫자를 자연스러운 한국어로 변환

    Examples:
        "7개" → "일곱 개"
        "3명" → "세 명"
        "1000원" → "천 원"
        "50%" → "오십 퍼센트"
    """
    if not text:
        return text

    # 1. 숫자+단위 패턴 먼저 처리
    all_counters = NATIVE_KOREAN_COUNTERS + SINO_KOREAN_COUNTERS
    counter_pattern = "|".join(re.escape(c) for c in all_counters)
    pattern = rf"(\d+)\s*({counter_pattern})"
    text = re.sub(pattern, _convert_number_with_counter, text)

    # 2. 소수점이 있는 숫자 처리 (예: 3.5 → 삼점오)
    def convert_decimal(match):
        integer_part = match.group(1)
        decimal_part = match.group(2)
        int_korean = _number_to_sino_korean(int(integer_part)) if integer_part else "영"
        decimal_korean = "".join(SINO_KOREAN_DIGITS.get(int(d), d) for d in decimal_part)
        return f"{int_korean}점{decimal_korean}"

    text = re.sub(r"(\d+)\.(\d+)", convert_decimal, text)

    # 3. 남은 단독 숫자 처리 (2자리 이상만)
    text = re.sub(r"\b(\d{2,})\b", _convert_standalone_number, text)

    # 4. 1자리 숫자는 문맥에 따라 - 일단 한자어로
    def convert_single_digit(match):
        num = int(match.group(0))
        return SINO_KOREAN_DIGITS.get(num, str(num)) or "영"

    text = re.sub(r"\b(\d)\b", convert_single_digit, text)

    return text


def remove_non_korean(text: str, keep_punctuation: bool = True) -> str:
    """
    한글이 아닌 문자 제거/변환

    Args:
        text: 입력 텍스트
        keep_punctuation: 구두점 유지 여부

    Returns:
        한글만 포함된 텍스트
    """
    if not text:
        return text

    # 영어를 한글 발음으로 변환 (일반적인 단어들)
    english_to_korean = {
        "OK": "오케이",
        "ok": "오케이",
        "Yes": "예스",
        "yes": "예스",
        "No": "노",
        "no": "노",
        "Hi": "하이",
        "hi": "하이",
        "Hello": "헬로",
        "hello": "헬로",
        "Wow": "와우",
        "wow": "와우",
        "Oh": "오",
        "oh": "오",
        "Ah": "아",
        "ah": "아",
        "Thank you": "땡큐",
        "Thanks": "땡스",
        "Sorry": "쏘리",
        "Please": "플리즈",
        "Good": "굿",
        "Nice": "나이스",
        "Great": "그레잇",
        "Perfect": "퍼펙트",
        "Amazing": "어메이징",
        "Excellent": "엑설런트",
        "Best": "베스트",
        "Top": "탑",
        "New": "뉴",
        "Hot": "핫",
        "Sale": "세일",
        "Free": "프리",
        "Special": "스페셜",
        "Limited": "리미티드",
        "Premium": "프리미엄",
        "Pro": "프로",
        "Max": "맥스",
        "Plus": "플러스",
        "Super": "슈퍼",
        "Ultra": "울트라",
        "Mega": "메가",
        "Mini": "미니",
        "Tip": "팁",
        "Point": "포인트",
        "Bonus": "보너스",
        "Event": "이벤트",
        "Review": "리뷰",
        "Item": "아이템",
        "Set": "세트",
        "Box": "박스",
        "Pack": "팩",
        "Kit": "키트",
        "Style": "스타일",
        "Design": "디자인",
        "Color": "컬러",
        "Size": "사이즈",
        "Brand": "브랜드",
        "Model": "모델",
        "Version": "버전",
        "Type": "타입",
        "Class": "클래스",
        "Level": "레벨",
        "Grade": "그레이드",
        "Quality": "퀄리티",
        "Effect": "이펙트",
        "Function": "펑션",
        "Feature": "피처",
        "Option": "옵션",
        "Mode": "모드",
        "System": "시스템",
        "Smart": "스마트",
        "Auto": "오토",
        "Manual": "매뉴얼",
        "Easy": "이지",
        "Simple": "심플",
        "Fast": "패스트",
        "Quick": "퀵",
        "Slim": "슬림",
        "Light": "라이트",
        "Soft": "소프트",
        "Hard": "하드",
        "Strong": "스트롱",
        "Power": "파워",
        "Energy": "에너지",
        "Fresh": "프레시",
        "Clean": "클린",
        "Clear": "클리어",
        "Pure": "퓨어",
        "Natural": "내추럴",
        "Organic": "오가닉",
        "Real": "리얼",
        "Original": "오리지널",
        "Classic": "클래식",
        "Modern": "모던",
        "Trendy": "트렌디",
        "Luxury": "럭셔리",
        "Basic": "베이직",
        "Standard": "스탠다드",
        "Custom": "커스텀",
        "cm": "센티미터",
        "kg": "킬로그램",
        "g": "그램",
        "ml": "밀리리터",
        "L": "리터",
        "mm": "밀리미터",
        "m": "미터",
    }

    # 영어 단어 치환
    for eng, kor in english_to_korean.items():
        text = re.sub(rf"\b{re.escape(eng)}\b", kor, text, flags=re.IGNORECASE)

    # 남은 영어/숫자/특수문자 처리
    if keep_punctuation:
        # 한글, 공백, 기본 구두점만 유지
        text = re.sub(r"[^\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F\s.,!?~\-]", "", text)
    else:
        # 한글과 공백만 유지
        text = re.sub(r"[^\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F\s]", "", text)

    # 연속된 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _soften_periods_for_tts(text: str) -> str:
    """
    TTS를 위해 마침표(.)를 자연스럽게 처리

    문제: Gemini TTS가 마침표에서 부자연스럽게 긴 쉼을 넣음
    해결: 문장 중간의 마침표를 쉼표로 대체하거나 제거

    규칙:
    - 문장 끝 마침표 (텍스트 끝 또는 공백+대문자 앞): 유지 (자연스러운 끝맺음)
    - 문장 중간 마침표: 쉼표로 대체 (짧은 쉼)
    - 연속된 마침표/구두점: 하나로 통합
    """
    if not text:
        return text

    # 1. 연속된 구두점 정리 (.. 또는 ... → 쉼표)
    text = re.sub(r'\.{2,}', ',', text)

    # 2. 마침표 + 공백 + 한글 → 쉼표 + 공백 + 한글 (문장 중간)
    # 문장 중간의 마침표는 짧은 쉼으로 대체
    text = re.sub(r'\.\s+([가-힣])', r', \1', text)

    # 3. 마침표 바로 다음에 한글이 오는 경우 (공백 없이)
    text = re.sub(r'\.([가-힣])', r', \1', text)

    # 4. 연속된 쉼표 정리
    text = re.sub(r',\s*,+', ',', text)

    # 5. 쉼표 뒤 공백 정리
    text = re.sub(r',\s*', ', ', text)

    # 6. 문장 끝의 마침표는 유지 (텍스트 맨 끝)
    # 이미 위 규칙에서 중간 마침표가 처리되었으므로 끝 마침표만 남음

    return text.strip()


def process_korean_script(text: str, for_tts: bool = True) -> str:
    """
    스크립트를 TTS에 적합한 한국어로 처리

    1. 숫자를 자연스러운 한국어로 변환
    2. 비한글 문자 제거/변환
    3. TTS용: 마침표 처리 (부자연스러운 쉼 방지)

    Args:
        text: 원본 스크립트 텍스트
        for_tts: TTS용 처리 여부 (마침표 소프트닝)

    Returns:
        처리된 한국어 텍스트
    """
    if not text:
        return text

    # 1. 숫자 변환
    text = convert_numbers_to_korean(text)

    # 2. 비한글 제거 (구두점은 유지)
    text = remove_non_korean(text, keep_punctuation=True)

    # 3. TTS용 마침표 처리 (부자연스러운 쉼 방지)
    if for_tts:
        text = _soften_periods_for_tts(text)

    return text
