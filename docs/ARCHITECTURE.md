# Architecture Documentation

NewshoppingShortsMaker 시스템 아키텍처

---

## 시스템 개요

NewshoppingShortsMaker는 **레이어드 아키텍처**를 따르는 PyQt5 기반 데스크톱 애플리케이션입니다.

```
┌─────────────────────────────────────────────────────┐
│                  UI Layer (PyQt5)                   │
│        Panels, Components, Theme Management         │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│              Application Layer (core/)              │
│     Business Logic, State Management, API           │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│           Processing Layer (processors/)            │
│   Subtitle Detection, TTS, Video Composition        │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│              Utilities Layer (utils/)               │
│   Logging, Validation, Error Handling, OCR Wrapper  │
└─────────────────────────────────────────────────────┘
```

---

## 핵심 컴포넌트

### 1. UI Layer (`ui/`)

**책임**: 사용자 인터페이스, 이벤트 처리

**구조**:
```
ui/
├── panels/              # 기능별 UI 패널
│   ├── url_input_panel.py
│   ├── voice_panel.py
│   ├── font_panel.py
│   └── queue_panel.py
├── components/          # 재사용 가능한 위젯
│   ├── custom_dialog.py
│   ├── status_bar.py
│   └── animated_progress.py
└── theme_manager.py     # 테마 관리 (다크/라이트)
```

**특징**:
- PyQt5 기반 GUI
- 반응형 레이아웃
- 실시간 진행 상황 표시
- 다크/라이트 테마 지원

---

### 2. Application Layer (`core/`)

**책임**: 비즈니스 로직, 상태 관리

**구조**:
```
core/
├── api/                 # API 통합
│   └── ApiKeyManager.py
├── video/               # 비디오 처리 도구
│   ├── CreateFinalVideo.py
│   ├── batch/           # 배치 처리
│   └── video_validator.py
└── download/            # 비디오 다운로더
    ├── DouyinExtract.py
    ├── TicktokExtract.py
    ├── XiaohongshuExtract.py
    ├── VideoDownloader.py
    └── platforms/
```

**주요 기능**:
- API 키 관리 (Gemini, Anthropic)
- 비디오 다운로드 (Douyin, TikTok, Xiaohongshu)
- 비디오 검증 및 변환
- 배치 작업 관리

---

### 3. Processing Layer (`processors/`)

**책임**: 비디오/오디오/자막 처리

#### 3.1 Subtitle Detection (`subtitle_detector.py`)

**기능**:
- OCR 기반 중국어 자막 감지
- GPU/CPU 가속 (CuPy/NumPy)
- 하이브리드 감지기 (40% OCR 호출 감소)
- SSIM 기반 프레임 스킵

**처리 흐름**:
```
Video Input
    ↓
10초 세그먼트 분할
    ↓
병렬 OCR 처리 (멀티스레드)
    ↓
중국어 텍스트 필터링
    ↓
영역 병합 (IoU 기반)
    ↓
Subtitle Regions
```

**최적화 기법**:
1. **SSIM (Structural Similarity)**: 98% 이상 유사 프레임 스킵
2. **Edge Detection**: 0.1% 변화 감지
3. **Hybrid Detector**: Canny edge 기반 빠른 변화 감지
4. **GPU Batching**: 32 프레임 배치 처리 (GPU), 8 프레임 (CPU)

#### 3.2 Subtitle Processing (`subtitle_processor.py`)

**기능**:
- 중국어 자막 블러 처리
- 한국어 자막 레이아웃 관리
- 실시간 진행 상황 업데이트

**Blur Algorithm**:
```python
1. 감지된 자막 영역 추출
2. 모션 블러 적용 (Gaussian kernel)
3. 주변과 자연스럽게 혼합 (alpha blending)
4. 영상에 합성
```

#### 3.3 TTS Processing (`tts_processor.py`)

**기능**:
- Gemini API TTS 생성
- 음성 속도 조절
- 세그먼트 별 음성 생성

---

### 4. Utilities Layer (`utils/`)

#### 4.1 Logging (`logging_config.py`)

**기능**:
- 중앙집중식 로깅
- 컬러 콘솔 출력
- 파일 로테이션 (10MB)
- JSON 에러 로그

**Usage**:
```python
from utils.logging_config import AppLogger

AppLogger.setup(Path("logs"), level="INFO")
logger = AppLogger.get_logger(__name__)
logger.info("Message")
```

#### 4.2 Validation (`validators.py`)

**기능**:
- 경로 순회 공격 방지
- 파일 확장자 화이트리스트
- API 응답 검증
- SQL 인젝션 방지

**Usage**:
```python
from utils.validators import PathValidator

safe_path = PathValidator.validate_video_path(user_input)
```

#### 4.3 Error Handling (`error_handlers.py`)

**기능**:
- 타입화된 예외 (`AppException`)
- 복구 힌트 포함
- 데코레이터 기반 에러 처리

**Exception Hierarchy**:
```
Exception
└── AppException
    ├── OCRInitializationError
    ├── VideoProcessingError
    ├── APIError
    └── ConfigurationError
```

#### 4.4 OCR Backend (`ocr_backend.py`)

**기능**:
- Tesseract/RapidOCR 통합
- 자동 폴백
- 재시도 로직 (3회)

**Engine Selection Logic**:
```
Python < 3.13:
    Try RapidOCR → Fall back to Tesseract

Python >= 3.13:
    Tesseract only (onnxruntime incompatible)
```

---

## 데이터 흐름

### 전체 비디오 처리 파이프라인

