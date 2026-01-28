# NewshoppingShortsMaker

쇼핑 숏폼 영상 자동 제작 도구 | Automated Shopping Shorts Video Creator

중국어 자막을 제거하고 한국어 TTS를 추가하여 쇼핑 숏폼 콘텐츠를 자동으로 생성합니다.

---

## ✨ 주요 기능

- **🎯 OCR 기반 자막 감지**: Tesseract/RapidOCR로 중국어 자막 자동 인식
- **🚀 GPU 가속**: CuPy를 통한 CUDA 가속 지원 (선택사항)
- **🔊 AI 음성 생성**: Gemini API를 활용한 자연스러운 한국어 TTS
- **📹 자동 비디오 처리**: 자막 블러 처리, 한국어 자막 추가, 영상 합성
- **⚡ 병렬 처리**: 다중 세그먼트 동시 처리로 빠른 작업 속도
- **🛡️ 안정성 강화**: 포괄적인 에러 처리, 입력 검증, 자동 재시도

---

## 📋 시스템 요구사항

### 필수 요구사항

- **Python**: 3.12 - 3.14 (최신 버전 권장)
- **FFmpeg**: 비디오 처리용
- **Tesseract OCR**: 자막 인식용

### 선택사항 (권장)

- **NVIDIA GPU + CUDA**: GPU 가속 (2-3배 빠른 처리)
- **CuPy**: GPU 가속 라이브러리

---

## 🚀 빠른 시작

### 1. 저장소 클론

```bash
git clone https://github.com/yourusername/NewshoppingShortsMaker.git
cd NewshoppingShortsMaker
```

### 2. 의존성 설치

**자동 설치 (권장)**:
```bash
python install_dependencies.py
```

**수동 설치**:
```bash
pip install -r requirements.txt
```

### 3. 시스템 검증

설치가 올바르게 되었는지 확인:
```bash
python scripts/startup_validation.py
```

**예상 출력**:
```
✓ Python Version: Python 3.14.x
✓ Required Packages: 6 packages installed
✓ OCR Engine: Tesseract OCR available
✓ FFmpeg: FFmpeg available
✓ File Permissions: Write permissions OK

✓ All checks passed! Ready to run.
```

### 4. OCR 엔진 설치 (Tesseract)

**Windows**:
```bash
winget install UB-Mannheim.TesseractOCR
```

**macOS**:
```bash
brew install tesseract tesseract-lang
```

**Linux**:
```bash
sudo apt install tesseract-ocr tesseract-ocr-kor tesseract-ocr-chi-sim
```

### 5. API 키 설정

**방법 1: 환경 변수 (권장)**
```bash
# Windows
set GEMINI_API_KEY=your_gemini_api_key_here

# Linux/macOS
export GEMINI_API_KEY=your_gemini_api_key_here
```

**방법 2: UI에서 설정**
- 앱 실행 후 "API 키 관리"에서 추가

### 6. 앱 실행

```bash
python main.py
```

---

## 🎮 사용 방법

### 기본 워크플로우

1. **비디오 선택**
   - 로컬 파일 선택 또는 URL 입력 (Douyin, TikTok 지원)

2. **옵션 설정**
   - 중국어 자막 블러: ✅
   - 한국어 자막 추가: ✅
   - TTS 음성 생성: ✅

3. **처리 시작**
   - "영상 처리 시작" 버튼 클릭
   - 진행 상황 실시간 확인

4. **결과 확인**
   - 완료된 영상은 지정한 출력 폴더에 저장
   - 기본: `C:\Users\Administrator\Desktop\`

---

## ⚙️ 고급 설정

### GPU 가속 활성화

**1. CUDA 설치 확인**:
```bash
nvidia-smi
```

**2. CuPy 설치**:
```bash
# CUDA 12.x
pip install cupy-cuda12x

# CUDA 11.x
pip install cupy-cuda11x
```

**3. GPU 가용성 확인**:
```python
import cupy as cp
print(f"GPU devices: {cp.cuda.runtime.getDeviceCount()}")
```

### 환경 변수 설정

| 변수 | 설명 | 예시 |
|------|------|------|
| `GEMINI_API_KEY` | Gemini API 키 | `AIza...` |
| `TESSERACT_CMD` | Tesseract 실행 파일 경로 | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `TESSDATA_PREFIX` | Tesseract 언어 데이터 경로 | `C:\Program Files\Tesseract-OCR\tessdata` |

---

## 🧪 테스트 실행

```bash
# 모든 테스트 실행
pytest

# 특정 카테고리만 실행
pytest -m unit  # 유닛 테스트만
pytest tests/unit/test_validators.py  # 특정 파일만

