"""
Utility Functions for Batch Processing

Contains general-purpose helper functions used across the batch processing module.
"""

import os
import re
import base64
import wave
from typing import List, Tuple, Set

from utils import Tool
from caller import ui_controller
from utils.logging_config import get_logger

logger = get_logger(__name__)


def _extract_product_name(app) -> str:
    """
    상품명 추출 (여러 소스에서 시도)

    우선순위:
    1. app.video_title (설정된 경우)
    2. app.product_name (설정된 경우)
    3. 로컬 파일명에서 추출
    4. 번역 결과 첫 20자
    5. 기본값 'video'
    """
    # 1. video_title 확인
    title = getattr(app, 'video_title', None)
    if title and title.strip():
        return Tool.sanitize_filename(title.strip()[:30])

    # 2. product_name 확인
    product = getattr(app, 'product_name', None)
    if product and product.strip():
        return Tool.sanitize_filename(product.strip()[:30])

    # 3. 로컬 파일명에서 추출
    if app.video_source.get() == "local" and app.local_file_path:
        base_name = os.path.splitext(os.path.basename(app.local_file_path))[0]
        if base_name:
            # 날짜/숫자 패턴 제거 (예: 20231124_video -> video)
            cleaned = re.sub(r'^\d{6,}_?', '', base_name)
            cleaned = re.sub(r'_\d{6,}$', '', cleaned)
            if cleaned:
                return Tool.sanitize_filename(cleaned[:30])

    # 4. 번역 결과 첫 20자 (공백으로 구분된 첫 문장)
    translation = getattr(app, 'translation_result', '')
    if translation:
        # 첫 줄 또는 첫 문장 추출
        first_line = translation.strip().split('\n')[0]
        first_sentence = re.split(r'[.!?。]', first_line)[0].strip()
        if first_sentence:
            # 특수문자 제거하고 20자까지
            clean_text = re.sub(r'[^\w\s가-힣]', '', first_sentence)[:20].strip()
            if clean_text:
                return Tool.sanitize_filename(clean_text)

    # 5. 기본값
    return "video"


def _extract_text_from_response(response):
    """
    Gemini API 응답에서 안전하게 텍스트만 추출 (thought_signature 경고 방지)

    Args:
        response: Gemini API 응답 객체

    Returns:
        str: 추출된 텍스트
    """
    try:
        # candidates에서 텍스트 파트만 추출
        if hasattr(response, 'candidates') and response.candidates:
            text_parts = []
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content:
                    for part in candidate.content.parts:
                        # text 속성이 있는 파트만 추출 (thought_signature 제외)
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
            if text_parts:
                return '\n'.join(text_parts).strip()

        # fallback: response.text 사용 (경고 발생 가능)
        return getattr(response, 'text', '').strip()
    except Exception as e:
        logger.warning(f"[텍스트 추출 오류] {e}")
        ui_controller.write_error_log(e)
        return ""


def _get_voice_display_name(voice_name: str) -> str:
    """
    Gemini 음성 ID를 한글 표시 이름으로 변환

    Args:
        voice_name: Gemini API voice ID (예: "Charon", "Callirrhoe")

    Returns:
        str: 한글 표시 이름 (예: "준호", "지은")
    """
    try:
        from voice_profiles import VOICE_PROFILES
        for profile in VOICE_PROFILES:
            if profile.get('voice_name') == voice_name or profile.get('id') == voice_name:
                return profile.get('label', voice_name)
    except Exception as e:
        logger.debug(f"[음성 이름 변환] VOICE_PROFILES 로드 실패: {e}")
    return voice_name


