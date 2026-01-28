# 빌드 가이드 - Shopping Shorts Maker

OpenAI Whisper로 완전히 마이그레이션된 버전의 빌드 가이드입니다.

## ⚠️ 중요 변경사항

- ❌ **제거**: `faster-whisper`, `ctranslate2`
- ✅ **추가**: `openai-whisper`, `torch`, `torchaudio`, `tiktoken`
- 🎯 **목표**: 어떤 컴퓨터에서도 오프라인으로 실행 가능한 완전 패키지

---

## 📋 사전 요구사항

### 시스템 요구사항
- **OS**: Windows 10 이상 (64비트)
- **RAM**: 8GB 이상 권장
- **디스크**: 10GB 이상 여유 공간 (빌드 과정에서 사용)
- **인터넷**: 빌드 시에만 필요 (패키지 다운로드)

### 소프트웨어
- Python 3.8 ~ 3.12
- pip (최신 버전)
- PyInstaller

---

## 🔧 빌드 단계

### 1단계: 의존성 설치

```bash
# requirements.txt 사용
pip install -r requirements.txt

# 또는 자동 설치 스크립트 사용
python install_dependencies.py
```

### 2단계: Whisper 모델 사전 다운로드 ⭐ **필수!**

```bash
python download_whisper_models.py
```

**이 단계를 건너뛰면:**
- 빌드된 exe가 첫 실행 시 인터넷에서 모델 다운로드 시도
- 오프라인 환경에서 Whisper 기능 사용 불가

**다운로드되는 모델:**
- `tiny.pt` (~72MB) - 가장 빠른 모델
- `base.pt` (~139MB) - 기본 권장 모델
- `small.pt` (~461MB) - 고품질 모델
- `large-v3.pt` (~2.9GB) - 최고 품질 모델
- **총 크기**: ~3.6GB

**모델 저장 위치:**
- Windows: `C:\Users\<사용자>\.cache\whisper\`
- 이 경로의 모델이 자동으로 빌드에 포함됩니다.

### 3단계: PyInstaller 빌드

```bash
pyinstaller ssmaker.spec
```

**빌드 시간:** 약 5-15분 (시스템 성능에 따라 다름)

**빌드 과정에서 확인할 로그:**
```
[Build] Whisper model included: tiny.pt
[Build] Whisper model included: base.pt
[Build] Whisper model included: small.pt
[Build] Whisper model included: large-v3.pt
[Build] Total Whisper models: 4
```
이 로그가 보이면 성공!

### 4단계: 빌드 결과 확인

```
dist/
└── ssmaker/
    ├── ssmaker.exe          ← 실행 파일 (~91MB)
    └── _internal/           ← 필요한 라이브러리들
        ├── whisper_models/  ← 포함된 Whisper 모델 (~3.6GB)
        │   ├── tiny.pt
        │   ├── base.pt
        │   ├── small.pt
        │   └── large-v3.pt
        ├── torch/
        ├── whisper/
        ├── tiktoken/
        ├── rapidocr_onnxruntime/
        ├── onnxruntime/
        ├── imageio_ffmpeg/
        ├── certifi/
        ├── libssl-3.dll
        └── ...
```

---

## ✅ 테스트

### 빌드 검증 스크립트 실행 ⭐ **권장!**

빌드 전 또는 빌드 후에 검증 스크립트를 실행하여 모든 필수 파일이 포함되었는지 확인하세요:

```bash
python validate_build.py
```

**출력 예시:**
```
============================================================
SSMaker Build Validation Script
============================================================
✓ ssmaker.exe: 87.04 MB
✓ _internal folder
✓ onnxruntime - ONNX Runtime for AI model inference
✓ torch - PyTorch deep learning framework
✓ whisper_models folder
✓   tiny.pt: 72 MB
✓   base.pt: 139 MB
✓   small.pt: 461 MB
✓   large-v3.pt: 2.9 GB
============================================================
✓ ALL CHECKS PASSED - Build is ready for distribution
============================================================
```

### 로컬 테스트 (빌드 머신)
```bash
cd dist\ssmaker
ssmaker.exe
```

### 다른 컴퓨터 테스트
1. `dist\ssmaker` 폴더 전체를 복사
2. **인터넷 연결 끊기** (오프라인 테스트)
3. `ssmaker.exe` 실행
4. 영상 생성 테스트 → Whisper 분석 확인

**확인할 로그:**
```
[OpenAI Whisper STT 분석] 시작...
[OpenAI Whisper] 빌드 포함 모델 사용: C:\...\whisper_models
[OpenAI Whisper] 모델 로드 완료
```

---

## 🐛 트러블슈팅

### 문제 1: "Whisper cache not found" 경고
**원인:** 2단계를 건너뛰었거나 모델 다운로드 실패

**해결:**
```bash
python download_whisper_models.py
pyinstaller ssmaker.spec  # 다시 빌드
```

### 문제 2: 빌드 크기가 너무 큼 (>2GB)
**원인:** PyTorch가 큰 편입니다 (정상)

**최적화:**
- 불필요한 PyTorch 컴포넌트 제거 가능하지만 권장하지 않음
- UPX 압축 이미 적용됨 (`upx=True`)

### 문제 3: "ModuleNotFoundError: No module named 'whisper'"
**원인:** whisper 패키지가 빌드에 포함되지 않음

**해결:** ssmaker.spec 확인
```python
packages_to_collect = [
    ...
    'whisper',  # 이 줄이 있는지 확인
    'torch',
    'tiktoken',
    ...
]
```

### 문제 4: 실행 시 "torch not found" 오류
**원인:** PyTorch가 제대로 빌드되지 않음

**해결:**
```bash
pip install torch --upgrade
pyinstaller --clean ssmaker.spec
```

### 문제 5: 오프라인에서 모델 다운로드 시도
**원인:** 빌드에 모델이 포함되지 않았거나 경로 찾기 실패

**해결:** `whisper_analyzer.py`의 로그 확인
```python
# 이 부분이 실행되는지 확인
if getattr(sys, 'frozen', False):
    bundled_model_dir = os.path.join(base_path, 'whisper_models')
