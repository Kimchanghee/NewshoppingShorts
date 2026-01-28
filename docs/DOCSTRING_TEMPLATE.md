# Docstring Template Guide

Python Docstring 작성 가이드

---

## 목적 / Purpose

**Why Docstrings?**
- API 문서 자동 생성 / Auto-generate API documentation
- IDE 자동완성 지원 / IDE autocomplete support
- 코드 이해도 향상 / Improve code understanding
- 타입 힌팅 보완 / Complement type hinting

---

## 스타일 가이드 / Style Guide

**사용 스타일 / Style**: Google Style Python Docstrings

**참고 문서 / Reference**:
- https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings

---

## 함수 Docstring / Function Docstring

### 템플릿 / Template

```python
def function_name(param1: type1, param2: type2) -> return_type:
    """
    함수의 간단한 설명 (한 줄)
    One-line summary of the function

    더 자세한 설명 (선택사항)
    More detailed explanation (optional)

    Args:
        param1: 첫 번째 매개변수 설명 / Description of first parameter
        param2: 두 번째 매개변수 설명 / Description of second parameter

    Returns:
        반환값 설명 / Description of return value

    Raises:
        ExceptionType: 예외 발생 조건 / When this exception is raised

    Example:
        >>> result = function_name(arg1, arg2)
        >>> print(result)
        expected output
    """
    pass
```

### 실제 예시 / Real Example

```python
def validate_video_path(path: str) -> Path:
    """
    비디오 파일 경로 검증 및 정규화
    Validate and normalize video file path

    경로 순회 공격을 방지하고, 허용된 확장자만 통과시킵니다.
    Prevents path traversal attacks and only allows whitelisted extensions.

    Args:
        path: 검증할 비디오 파일 경로 (상대 또는 절대 경로)
              Video file path to validate (relative or absolute)

    Returns:
        검증된 절대 경로 / Validated absolute path

    Raises:
        ValidationError: 경로 순회 시도 또는 잘못된 확장자
                        Path traversal attempt or invalid extension
        FileNotFoundError: 파일이 존재하지 않음
                          File does not exist

    Example:
        >>> path = validate_video_path("/videos/sample.mp4")
        >>> print(path)
        /absolute/path/to/videos/sample.mp4
    """
    pass
```

---

## 클래스 Docstring / Class Docstring

### 템플릿 / Template

```python
class ClassName:
    """
    클래스의 간단한 설명 (한 줄)
    One-line summary of the class

    더 자세한 설명 (선택사항)
    More detailed explanation (optional)

    Attributes:
        attr1: 첫 번째 속성 설명 / Description of first attribute
        attr2: 두 번째 속성 설명 / Description of second attribute

    Example:
        >>> obj = ClassName(arg1, arg2)
        >>> obj.method()
    """

    def __init__(self, param1: type1, param2: type2):
        """
        클래스 초기화
        Initialize the class

        Args:
            param1: 첫 번째 매개변수 설명
            param2: 두 번째 매개변수 설명
        """
        self.attr1 = param1
        self.attr2 = param2
```

### 실제 예시 / Real Example

```python
class SubtitleDetector:
    """
    OCR 기반 중국어 자막 감지기
    OCR-based Chinese subtitle detector

    비디오 프레임에서 OCR을 사용하여 중국어 자막 영역을 감지합니다.
    GPU 가속(CuPy)을 지원하며, 하이브리드 감지 모드를 제공합니다.

    Detects Chinese subtitle regions in video frames using OCR.
    Supports GPU acceleration (CuPy) with hybrid detection mode.

    Attributes:
        gui: GUI 객체 (OCR 리더 포함) / GUI object (contains OCR reader)
        ocr_reader: OCR 엔진 인스턴스 / OCR engine instance
        ssim_threshold: SSIM 임계값 (기본 0.98) / SSIM threshold (default 0.98)
        use_hybrid: 하이브리드 감지 모드 사용 여부 / Whether to use hybrid detection

    Example:
        >>> detector = SubtitleDetector(gui)
        >>> regions = detector.detect_subtitles_with_opencv()
        >>> print(f"Found {len(regions)} subtitle regions")
    """

    def __init__(self, gui):
        """
        자막 감지기 초기화 / Initialize subtitle detector

        Args:
            gui: MainWindow 객체 (ocr_reader 속성 포함)
                 MainWindow object (with ocr_reader attribute)
        """
        self.gui = gui
        self.ocr_reader = gui.ocr_reader
```

---

## 모듈 Docstring / Module Docstring

### 템플릿 / Template

```python
"""
모듈 이름 / Module Name

모듈의 목적과 주요 기능 설명
Description of module purpose and main functionality

주요 클래스/함수:
Main classes/functions:
- ClassName: 클래스 설명 / Class description
- function_name: 함수 설명 / Function description

사용 예시 / Example:
    from module_name import ClassName

    obj = ClassName()
    result = obj.method()
"""
```

### 실제 예시 / Real Example