def _translate_error_message(error_text: str) -> str:
    """
    영어 오류 메시지를 한글로 번역 (간결하고 사용자 친화적)

    Args:
        error_text: 원본 오류 메시지

    Returns:
        번역된 오류 메시지
    """
    error_lower = error_text.lower()

    # ★ 프레임 읽기 오류 (블러 처리 후 원본 파일 참조 끊김) - 인코딩 오류보다 먼저 체크
    if 'failed to read' in error_lower and 'frame' in error_lower:
        return "비디오 프레임 읽기 오류 - 원본 파일 접근 불가 (블러 처리 관련)"

    # ★ 인코딩/ffmpeg 오류 체크 (API 오류보다 우선)
    # 영상 합성 단계에서는 API 호출이 없으므로 인코딩 오류로 분류
    encoding_keywords = ['ffmpeg', 'encoder', 'encoding', 'codec', 'write_videofile', 'libx264', 'h264', 'aac']
    # 'video'는 write/export 컨텍스트에서만 인코딩 오류로 분류 (frame 제외 - 프레임 읽기 오류와 구분)
    has_encoding_keyword = any(kw in error_lower for kw in encoding_keywords)
    has_video_with_context = 'video' in error_lower and any(ctx in error_lower for ctx in ['write', 'export', 'render', 'output'])

    if has_encoding_keyword or has_video_with_context:
        return "인코딩 오류 - 영상 합성 중 문제 발생"

    # 429 RESOURCE_EXHAUSTED (할당량 초과) - 가장 흔한 에러
    if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text or "quota" in error_lower:
        return "API 일일 할당량 초과 - 다른 API 키로 자동 전환 중"

    # 500번대 서버 오류 (API 관련 키워드가 있을 때만)
    if ("500" in error_text or "503" in error_text or "overloaded" in error_lower) and \
       any(kw in error_lower for kw in ['api', 'gemini', 'google', 'request', 'response', 'http']):
        return "API 서버 과부하 - 잠시 후 재시도"

    # 401/403 권한 오류
    if "401" in error_text or "403" in error_text or "PERMISSION_DENIED" in error_text or "Unauthorized" in error_text:
        return "API 인증 오류 - API 키 확인 필요"

    # 400 잘못된 요청
    if "400" in error_text or "Bad request" in error_text or "validation error" in error_text.lower():
        return "잘못된 요청 형식 - 설정 확인 필요"

    # 404 Not Found
    if "404" in error_text or "Not found" in error_text:
        return "리소스를 찾을 수 없음"

    # 타임아웃
    if "timeout" in error_text.lower() or "timed out" in error_text.lower():
        return "요청 시간 초과 - 네트워크 확인 필요"

    # 네트워크 오류
    if "network" in error_text.lower() or "connection" in error_text.lower():
        return "네트워크 연결 오류 - 인터넷 연결 확인 필요"

    # 영상 길이 제한 (10초~39초)
    if "영상 너무 짧음" in error_text or "너무짧음" in error_text:
        duration_match = re.search(r'실제:\s*(\d+\.?\d*)', error_text)
        if duration_match:
            duration = float(duration_match.group(1))
            return f"영상 {duration:.0f}초 - 10초 이상 필요"
        return "영상이 10초 미만 - 다음 영상으로 건너뜀"

    if "영상 길이 초과" in error_text or "길이초과" in error_text:
        duration_match = re.search(r'실제:\s*(\d+\.?\d*)', error_text)
        if duration_match:
            duration = float(duration_match.group(1))
            return f"영상 {duration:.0f}초 - 39초 이하만 처리 가능"
        return "영상이 39초 초과 - 다음 영상으로 건너뜀"

    # TTS 길이 초과 오류 (영어/한글 모두 지원)
    if "TTS length" in error_text and "exceeds video length" in error_text:
        # 구체적인 숫자 추출 시도
        tts_match = re.search(r'TTS length \((\d+\.?\d*)s\)', error_text)
        video_match = re.search(r'video length \((\d+\.?\d*)s\)', error_text)
        if tts_match and video_match:
            tts_len = float(tts_match.group(1))
            video_len = float(video_match.group(1))
            return f"영상 너무 짧음 ({video_len:.0f}초) - TTS {tts_len:.0f}초 필요. 최소 {tts_len + 2:.0f}초 이상 영상 사용"
        return "영상이 너무 짧아 CTA조차 담을 수 없음 - 더 긴 영상 필요"
    if "TTS 길이" in error_text or "영상 길이" in error_text or "초과합니다" in error_text:
        return "영상이 너무 짧음 - TTS가 영상보다 김. 더 긴 영상 필요"

    # 기타 간단한 패턴 매칭
    simple_translations = {
        "Extra inputs are not permitted": "허용되지 않는 입력 파라미터",
        "Field required": "필수 항목 누락",
        "invalid type": "잘못된 데이터 타입",
        "rate limit": "API 요청 제한 초과",
    }

    for eng, kor in simple_translations.items():
        if eng.lower() in error_text.lower():
            return kor

    # 알 수 없는 오류 - HTTP 에러 코드만 추출 (실제 HTTP 에러 패턴만 매칭)
    # "HTTP 4XX", "status 5XX", "error 4XX", "[5XX]" 등의 패턴만 추출
    # ★ 단, API 관련 컨텍스트가 있을 때만 "API 오류"로 표시
    http_error_patterns = [
        r'(?:HTTP|http|status|Status)[\s:_-]*(\d{3})',  # HTTP 401, status 500 등
        r'\[(\d{3})\]',  # [404], [500] 등
    ]

    # API 관련 키워드가 있는지 확인
    is_api_related = any(kw in error_lower for kw in ['api', 'gemini', 'google', 'request', 'response', 'endpoint'])

    for pattern in http_error_patterns:
        error_code_match = re.search(pattern, error_text)
        if error_code_match:
            code = error_code_match.group(1)
            # 4XX 또는 5XX 코드만 유효
            if code.startswith('4') or code.startswith('5'):
                if is_api_related:
                    return f"API 오류 (코드 {code}) - 재시도 중"
                else:
                    return f"처리 오류 (코드 {code}) - 재시도 중"

    # 완전히 알 수 없는 경우 - 원본 에러 메시지 일부 표시
    # 에러 메시지가 너무 길면 처음 50자만 표시
    short_error = error_text[:50] + "..." if len(error_text) > 50 else error_text
    logger.debug(f"[알 수 없는 오류] 원본: {error_text}")
    return f"처리 오류 - {short_error}"