# 커버리지 포함
pytest --cov=. --cov-report=html
```

---

## 📂 프로젝트 구조

```
NewshoppingShortsMaker/
├── main.py                     # 애플리케이션 진입점
├── config/
│   └── constants.py            # 설정 상수 (임계값, 제한값 등)
├── utils/
│   ├── logging_config.py       # 중앙집중식 로깅
│   ├── validators.py           # 입력 검증 (보안)
│   ├── error_handlers.py       # 예외 처리 프레임워크
│   └── ocr_backend.py          # OCR 엔진 래퍼
├── processors/
│   ├── subtitle_detector.py    # 자막 감지 (OCR)
│   ├── subtitle_processor.py   # 자막 블러 처리
│   └── tts_processor.py        # TTS 생성
├── managers/
│   ├── settings_manager.py     # 설정 관리
│   └── voice_manager.py        # 음성 관리
├── ui/
│   ├── components/             # UI 컴포넌트
│   └── panels/                 # UI 패널
├── scripts/
│   └── startup_validation.py   # 시스템 사전 검사
├── tests/
│   ├── unit/                   # 유닛 테스트
│   ├── integration/            # 통합 테스트
│   └── conftest.py             # 테스트 설정
└── docs/
    └── IMPROVEMENTS.md         # 개선사항 문서
```

---

## 🛠️ 문제 해결

### OCR이 작동하지 않음

**증상**: "OCR reader not initialized" 에러

**해결**:
1. Tesseract 설치 확인:
   ```bash
   tesseract --version
   ```

2. Tesseract 경로 설정:
   ```bash
   set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

3. 언어 데이터 설치 확인:
   - `chi_sim.traineddata` (중국어 간체)
   - `kor.traineddata` (한국어)

### GPU 가속이 작동하지 않음

**증상**: "GPU acceleration disabled" 메시지

**해결**:
1. NVIDIA GPU 확인:
   ```bash
   nvidia-smi
   ```

2. CUDA 설치 확인:
   - CUDA Toolkit 11.8 또는 12.x 필요

3. CuPy 재설치:
   ```bash
   pip uninstall cupy cupy-cuda12x
   pip install cupy-cuda12x
   ```

4. **Python 3.14 주의사항**:
   - CuPy가 설치되지 않으면 자동으로 NumPy CPU 모드로 전환됩니다
   - 기능은 정상 작동하지만 속도가 느릴 수 있습니다

### API 키 오류

**증상**: "등록된 API 키가 없습니다"

**해결**:
1. 환경 변수 설정:
   ```bash
   set GEMINI_API_KEY=your_key_here
   ```

2. 또는 UI에서 "API 키 관리" → 키 추가

3. `api_keys_config.json` 직접 편집:
   ```json
   {
     "gemini": {
       "key_1": "AIza..."
     }
   }
   ```

---

## 📊 성능 최적화 팁

### 1. GPU 가속 활용
- NVIDIA GPU 사용 시 2-3배 빠른 처리
- CuPy 설치 권장

### 2. 병렬 처리 최적화
- CPU 코어 수에 따라 자동 조정
- `config/constants.py`에서 `MAX_WORKERS` 조정 가능

### 3. OCR 샘플링 간격 조정
- 기본: 0.3초 간격
- `VideoSettings.SAMPLE_INTERVAL_DEFAULT` 조정

### 4. 메모리 최적화
- 프레임 캐시는 자동 정리됨
- 긴 영상 처리 시 10초 세그먼트로 분할 처리

---

## 🔒 보안 기능

- ✅ **경로 순회 공격 방지**: 파일 경로 검증
- ✅ **파일 확장자 화이트리스트**: 안전한 파일만 허용
- ✅ **API 응답 검증**: 악의적인 API 응답 차단
- ✅ **환경 변수 API 키**: 평문 저장 방지
- ✅ **입력 검증**: SQL 인젝션, XSS 방지

---

## 📈 최근 개선사항

### Phase 1-2 (2026-01-24 완료)

#### 새로 추가된 기능
- ✅ 중앙집중식 로깅 시스템 (파일 + 콘솔)
- ✅ 포괄적인 입력 검증 (보안 강화)
- ✅ 타입화된 예외 처리 (복구 힌트 포함)
- ✅ 시스템 사전 검사 스크립트
- ✅ 환경 변수 API 키 지원

#### 수정된 문제
- ✅ OCR 초기화 실패 → 명확한 에러 + 재시도 (3회)
- ✅ Python 3.14 호환성 → Graceful fallback
- ✅ 중복 detector 생성 → 40% 성능 개선
- ✅ 메모리 누수 → 프레임 캐시 자동 정리
- ✅ GPU detection 개선 → 버전 체크 제거

자세한 내용은 [IMPROVEMENTS.md](IMPROVEMENTS.md) 참조

---

## 🤝 기여하기

버그 리포트, 기능 제안, Pull Request를 환영합니다!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능

---

## 🙏 도움말 및 지원

- **이슈 리포트**: [GitHub Issues](https://github.com/yourusername/NewshoppingShortsMaker/issues)
- **문서**: [docs/](docs/) 폴더 참조
- **개선사항**: [IMPROVEMENTS.md](IMPROVEMENTS.md)

---

## 🎉 감사합니다!

NewshoppingShortsMaker를 사용해주셔서 감사합니다. 쇼핑 숏폼 제작이 더 쉬워지길 바랍니다!

---

*Last Updated: 2026-01-24*