```python
"""
Subtitle Detection Processor

This module handles OCR-based Chinese subtitle detection with GPU/NumPy acceleration.
Integrates HybridSubtitleDetector for optimized OCR calls (40% reduction).

이 모듈은 GPU/NumPy 가속을 지원하는 OCR 기반 중국어 자막 감지를 처리합니다.
하이브리드 자막 감지기를 통합하여 OCR 호출을 40% 감소시켰습니다.

Main classes:
    SubtitleDetector: OCR 기반 자막 영역 감지 / OCR-based subtitle region detection

Usage:
    from processors.subtitle_detector import SubtitleDetector

    detector = SubtitleDetector(gui)
    regions = detector.detect_subtitles_with_opencv()
"""
```

---

## 타입 힌트와 함께 사용 / Use with Type Hints

### 타입 힌트가 있는 경우 / With Type Hints

타입 힌트가 이미 제공되므로 docstring에서 반복하지 않습니다.
Since type hints are already provided, don't repeat them in docstrings.

```python
def process_frame(
    frame: np.ndarray,
    threshold: float = 0.98,
    use_gpu: bool = True
) -> List[Dict[str, Any]]:
    """
    프레임에서 자막 영역 감지
    Detect subtitle regions in frame

    Args:
        frame: BGR 형식 비디오 프레임 (H, W, 3)
               Video frame in BGR format (H, W, 3)
        threshold: OCR 신뢰도 임계값 [0.0-1.0] (기본값: 0.98)
                   OCR confidence threshold [0.0-1.0] (default: 0.98)
        use_gpu: GPU 가속 사용 여부 (기본값: True)
                 Whether to use GPU acceleration (default: True)

    Returns:
        감지된 영역 리스트, 각 영역은 bbox, text, confidence 포함
        List of detected regions, each contains bbox, text, confidence
    """
    pass
```

---

## Property Docstring

```python
@property
def is_gpu_available(self) -> bool:
    """
    GPU 가속 사용 가능 여부
    Whether GPU acceleration is available

    CuPy가 설치되어 있고 CUDA 디바이스가 감지된 경우 True를 반환합니다.
    Returns True if CuPy is installed and CUDA device is detected.

    Returns:
        GPU 사용 가능 여부 / Whether GPU is available
    """
    return GPU_ACCEL_AVAILABLE
```

---

## 짧은 함수 / Short Functions

간단한 함수는 한 줄 설명만으로 충분합니다.
Simple functions only need one-line summaries.

```python
def clear_cache(self) -> None:
    """프레임 캐시 클리어 / Clear frame cache"""
    self.frame_cache.clear()

def get_frame_count(self) -> int:
    """총 프레임 수 반환 / Return total frame count"""
    return self.total_frames
```

---

## Deprecated Functions

```python
def old_function(param: str) -> str:
    """
    구식 함수 - 사용하지 마세요
    Deprecated function - do not use

    .. deprecated:: 2.0
        대신 :func:`new_function` 사용
        Use :func:`new_function` instead

    Args:
        param: 매개변수 / Parameter

    Returns:
        결과 / Result
    """
    import warnings
    warnings.warn("old_function is deprecated, use new_function instead",
                  DeprecationWarning)
    return new_function(param)
```

---

## 자동 생성 도구 / Auto-generation Tools

### Sphinx

```bash
# Install Sphinx
pip install sphinx sphinx-rtd-theme

# Generate documentation
sphinx-apidoc -o docs/api .
cd docs
make html
```

### VSCode Extension

**autoDocstring**: Python Docstring Generator
- 단축키: `Ctrl+Shift+2` (Windows/Linux)
- 함수 위에서 `"""` 입력 후 엔터

---

## 우선순위 / Priority

### High Priority (반드시 작성)

1. **Public API** - 외부에서 호출하는 함수/클래스
   - `utils/*.py`의 모든 public 함수
   - `processors/*.py`의 주요 클래스

2. **Complex Functions** - 복잡한 알고리즘
   - `detect_subtitles_with_opencv()`
   - `process_frame()`
   - `filter_regions()`

### Medium Priority

3. **Internal Functions** - 내부 함수 (간단한 설명만)
   - `_helper_function()`
   - `_validate_input()`

### Low Priority

4. **Trivial Functions** - 자명한 함수 (생략 가능)
   - Getters/setters
   - 한 줄짜리 wrapper 함수

---

## 검증 / Verification

### Docstring 커버리지 확인 / Check Docstring Coverage

```bash
# Install interrogate
pip install interrogate

# Check docstring coverage
interrogate -v .

# Fail if coverage < 80%
interrogate --fail-under 80 .
```

### Linting

```bash
# Install pydocstyle
pip install pydocstyle

# Check docstring style
pydocstyle processors/
```

---

## 완료 기준 / Completion Criteria

- [ ] 모든 public 함수/클래스에 docstring 작성
- [ ] 모든 docstring에 Args, Returns 포함
- [ ] 복잡한 함수는 Example 포함
- [ ] interrogate 80%+ 달성

---

**Last Updated**: 2026-01-25