```

---

## 📦 배포

### 배포 파일 생성
```bash
# dist/ssmaker 폴더를 압축
cd dist
powershell Compress-Archive -Path ssmaker -DestinationPath ssmaker_v1.0.zip
```

### 배포 시 주의사항
1. **전체 폴더 배포 필수**
   - `ssmaker.exe`만 단독으로는 작동하지 않음
   - `_internal/`, `whisper_models/` 등 모든 폴더 포함

2. **사용자 시스템 요구사항 안내**
   - Windows 10 이상 (64비트)
   - RAM 8GB 이상
   - Visual C++ 재배포 패키지 (자동 설치됨)

3. **백신 오탐 대응**
   - PyInstaller로 빌드된 exe는 일부 백신에서 오탐 가능
   - 배포 전 VirusTotal 스캔 권장
   - 코드 서명 인증서 적용 권장

---

## 🔍 빌드 검증 체크리스트

빌드 완료 후 다음을 확인하세요:

**자동 검증 (권장):**
- [ ] `python validate_build.py` 실행하여 모든 검사 통과

**수동 검증:**
- [ ] `dist/ssmaker/ssmaker.exe` 존재 (~91MB)
- [ ] `dist/ssmaker/_internal/whisper_models/tiny.pt` 존재 (~72MB)
- [ ] `dist/ssmaker/_internal/whisper_models/base.pt` 존재 (~139MB)
- [ ] `dist/ssmaker/_internal/whisper_models/small.pt` 존재 (~461MB)
- [ ] `dist/ssmaker/_internal/whisper_models/large-v3.pt` 존재 (~2.9GB)
- [ ] `dist/ssmaker/_internal/torch/` 존재
- [ ] `dist/ssmaker/_internal/whisper/` 존재
- [ ] `dist/ssmaker/_internal/tiktoken/` 존재
- [ ] `dist/ssmaker/_internal/onnxruntime/` 존재 (RapidOCR용)
- [ ] `dist/ssmaker/_internal/imageio_ffmpeg/` 존재
- [ ] `dist/ssmaker/_internal/certifi/` 존재
- [ ] exe 실행 시 GUI 정상 표시
- [ ] 영상 생성 시 Whisper 분석 작동
- [ ] 오프라인 환경에서 Whisper 사용 가능

---

## 📊 빌드 크기 참고

| 구성요소 | 크기 |
|---------|------|
| ssmaker.exe | ~91MB |
| PyTorch (torch + torchvision) | ~500MB |
| Whisper 모델 (4개) | ~3.6GB |
| Whisper 패키지 | ~50MB |
| tiktoken | ~20MB |
| RapidOCR + onnxruntime | ~100MB |
| imageio_ffmpeg | ~50MB |
| SSL 라이브러리 (certifi, libssl) | ~10MB |
| 기타 라이브러리 | ~200MB |
| **전체** | **~4.6GB** |

**주의**: Whisper 모델이 전체 크기의 대부분을 차지합니다.

---

## 🎯 최종 확인

빌드가 완료되면 다음을 테스트하세요:

1. **로컬 실행**: `dist\ssmaker\ssmaker.exe` 실행
2. **오프라인 테스트**: 인터넷 끊고 실행
3. **영상 생성 테스트**: 더빙 URL 입력 후 전체 프로세스 실행
4. **Whisper 로그 확인**:
   ```
   [OpenAI Whisper STT 분석] 시작...
   [OpenAI Whisper] 빌드 포함 모델 사용
   [OpenAI Whisper] 모델 로드 완료
   [OpenAI Whisper] 인식 완료!
   ```

모든 단계가 성공하면 배포 준비 완료! 🎉