def _get_short_error_message(error: Exception) -> str:
    """
    오류를 분석하여 '비고' 란에 표시할 짧은 한글 메시지 생성 (최대 10자)

    Args:
        error: 발생한 예외 객체

    Returns:
        str: 10자 이내의 한글 오류 메시지
    """

    ui_controller.write_error_log(error)

    error_str = str(error)
    error_type = type(error).__name__

    # 오류 타입별 짧은 메시지 매핑
    short_messages = {
        'TypeError': '타입오류',
        'AttributeError': '속성오류',
        'ValueError': '값오류',
        'KeyError': '키오류',
        'IndexError': '인덱스오류',
        'FileNotFoundError': '파일없음',
        'PermissionError': '권한오류',
        'TimeoutError': '시간초과',
        'ConnectionError': '연결오류',
        'HTTPError': 'HTTP오류',
        'JSONDecodeError': 'JSON오류',
        'UnicodeDecodeError': '인코딩오류',
        'MemoryError': '메모리부족',
        'OSError': '시스템오류',
        'RuntimeError': '실행오류',
        'ImportError': '모듈없음',
        'ModuleNotFoundError': '모듈없음',
    }

    # 특정 오류 메시지 패턴 감지
    error_lower = error_str.lower()

    # ★ 인코딩/영상 처리 오류 먼저 체크 (API 오류보다 우선)
    encoding_keywords = ['ffmpeg', 'encoder', 'encoding', 'codec', 'moviepy', 'write_videofile', 'libx264', 'h264', 'aac']
    if any(kw in error_lower for kw in encoding_keywords):
        return '인코딩오류'
    elif 'video' in error_lower and any(ctx in error_lower for ctx in ['write', 'export', 'render', 'frame', 'clip', 'output']):
        return '영상처리오류'
    elif 'subtitle' in error_lower or 'ocr' in error_lower:
        return '자막처리오류'
    elif '너무짧음' in error_str or '영상 너무 짧음' in error_str:
        return '10초미만'
    elif '길이초과' in error_str or '영상 길이 초과' in error_str:
        return '39초초과'
    elif 'tts length' in error_lower and 'exceeds' in error_lower:
        return '영상짧음'
    elif 'tts' in error_lower or 'audio' in error_lower:
        return 'TTS오류'
    elif 'download' in error_lower:
        return '다운로드오류'
    # API 관련 오류
    elif 'api' in error_lower and ('quota' in error_lower or 'limit' in error_lower):
        return 'API한도초과'
    elif 'permission' in error_lower or 'denied' in error_lower:
        return 'API권한없음'
    elif 'rate limit' in error_lower:
        return 'API제한초과'
    # 타임아웃/시간초과 오류 - 구체적인 상황별 메시지 (영어 + 한글)
    elif 'timeout' in error_lower or 'timed out' in error_lower or '시간 초과' in error_str or '타임아웃' in error_str:
        # 다운로드 관련 타임아웃
        if 'download' in error_lower or '다운로드' in error_str or 'read operation' in error_lower:
            return '다운로드실패'
        # 분석/API 관련 타임아웃
        elif 'analysis' in error_lower or '분석' in error_str or 'gemini' in error_lower:
            return '분석시간초과'
        # 연결 관련 타임아웃
        elif 'connect' in error_lower or '연결' in error_str:
            return '연결시간초과'
        # 요청 관련 타임아웃 (네트워크 문제)
        elif '요청' in error_str or 'request' in error_lower or '네트워크' in error_str:
            return '네트워크불안정'
        else:
            return '응답시간초과'
    # 네트워크 오류 (영어 + 한글)
    elif 'network' in error_lower or 'connection' in error_lower or '네트워크' in error_str:
        if 'reset' in error_lower or '끊김' in error_str:
            return '연결끊김'
        elif 'refused' in error_lower or '거부' in error_str:
            return '연결거부됨'
        else:
            return '네트워크오류'
    elif '연결' in error_str:
        return '연결오류'
    elif 'not found' in error_lower:
        return '리소스없음'
    elif 'validation' in error_lower:
        return '입력값오류'
    elif 'unauthorized' in error_lower:
        return '인증실패'
    elif 'bad request' in error_lower:
        return '잘못된요청'
    elif 'internal server' in error_lower:
        return '서버오류'
    elif 'overloaded' in error_lower:
        return '서버과부하'

    # 기본 오류 타입 매핑
    if error_type in short_messages:
        return short_messages[error_type]

    # 알 수 없는 오류
    return '알수없음'


