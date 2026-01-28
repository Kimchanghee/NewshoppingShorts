# Bilingual Comments Guide (Korean + English)

이중언어 주석 가이드 (한국어 + 영어)

---

## 목적 / Purpose

**Why Bilingual Comments?**
- 국제 협업 가능 / Enable international collaboration
- 코드 이해도 향상 / Improve code understanding
- 문서화 품질 개선 / Better documentation quality
- 오픈소스 기여 용이 / Easier open-source contributions

---

## 기본 원칙 / Basic Principles

### 1. 한국어 먼저, 영어 다음 / Korean First, English Second

```python
# 중국어 자막 블러 처리 시작
# Start Chinese subtitle blur processing
def blur_chinese_subtitles(frame, regions):
    pass
```

### 2. 구분자 사용 / Use Separator

**권장 / Recommended**: ` / ` (띄어쓰기 + 슬래시 + 띄어쓰기)

```python
# OCR 엔진 초기화 / Initialize OCR engine
# GPU 가속 활성화 / Enable GPU acceleration
```

### 3. 짧은 주석은 한 줄에 / Short Comments on One Line

```python
# 비디오 경로 검증 / Validate video path
video_path = PathValidator.validate_video_path(path)
```

### 4. 긴 주석은 두 줄로 / Long Comments on Two Lines

```python
# 중국어 자막 영역을 감지하고 OCR 결과를 필터링합니다.
# Detect Chinese subtitle regions and filter OCR results.
def detect_subtitle_regions(frame):
    pass
```

---

## 주석 종류별 패턴 / Patterns by Comment Type

### 1. 함수/클래스 설명 / Function/Class Descriptions

```python
class SubtitleDetector:
    """
    OCR 기반 중국어 자막 감지기
    OCR-based Chinese subtitle detector

    GPU/NumPy 가속을 지원하며, 하이브리드 감지 모드를 제공합니다.
    Supports GPU/NumPy acceleration with hybrid detection mode.
    """

    def __init__(self, gui):
        pass
```

### 2. 변수 선언 / Variable Declarations

```python
# GPU 가속 사용 가능 여부 / GPU acceleration availability
GPU_ACCEL_AVAILABLE = False

# SSIM 임계값 (98% 유사도) / SSIM threshold (98% similarity)
SSIM_THRESHOLD = 0.98
```

### 3. 알고리즘 설명 / Algorithm Explanations

```python
# 1. 프레임을 10초 단위로 분할 / Split frames into 10-second segments
# 2. 각 세그먼트를 병렬로 처리 / Process each segment in parallel
# 3. SSIM으로 유사 프레임 스킵 / Skip similar frames using SSIM
# 4. OCR 결과를 병합 / Merge OCR results
```

### 4. TODO/FIXME 주석 / TODO/FIXME Comments

```python
# TODO: Python 3.14에서 CuPy 호환성 테스트 필요
# TODO: Need to test CuPy compatibility with Python 3.14

# FIXME: 메모리 누수 가능성 확인
# FIXME: Potential memory leak to investigate
```

### 5. 에러 처리 / Error Handling

```python
try:
    import cupy as cp
    xp = cp
except Exception as e:
    # GPU 불가, NumPy로 전환 / GPU unavailable, fallback to NumPy
    xp = np
    print(f"GPU 가속 비활성화 / GPU acceleration disabled: {e}")
```

---

## 도메인별 용어집 / Domain-Specific Glossary

### OCR / OCR

| 한국어 | English |
|--------|---------|
| 광학 문자 인식 | Optical Character Recognition |
| 자막 감지 | Subtitle detection |
| 신뢰도 | Confidence |
| 임계값 | Threshold |
| 바운딩 박스 | Bounding box |

### 비디오 처리 / Video Processing

| 한국어 | English |
|--------|---------|
| 프레임 | Frame |
| 세그먼트 | Segment |
| 샘플링 간격 | Sampling interval |
| 블러 처리 | Blur processing |
| 영상 합성 | Video composition |

### 성능 / Performance