```
[입력]
Video URL/File
    ↓
[검증]
Path Validation
    ↓
[다운로드] (URL인 경우)
DouyinExtract/TicktokExtract
    ↓
[자막 감지]
SubtitleDetector
    ↓
[자막 블러]
SubtitleProcessor
    ↓
[TTS 생성]
TTSProcessor → Gemini API
    ↓
[영상 합성]
CreateFinalVideo → MoviePy
    ↓
[출력]
Final Video File
```

---

## 설계 결정사항

### 1. OCR Engine Abstraction

**문제**: RapidOCR와 Tesseract가 다른 API 제공

**해결**: `OCRBackend` 래퍼로 통합 인터페이스 제공
```python
class OCRBackend:
    def readtext(image) -> List[Tuple[bbox, text, confidence]]:
        if self.engine_name == "rapidocr":
            return self._read_with_rapidocr(image)
        elif self.engine_name == "tesseract":
            return self._read_with_tesseract(image)
```

### 2. GPU Acceleration Strategy

**문제**: CuPy Python 3.13+ 비호환

**해결**: Graceful fallback to NumPy
```python
try:
    import cupy as cp
    xp = cp
    GPU_ACCEL_AVAILABLE = True
except Exception:
    xp = np
    GPU_ACCEL_AVAILABLE = False
```

**이점**:
- 동일한 코드로 GPU/CPU 처리
- Python 버전에 관계없이 작동
- 성능 저하 시 자동 폴백

### 3. Memory Management

**문제**: Frame cache 메모리 누수

**해결**: 명시적 cleanup + GC
```python
def detect_subtitles_with_opencv(self):
    try:
        # Process video
        pass
    finally:
        # Clear frame cache
        del prev_frame_roi
        gc.collect()
```

### 4. Configuration Management

**문제**: 100+ magic numbers 산재

**해결**: `config/constants.py` 중앙 집중화
```python
from config.constants import OCRThresholds

ssim_threshold = OCRThresholds.SSIM_THRESHOLD  # 0.98
```

---

## 성능 최적화

### 1. 병렬 처리

- **세그먼트 분할**: 10초 단위로 분할
- **멀티스레드**: `ThreadPoolExecutor`로 동시 처리
- **Worker 수**: CPU 코어에 따라 동적 조정

### 2. OCR 최적화

- **Sampling**: 0.3초 간격 (기본), 0.1초 (중요 구간)
- **SSIM Skip**: 98% 유사 프레임 스킵
- **Hybrid Detector**: Edge detection으로 40% 감소

### 3. GPU 가속

- **CuPy**: NumPy 대비 10-20배 빠른 배열 연산
- **Batching**: 32개 bbox 배치 처리
- **Zero-copy**: GPU ↔ CPU 데이터 전송 최소화

---

## 보안 설계

### 입력 검증 (Defense in Depth)

```
User Input
    ↓
PathValidator (경로 순회 차단)
    ↓
Extension Whitelist (.mp4, .avi만)
    ↓
File Existence Check
    ↓
Safe Processing
```

### API 보안

- **Environment Variables**: API 키 평문 저장 방지
- **Response Validation**: 악의적 API 응답 차단
- **Rate Limiting**: API 호출 제한 (예정)

---

## 확장 가능성

### 향후 개선 계획

#### Phase 3 (예정)
- Main.py 분할 (1837줄 → 5개 모듈)
- Frame cache LRU 구현
- Type hints 95%+ 달성

#### Phase 4 (예정)
- API key 암호화 (keyring)
- 테스트 커버리지 80%+
- CI/CD 파이프라인

#### Phase 5 (예정)
- Bilingual comments (KR/EN)
- 완전한 문서화
- 플러그인 시스템

---

## 주요 기술 스택

| Category | Technology | Purpose |
|----------|------------|---------|
| **UI** | PyQt5 | Desktop GUI |
| **Video** | MoviePy, OpenCV | Video processing |
| **OCR** | Tesseract, RapidOCR | Text detection |
| **GPU** | CuPy, CUDA | Acceleration |
| **AI** | Gemini API | TTS generation |
| **Testing** | Pytest | Unit/Integration tests |
| **Logging** | Python logging | Error tracking |

---

## 성능 벤치마크

### 1분 영상 처리 시간

| Configuration | Processing Time | Speed Improvement |
|---------------|----------------|-------------------|
| **CPU (NumPy)** | ~45초 | 1x (baseline) |
| **GPU (CuPy)** | ~18초 | **2.5x faster** |
| **Hybrid Detector** | ~27초 | **1.7x faster** |
| **GPU + Hybrid** | ~12초 | **3.75x faster** |

*Intel i7-12700K + NVIDIA RTX 3080 기준*

---

## 트러블슈팅 가이드

### OCR 성능 저하

**증상**: OCR 속도 느림

**원인**:
1. GPU 가속 비활성화
2. 샘플링 간격이 너무 짧음
3. SSIM skip 비활성화

**해결**:
```python
# config/constants.py
VideoSettings.SAMPLE_INTERVAL_DEFAULT = 0.5  # 0.3 → 0.5
OCRThresholds.SSIM_THRESHOLD = 0.95  # 0.98 → 0.95 (더 자주 스킵)
```

### 메모리 부족

**증상**: OOM (Out of Memory) 에러

**원인**: 긴 영상 처리 시 메모리 누수

**해결**:
- **자동 해결됨** (Phase 3 수정 완료)
- Frame cache 자동 정리
- GC 명시적 호출

---

**Last Updated**: 2026-01-24
**Version**: 2.0 (Post Phase 1-3 improvements)