def _select_sentences_with_priority(
    sentence_entries: List[Tuple[str, bool]],
    target_chars: int,
    allowed_overflow: int,
) -> Tuple[List[Tuple[str, bool]], int, int]:
    """Pick sentences while keeping priority ones such as CTA lines."""

    if not sentence_entries:
        return [], max(target_chars, 0), 0

    # Collect unique priority sentences to estimate reserved length
    priority_sentences: List[str] = []
    seen_priority: Set[str] = set()
    for sentence, is_priority in sentence_entries:
        text = sentence.strip()
        if is_priority and text and text not in seen_priority:
            priority_sentences.append(text)
            seen_priority.add(text)

    priority_text = " ".join(priority_sentences).strip()
    priority_length = len(priority_text)

    allowed_total = max(target_chars, priority_length)
    if allowed_overflow > 0:
        allowed_total += allowed_overflow
    if allowed_total < priority_length:
        allowed_total = priority_length

    available_non_priority = max(target_chars - priority_length, 0)

    result_entries: List[Tuple[str, bool]] = []
    used_chars = 0
    seen_priority.clear()

    for sentence, is_priority in sentence_entries:
        text = sentence.strip()
        if not text:
            continue

        if is_priority:
            if text not in seen_priority:
                result_entries.append((text, True))
                seen_priority.add(text)
            continue

        addition = len(text)
        if result_entries:
            addition += 1  # account for space when joined

        if used_chars + addition <= available_non_priority:
            result_entries.append((text, False))
            used_chars += addition

    if not result_entries:
        if priority_sentences:
            result_entries = [(sentence, True) for sentence in priority_sentences]
        else:
            first_sentence = sentence_entries[0][0].strip()
            if first_sentence:
                result_entries = [(first_sentence, False)]

    current_text = " ".join(sentence for sentence, _ in result_entries).strip()

    while len(current_text) > allowed_total:
        removable_idx = next(
            (idx for idx in range(len(result_entries) - 1, -1, -1)
             if not result_entries[idx][1]),
            None,
        )
        if removable_idx is None:
            break
        del result_entries[removable_idx]
        current_text = " ".join(sentence for sentence, _ in result_entries).strip()

    allowed_total = max(allowed_total, len(current_text))

    return result_entries, allowed_total, priority_length