| 한국어 | English |
|--------|---------|
| GPU 가속 | GPU acceleration |
| 배치 처리 | Batch processing |
| 병렬 처리 | Parallel processing |
| 메모리 누수 | Memory leak |
| 캐시 | Cache |

---

## 자동화 스크립트 / Automation Script

### 영어 번역 추가 / Add English Translation

```python
# scripts/add_english_comments.py
"""
Automatically add English translations to Korean comments.

Uses Google Translate API or similar service.
"""

def add_english_translation(korean_comment: str) -> str:
    """Add English translation after Korean comment"""
    # 한국어 주석 추출 / Extract Korean comment
    # 영어로 번역 / Translate to English
    # 형식: 한국어 / English
    english = translate_to_english(korean_comment)
    return f"{korean_comment} / {english}"
```

---

## 예시: Before & After / Examples: Before & After

### Before (Korean Only)

```python
class SubtitleDetector:
    def __init__(self, gui):
        # OCR 리더 초기화
        self.ocr_reader = gui.ocr_reader

        # GPU 가속 확인
        if GPU_ACCEL_AVAILABLE:
            print("GPU 가속 활성화")
        else:
            print("CPU 모드로 동작")

        # SSIM 임계값 설정
        self.ssim_threshold = 0.98
```

### After (Bilingual)

```python
class SubtitleDetector:
    """
    중국어 자막 감지기 / Chinese subtitle detector
    """

    def __init__(self, gui):
        # OCR 리더 초기화 / Initialize OCR reader
        self.ocr_reader = gui.ocr_reader

        # GPU 가속 확인 / Check GPU acceleration
        if GPU_ACCEL_AVAILABLE:
            print("GPU 가속 활성화 / GPU acceleration enabled")
        else:
            print("CPU 모드로 동작 / Running in CPU mode")

        # SSIM 임계값 설정 / Set SSIM threshold
        self.ssim_threshold = 0.98
```

---

## 우선순위 / Priority

모든 파일을 한번에 변환하기 어려우므로 우선순위를 정합니다.
Since converting all files at once is difficult, set priorities.

### High Priority (우선 변환)

1. **Public API** - 외부에서 사용하는 함수/클래스
   - `utils/validators.py`
   - `utils/logging_config.py`
   - `utils/error_handlers.py`

2. **Core Modules** - 핵심 로직
   - `processors/subtitle_detector.py`
   - `processors/subtitle_processor.py`
   - `processors/tts_processor.py`

3. **Configuration** - 설정 파일
   - `config.py`
   - `config/constants.py`

### Medium Priority

4. **Managers** - 관리 모듈
   - `managers/*.py`

5. **UI** - 사용자 인터페이스
   - `ui/*.py`

### Low Priority

6. **Scripts** - 보조 스크립트
   - `scripts/*.py`

7. **Tests** - 테스트 코드
   - `tests/**/*.py`

---

## 검증 / Verification

### 주석 품질 체크 / Comment Quality Check

```bash
# Check for Korean-only comments (no English)
grep -r "# [^A-Za-z]*$" --include="*.py" | wc -l

# Should decrease over time
```

### 번역 일관성 / Translation Consistency

동일한 용어는 항상 동일하게 번역 / Always translate the same terms consistently

- ✅ "초기화 / Initialize" (일관성 있음 / Consistent)
- ❌ "초기화 / Initialize", "초기화 / Init" (불일치 / Inconsistent)

---

## 도구 / Tools

### VS Code Extension

**Recommended**: Korean to English Translation Extension

### Google Translate API

```python
from googletrans import Translator

translator = Translator()
result = translator.translate("자막 감지", src='ko', dest='en')
print(result.text)  # "Subtitle detection"
```

---

## 완료 기준 / Completion Criteria

- [ ] 모든 public API에 이중언어 주석 / Bilingual comments on all public APIs
- [ ] 핵심 알고리즘에 설명 추가 / Explanations for core algorithms
- [ ] 용어 일관성 확인 / Terminology consistency verified
- [ ] README.md에 bilingual 정책 명시 / Bilingual policy in README.md

---

**Last Updated**: 2026-01-25