def _is_bad_split_point(text, pos):
    """
    분할 위치가 한국어 문법 단위를 끊는지 검사.

    나쁜 분할 예시:
    - "쌀알 한 | 톨" → "한 톨"이 끊김
    - "먹을 수 | 있는" → "~ㄹ 수 있/없" 패턴 끊김
    - "물을 | 빼고" → OK (조사 뒤 분리는 허용)

    Returns:
        bool: True면 이 위치에서 분리하면 안됨
    """
    if pos <= 0 or pos >= len(text):
        return False

    # 분리 지점 앞뒤 텍스트
    before = text[:pos].rstrip()
    after = text[pos:].lstrip()

    if not before or not after:
        return False

    # ★★★ 1. 숫자/수량사 + 단위 패턴 (끊으면 안됨) ★★★
    # "한 톨", "두 개", "세 마리", "한두 개" 등
    number_words = ['한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉', '열',
                    '한두', '두세', '서너', '몇', '몇몇', '여러']
    counter_words = ['개', '톨', '마리', '명', '장', '권', '병', '잔', '그릇', '벌', '켤레',
                     '대', '채', '척', '자루', '송이', '알', '방울', '조각', '점', '가지']

    # before가 숫자로 끝나고 after가 단위로 시작하면 나쁜 분리
    for num in number_words:
        if before.endswith(num):
            for counter in counter_words:
                if after.startswith(counter):
                    return True

    # ★★★ 2. ~ㄹ 수 있/없 패턴 (끊으면 안됨) ★★★
    # "먹을 수 있는", "할 수 없어요", "볼 수 있어요"
    if before.endswith(' 수') or before.endswith('ㄹ 수'):
        if after.startswith('있') or after.startswith('없'):
            return True

    # "~을/ㄹ" 로 끝나고 "수 있/없"이 다음에 오면 나쁜 분리
    if re.search(r'[을ㄹ]$', before):
        if after.startswith('수 있') or after.startswith('수 없'):
            return True

    # ★★★ 3. ~하고 싶/않 패턴 ★★★
    if before.endswith('하고') or before.endswith('고'):
        if after.startswith('싶') or after.startswith('않'):
            return True

    # ★★★ 3-1. ~ㄹ 때/~을 때 패턴 (끊으면 안됨) ★★★
    # "심심해할 때", "먹을 때", "갈 때" 등
    if after.startswith('때'):
        # 앞 단어가 관형사형 어미로 끝나면 나쁜 분리
        # ㄹ, 을, 할, 볼, 갈, 할, 될 등
        if re.search(r'[ㄹ을할볼갈될줄알쓸살]$', before):
            return True
        # 공백 + 동사 관형사형 (예: "심심해할", "놀아줄")
        last_word = before.split()[-1] if before.split() else ''
        if last_word and re.search(r'[ㄹ을할볼갈될줄알쓸살]$', last_word):
            return True

    # ★★★ 3-2. 의존명사 패턴 (끊으면 안됨) ★★★
    # "먹을 것", "알 줄", "갈 데", "할 바", "올 리", "할 터", "할 뿐"
    dependent_nouns = ['것', '줄', '데', '바', '리', '터', '뿐', '만큼', '대로', '듯', '뻔']
    for dn in dependent_nouns:
        if after.startswith(dn):
            # 앞이 관형사형 어미로 끝나면 나쁜 분리
            if re.search(r'[ㄴㄹ은을는]$', before):
                return True
            last_word = before.split()[-1] if before.split() else ''
            if last_word and re.search(r'[ㄴㄹ은을는]$', last_word):
                return True

    # ★★★ 3-3. ~지 않다/못하다/말다 부정 패턴 ★★★
    # "먹지 않는", "하지 못해", "가지 마세요"
    if before.endswith('지'):
        if re.match(r'^(않|못|말)', after):
            return True

    # ★★★ 3-4. ~게 되다/하다 패턴 ★★★
    # "먹게 되다", "하게 하다", "알게 됐어"
    if before.endswith('게'):
        if re.match(r'^(되|하|만들)', after):
            return True

    # ★★★ 3-5. ~고 있다/보다/싶다 보조동사 패턴 ★★★
    # "먹고 있다", "해 보다", "하고 싶다"
    if before.endswith('고'):
        if re.match(r'^(있|싶|보|나)', after):
            return True

    # ★★★ 3-6. ~아/어 주다/보다/내다/버리다 보조용언 패턴 ★★★
    # "해 줘", "먹어 봐", "해 내다", "먹어 버려"
    if re.search(r'[아어해]$', before):
        if re.match(r'^(주|줘|보|봐|내|버|드)', after):
            return True

    # ★★★ 3-7. ~ㄹ 것 같다 추측 패턴 ★★★
    # "먹을 것 같아", "할 것 같다"
    if before.endswith(' 것') or before.endswith('ㄹ 것'):
        if after.startswith('같'):
            return True

    # ★★★ 3-8. ~도록 하다/만들다 패턴 ★★★
    # "먹도록 하다", "가도록 만들다"
    if before.endswith('도록'):
        if re.match(r'^(하|만들|해)', after):
            return True

    # ★★★ 3-9. ~ㄴ지/는지/을지 의문/간접의문 패턴 ★★★
    # "뭔지 알아", "하는지 봐", "갈지 몰라"
    if re.search(r'[ㄴ는을]지$', before):
        if re.match(r'^(알|몰|봐|보|궁금|모르)', after):
            return True

    # ★★★ 3-10. ~ㄹ 수밖에 없다 패턴 ★★★
    if before.endswith(' 수밖에') or before.endswith('ㄹ 수밖에'):
        if after.startswith('없'):
            return True

    # ★★★ 3-11. ~(으)면 되다/안되다 조건 결과 패턴 ★★★
    # "하면 돼", "먹으면 안돼"
    if re.search(r'[으]?면$', before):
        if re.match(r'^(돼|되|안)', after):
            return True

    # ★★★ 3-12. ~(으)려고 하다 의도 패턴 ★★★
    # "먹으려고 해", "가려고 했어"
    if before.endswith('려고') or before.endswith('으려고'):
        if re.match(r'^(하|해|했)', after):
            return True

    # ★★★ 3-13. ~ㄹ 수도 있다 가능성 패턴 ★★★
    if before.endswith(' 수도') or before.endswith('ㄹ 수도'):
        if after.startswith('있') or after.startswith('없'):
            return True

    # ★★★ 3-14. 부정 부사 + 동사/형용사 (전혀/별로/도저히 + 없/못/안) ★★★
    neg_adverbs = ['전혀', '별로', '도저히', '절대', '결코', '도무지']
    last_word = before.split()[-1] if before.split() else ''
    if last_word in neg_adverbs:
        if re.match(r'^(없|못|안|아니)', after):
            return True

    # ★★★ 3-15. ~기 때문에/위해/전에/후에 명사형 어미 + 의존명사 ★★★
    if before.endswith('기'):
        if re.match(r'^(때문|위해|전에|후에|위한|바라|싫|좋|쉬)', after):
            return True

    # ★★★ 3-16. ~ㄴ/는 편이다 평가 패턴 ★★★
    if before.endswith(' 편') or re.search(r'[ㄴ는]편$', before):
        if after.startswith('이') or after.startswith('인'):
            return True

    # ★★★ 3-17. ~(으)ㄹ 정도 정도 표현 패턴 ★★★
    if after.startswith('정도'):
        if re.search(r'[ㄹ을]$', before):
            return True
        last_word = before.split()[-1] if before.split() else ''
        if last_word and re.search(r'[ㄹ을]$', last_word):
            return True

    # ★★★ 3-18. 복합 조사 패턴 (에서는, 으로는, 에게는 등) ★★★
    compound_particles = ['에서는', '으로는', '에게는', '한테는', '부터는', '까지는', '마저도', '조차도']
    for cp in compound_particles:
        if len(cp) > 1 and before.endswith(cp[:-1]) and after.startswith(cp[-1]):
            return True

    # ★★★ 4. 관형사 + 명사 패턴 (짧은 경우) ★★★
    # "이 제품", "그 방법", "저 사람" - 1글자 관형사 뒤에서 끊지 않음
    if len(before) >= 1 and before[-1] in ['이', '그', '저', '새', '헌', '온']:
        if before[-2:-1] == ' ' or len(before) == 1:
            return True

    # ★★★ 5. 부사 + 동사/형용사 패턴 ★★★
    # "잘 맞는", "못 하는", "안 되는"
    short_adverbs = ['잘', '못', '안', '꼭', '다', '더', '덜', '막']
    if before.split()[-1] if before.split() else '' in short_adverbs:
        return True

    # ★★★ 6. ~(으)ㄴ/는/ㄹ + 명사 관형사형 패턴 ★★★
    # "예쁜 꽃", "먹는 음식", "갈 곳" - 관형사형 어미 뒤에서 분리 금지
    if re.search(r'[ㄴ는ㄹ은]$', before):
        # 다음에 명사/의존명사가 올 가능성 높음
        if after and not re.match(r'^(것|수|때|줄|곳|바|터|뿐|편|정도|만큼)', after):
            # 일반 명사로 시작하면 분리 금지
            if re.match(r'^[가-힣]', after):
                return True

    # ★★★ 7. 존칭/높임 표현 패턴 ★★★
    # "드릴게요", "드려요", "주세요" 등 분리 금지
    honorific_patterns = ['드릴', '드려', '드리', '주셔', '주시', '하셔', '하시', '오셔', '오시', '계셔', '계시']
    for hp in honorific_patterns:
        if before.endswith(hp[:2]) and after.startswith(hp[2:]):
            return True

    # ★★★ 8. 이중 모음 / 복합 어미 패턴 ★★★
    # "~아요/어요", "~해요", "~죠" 등 분리 금지
    if re.search(r'[아어해]$', before) and re.match(r'^요', after):
        return True
    if before.endswith('지') and after.startswith('요'):
        return True

    # ★★★ 9. 숫자 + 조사 패턴 ★★★
    # "10개", "5분", "3번" 등
    if re.search(r'\d$', before):
        if re.match(r'^[개분번초시일월년회명%]', after):
            return True

    # ★★★ 10. 한자어 + 하다 패턴 ★★★
    # "확인해", "선택해", "등록해" - 한자어와 하다 분리 금지
    sino_korean = ['확인', '선택', '등록', '수정', '삭제', '저장', '검색', '구매', '결제', '배송',
                   '주문', '취소', '문의', '상담', '추천', '할인', '적용', '완료', '진행', '처리',
                   '사용', '이용', '참고', '참조', '설명', '안내', '소개', '공유', '연결', '연락']
    for sk in sino_korean:
        if before.endswith(sk) and re.match(r'^[해하]', after):
            return True

    # ★★★ 11. 짧은 단어 보호 (2글자 이하) ★★★
    # 마지막 단어가 2글자 이하면 분리하지 않음 (조사 등과 붙어있어야 함)
    last_word = before.split()[-1] if before.split() else ''
    if len(last_word) <= 2 and not re.search(r'[은는이가을를에서로]$', last_word):
        # 조사가 아닌 2글자 이하 단어 뒤에서 분리 금지
        return True

    # ★★★ 12. 인용/인칭 패턴 ★★★
    # "~라고", "~다고", "~냐고" 등의 인용 표현
    if before.endswith('라') or before.endswith('다') or before.endswith('냐'):
        if after.startswith('고'):
            return True

    # ★★★ 13. 보조사 패턴 ★★★
    # "~도", "~만", "~까지", "~조차", "~마저" 뒤에서 동사/형용사 분리 금지
    if re.search(r'[도만]$', before):
        if re.match(r'^[가-힣]', after) and not re.match(r'^[은는이가을를에서로와과의]', after):
            return True

    return False


def _split_text_naturally(app, text, max_chars=13):
    """
    자막 텍스트를 자연스럽게 분할 - 한글 지원

    분할 순서:
    1. 구두점(. ! ? 등) 기준으로 1차 문장 분리
    2. 최대 길이 초과 시 자연스러운 위치에서 2차 분리
       - 쉼표/세미콜론
       - 접속 부사 (그리고, 하지만 등)
       - 연결 어미 (~고, ~며, ~서, ~면 등)
       - 조사 뒤 공백 (은/는/이/가/을/를/에/로 등)
    3. 나쁜 분할 위치 회피 (문법 단위 보존)
       - 숫자 + 단위 ("한 톨", "두 개")
       - ~ㄹ 수 있/없 ("먹을 수 있는")

    max_chars: 기본 13글자 (띄어쓰기 포함)
    """
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    logger.info(f"[자막 분할] 원본 텍스트 길이: {len(normalized)}자")

    if not normalized:
        return []

    # CTA 문장 보존 처리 - CTA는 분할하지 않고 그대로 유지
    from ui.panels.cta_panel import get_selected_cta_lines
    cta_lines = get_selected_cta_lines(app)
    preserved_cta = []
    text_without_cta = normalized

    # CTA 문장들을 텍스트에서 추출하고 보존
    for cta_line in cta_lines:
        if cta_line in text_without_cta:
            text_without_cta = text_without_cta.replace(cta_line, " ").strip()
            preserved_cta.append(cta_line)

    # CTA가 텍스트에 포함되어 있었으면 로그 출력
    if preserved_cta:
        logger.info(f"[자막 분할] CTA {len(preserved_cta)}개 보존: {preserved_cta}")
        text_without_cta = re.sub(r"\s+", " ", text_without_cta).strip()

    # ★★★ 자연스러운 분할을 위한 파라미터 ★★★
    target = max_chars or 13  # 목표 글자 수 (기본 13자)
    min_chars = max(4, target - 3)  # 최소 4글자 (너무 짧은 분할 방지)
    hard_max = target + 2  # 최대 15글자까지만 허용 (엄격한 제한)

    # CTA가 없으면 원본 텍스트 사용
    working_text = text_without_cta if preserved_cta else normalized

    # ★★★ 1단계: 구두점 기준 문장 분리 ★★★
    # 마침표, 물음표, 느낌표 뒤에서 확실히 분리 (구두점은 앞 문장에 포함)
    sentence_pattern = re.compile(r'([.!?。？！]+)')
    parts = sentence_pattern.split(working_text)

    sentences = []
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if not part:
            i += 1
            continue
        # 다음 파트가 구두점이면 붙이기
        if i + 1 < len(parts) and sentence_pattern.fullmatch(parts[i + 1]):
            part = part + parts[i + 1]
            i += 2
        else:
            i += 1
        if part.strip():
            sentences.append(part.strip())

    if not sentences:
        sentences = [working_text] if working_text else []

    logger.info(f"[자막 분할] 1단계 구두점 분리: {len(sentences)}개")
    for idx, s in enumerate(sentences):
        logger.debug(f"  {idx+1}. [{len(s)}자] {s}")

    # ★★★ 2단계: 최대 길이 초과 시 자연스러운 위치에서 분리 ★★★
    segments = []

    # 한국어 연결 어미 패턴 (분리하기 좋은 위치)
    # ~고, ~며, ~서, ~면, ~니, ~라, ~지만, ~는데, ~요 뒤 공백
    connective_endings = re.compile(
        r'(고|며|서|면|니|지만|는데|지요|네요|어요|아요|죠|거든요|잖아요) '
    )

    for sentence in sentences:
        if len(sentence) <= hard_max:
            # 길이가 적절하면 그대로 추가
            segments.append(sentence)
        else:
            # 길면 자연스러운 위치에서 분리
            remaining = sentence
            while remaining:
                if len(remaining) <= hard_max:
                    segments.append(remaining)
                    break

                # 분리 위치 찾기 (우선순위별)
                split_idx = -1

                # 1순위: 쉼표, 가운뎃점 등 (가장 명확한 분리점)
                for sep in [',', '，', 'ㆍ', '·', ';']:
                    idx = remaining.rfind(sep, min_chars, hard_max)
                    if idx > min_chars:
                        split_idx = idx + 1
                        break

                # 2순위: 접속 부사 앞에서 분리
                if split_idx < 0:
                    for conj in ['그리고', '하지만', '그래서', '그런데', '또한', '그러나', '그러면', '만약']:
                        idx = remaining.find(conj, min_chars, hard_max + len(conj))
                        if idx > 0:
                            split_idx = idx
                            break

                # 3순위: 연결 어미 뒤에서 분리 (~고, ~며, ~서 등)
                if split_idx < 0:
                    search_region = remaining[:hard_max]
                    for m in connective_endings.finditer(search_region):
                        pos = m.end()
                        if pos >= min_chars:
                            split_idx = pos
                            # target에 가까운 위치 선호
                            if pos >= target - 2:
                                break

                # 4순위: 조사 뒤 공백에서 분리 (은/는/이/가/을/를/에/로 등)
                if split_idx < 0:
                    # 조사 + 공백 패턴
                    josa_pattern = re.compile(r'(은|는|이|가|을|를|에|로|와|과|의|도|만|까지|에서|으로|라서|하고) ')
                    search_region = remaining[:hard_max]
                    candidates = []
                    for m in josa_pattern.finditer(search_region):
                        pos = m.end()
                        if pos >= min_chars and not _is_bad_split_point(remaining, pos):
                            candidates.append(pos)
                    # target에 가장 가까운 위치 선택
                    if candidates:
                        split_idx = min(candidates, key=lambda p: abs(p - target))

                # 5순위: 일반 공백에서 분리 (target 근처, 나쁜 위치 회피)
                if split_idx < 0:
                    search_start = max(min_chars, target - 3)
                    search_end = min(len(remaining), hard_max)

                    candidates = []
                    for pos in range(search_start, search_end):
                        if remaining[pos] == ' ':
                            split_pos = pos + 1
                            if not _is_bad_split_point(remaining, split_pos):
                                candidates.append(split_pos)

                    # target에 가장 가까운 좋은 위치 선택
                    if candidates:
                        split_idx = min(candidates, key=lambda p: abs(p - target))
                    else:
                        # 모든 위치가 나쁘면 가장 덜 나쁜 위치 선택 (확장 범위)
                        for pos in range(min_chars, min(len(remaining), hard_max + 3)):
                            if remaining[pos] == ' ':
                                split_idx = pos + 1
                                break

                # 6순위: 강제 분리 (공백 없으면)
                if split_idx < 0:
                    split_idx = target

                # 분리 실행
                left = remaining[:split_idx].strip()
                remaining = remaining[split_idx:].strip()

                if left:
                    segments.append(left)

    logger.info(f"[자막 분할] 2단계 길이 분리 후: {len(segments)}개")

    # ★★★ 3단계: 너무 짧은 세그먼트 병합 ★★★
    merged = []
    for seg in segments:
        seg = seg.strip(' ,;')
        if not seg:
            continue
        if merged and len(seg) < min_chars:
            # 이전 세그먼트와 합쳐도 hard_max 이내면 병합
            if len(merged[-1]) + 1 + len(seg) <= hard_max:
                merged[-1] = f"{merged[-1]} {seg}".strip()
            else:
                merged.append(seg)
        else:
            merged.append(seg)

    # 마지막 세그먼트가 너무 짧으면 이전과 병합
    if len(merged) > 1 and len(merged[-1]) < min_chars:
        if len(merged[-2]) + 1 + len(merged[-1]) <= hard_max + 3:
            merged[-2] = f"{merged[-2]} {merged[-1]}".strip()
            merged.pop()

    result = [seg for seg in merged if seg]

    # ★★★ CTA 2분할 로직 ★★★
    # CTA 3줄을 통합 후 길면 2분할
    # 예: "영상 속 제품은 고정댓글 확인해 주세요" → "영상 속 제품은" / "고정댓글 확인해 주세요"
    if preserved_cta:
        combined_cta = " ".join(preserved_cta)
        cta_max_chars = 15  # 한 세그먼트 최대 글자수

        if len(combined_cta) <= cta_max_chars:
            # 짧으면 한줄로
            result.append(combined_cta)
            logger.info(f"[자막 분할] CTA 합침: {len(preserved_cta)}개 → 1개 ('{combined_cta}')")
        else:
            # 길면 2분할 (중간 지점에서 공백 기준 분할)
            mid = len(combined_cta) // 2
            # 중간 근처 공백 찾기
            split_idx = combined_cta.rfind(" ", 0, mid + 5)
            if split_idx <= 0:
                split_idx = combined_cta.find(" ", mid)
            if split_idx <= 0:
                split_idx = mid

            part1 = combined_cta[:split_idx].strip()
            part2 = combined_cta[split_idx:].strip()

            if part1 and part2:
                result.append(part1)
                result.append(part2)
                logger.info(f"[자막 분할] CTA 2분할: '{part1}' / '{part2}'")
            else:
                result.append(combined_cta)
                logger.info(f"[자막 분할] CTA 합침: {len(preserved_cta)}개 → 1개 ('{combined_cta}')")

    logger.info(f"[자막 분할] 최종 결과: {len(result)}개 세그먼트")
    for i, seg in enumerate(result):
        logger.debug(f"  {i+1}. [{len(seg)}자] {seg}")

    return result


def parse_script_from_text(app, result_text):
    """텍스트에서 대본 구조 파싱"""
    script_lines = []
    lines = result_text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # [타임스탬프] 화자: 대사 형식 파싱
        match = re.match(r'\[([^\]]+)\]\s*([^:]+):\s*(.+)', line)
        if match:
            timestamp = match.group(1)
            speaker = match.group(2).strip()
            text = match.group(3).strip()

            # 톤 마커 제거 (예: [웃으며], [놀라며])
            tone_match = re.search(r'\[([^\]]+)\]\s*(.+)', text)
            if tone_match:
                tone_marker = f"[{tone_match.group(1)}]"
                text = tone_match.group(2).strip()
            else:
                tone_marker = ""

            script_lines.append({
                'timestamp': timestamp,
                'speaker': speaker,
                'text': text,
                'tone_marker': tone_marker
            })


    if not script_lines and result_text:
        fallback_lines = []
        for idx, raw in enumerate(result_text.splitlines()):
            cleaned = raw.strip()
            if not cleaned:
                continue
            cleaned = re.sub(r'^[-*\d\.)\s]+', '', cleaned).strip()
            if len(cleaned) < 5 or cleaned.startswith('#'):
                continue
            fallback_lines.append({
                'timestamp': f"00:{idx:02d}",
                'speaker': '화자',
                'text': cleaned,
                'tone_marker': ''
            })
        if fallback_lines:
            logger.info(f"[배치 분석] 파싱된 대사가 없어 기본 규칙으로 {len(fallback_lines)}줄 추출")
            script_lines.extend(fallback_lines)
    return script_lines


def save_wave_file(app, filename, audio_data, channels=1, rate=24000, sample_width=2):
    """Persist WAV audio data returned by Gemini TTS."""
    try:
        if isinstance(audio_data, str):
            binary_data = base64.b64decode(audio_data)
        else:
            binary_data = audio_data or b""

        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

        if binary_data.startswith(b"RIFF"):
            with open(filename, "wb") as f:
                f.write(binary_data)
        else:
            with wave.open(filename, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(sample_width)
                wf.setframerate(rate)
                wf.writeframes(binary_data)

        logger.info(f"[WAV save] ok: {filename} ({len(binary_data)} bytes)")

    except Exception as exc:
        ui_controller.write_error_log(exc)
        logger.warning(f"[WAV save] failed: {exc}")
        try:
            with open(filename, "wb") as f:
                if isinstance(audio_data, str):
                    f.write(base64.b64decode(audio_data))
                else:
                    f.write(audio_data or b"")
        except Exception as fallback_exc:
            logger.error(f"[WAV save] fallback failed: {fallback_exc}")
            raise fallback_exc
