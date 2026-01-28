# Faster-Whisper → OpenAI Whisper 마이그레이션 체크리스트

완전한 마이그레이션을 위한 검증 체크리스트입니다.

---

## ✅ 코드 변경 완료 항목

### 1. 핵심 파일 수정
- [x] `core/video/batch/whisper_analyzer.py`
  - [x] `faster_whisper` → `whisper` import
  - [x] `WhisperModel` → `whisper.load_model()`
  - [x] API 호출 방식 변경 (`transcribe` 파라미터)
  - [x] 결과 처리 방식 변경 (`.get()` 사용)
  - [x] CTranslate2 환경 설정 함수 제거
  - [x] onnxruntime VAD 환경 설정 함수 제거
  - [x] 번들 모델 경로 처리 추가

### 2. 설정 파일 수정
- [x] `requirements.txt`
  - [x] `faster-whisper` 제거
  - [x] `openai-whisper` 추가
  - [x] `torch`, `torchaudio`, `tiktoken` 추가
  - [x] `more-itertools` 추가

- [x] `ssmaker.py`
  - [x] 패키지 설치 목록 업데이트
  - [x] 모듈 체크 목록 업데이트
  - [x] CTranslate2 환경 설정 제거

- [x] `install_dependencies.py`
  - [x] 패키지 목록 업데이트

### 3. 빌드 설정 수정
- [x] `ssmaker.spec`
  - [x] `faster_whisper`, `ctranslate2` 제거
  - [x] `whisper`, `torch`, `torchaudio`, `tiktoken` 추가
  - [x] CTranslate2 데이터 수집 제거
  - [x] Whisper 데이터 수집 추가
  - [x] PyTorch 데이터 수집 추가
  - [x] tiktoken 데이터 수집 추가
  - [x] Whisper 모델 캐시 포함 추가
  - [x] hiddenimports 업데이트

---

## ✅ 새로 추가된 파일

- [x] `download_whisper_models.py` - 모델 사전 다운로드 스크립트
- [x] `BUILD_GUIDE.md` - 빌드 가이드 문서
- [x] `MIGRATION_CHECKLIST.md` - 이 파일

---

## ✅ 제거된 기능/코드

### 제거된 함수
- [x] `_force_setup_ctranslate2_environment()` (whisper_analyzer.py)
- [x] `_force_setup_onnxruntime_environment()` (whisper_analyzer.py - VAD용)
- [x] `_setup_ctranslate2_environment()` (ssmaker.py)

### 제거된 파라미터
- [x] `vad_filter=True` (Faster-Whisper 전용)
- [x] `vad_parameters` (Faster-Whisper 전용)
- [x] `compute_type` (CTranslate2 전용)
- [x] `cpu_threads` (CTranslate2 최적화)
- [x] `beam_size` (일부 제거, Whisper는 내부적으로 처리)

---

## ✅ 추가된 기능

### 오프라인 지원
- [x] Whisper 모델 사전 다운로드 스크립트
- [x] 빌드 시 모델 자동 포함
- [x] 런타임 모델 경로 자동 감지

### 진단/로깅
- [x] OpenAI Whisper 런타임 진단 정보
- [x] 모델 경로 확인 로그
- [x] 번들 모델 사용 확인 로그

---

## 🔍 검증 필요 항목

### 빌드 전 검증
- [ ] `pip install -r requirements.txt` 성공
- [ ] `python download_whisper_models.py` 실행 및 모델 다운로드 확인
- [ ] `~/.cache/whisper/base.pt` 파일 존재 확인

### 빌드 검증
- [ ] `pyinstaller ssmaker.spec` 성공
- [ ] 빌드 로그에 "Whisper model included: base.pt" 확인
- [ ] `dist/ssmaker/whisper_models/base.pt` 존재 확인
- [ ] `dist/ssmaker/_internal/torch/` 존재 확인
- [ ] `dist/ssmaker/_internal/whisper/` 존재 확인
- [ ] `dist/ssmaker/_internal/tiktoken/` 존재 확인

### 런타임 검증 (온라인)
- [ ] 프로그램 실행 성공
- [ ] GUI 정상 표시
- [ ] 영상 다운로드 성공
- [ ] Whisper 분석 시작 로그 확인
- [ ] "[OpenAI Whisper STT 분석] 시작..." 로그 확인
- [ ] "[OpenAI Whisper] 모델 로드 완료" 로그 확인
- [ ] 단어 타임스탬프 추출 확인
- [ ] 자막 생성 성공
- [ ] 최종 영상 생성 성공

### 런타임 검증 (오프라인) ⭐ **중요!**
- [ ] 인터넷 연결 끊기
- [ ] 프로그램 실행 성공
- [ ] "[OpenAI Whisper] 빌드 포함 모델 사용" 로그 확인
- [ ] Whisper 분석 성공 (인터넷 없이)
- [ ] 영상 생성 성공 (TTS, 번역은 인터넷 필요)

---

## 🐛 회귀 테스트 (기존 기능 확인)

### OCR 기능
- [ ] RapidOCR 정상 작동
- [ ] 중국어 자막 감지 성공
- [ ] onnxruntime 환경 설정 정상 (RapidOCR용)

### 기타 기능
- [ ] 영상 다운로드 (Douyin, TikTok)
- [ ] AI 분석 (Gemini)
- [ ] TTS 생성
- [ ] 자막 렌더링
- [ ] 최종 영상 합성

---

## 🚨 알려진 제약사항

### 빌드 크기
- **이전 (Faster-Whisper)**: ~800MB
- **현재 (OpenAI Whisper)**: ~1-1.5GB
- **원인**: PyTorch가 CTranslate2보다 큼 (정상)

### 첫 실행 속도
- **이전**: 즉시 시작
- **현재**: 모델 로드에 3-5초 소요 (PyTorch 초기화)
- **완화**: 모델 캐싱으로 두 번째부터는 빠름

### 메모리 사용량
- **이전**: ~1-2GB
- **현재**: ~2-3GB
- **원인**: PyTorch 메모리 오버헤드

### 호환성
- ✅ **Windows 10+**: 완전 지원
- ⚠️ **Windows 7-8**: 테스트 필요 (PyTorch 지원 여부)
- ❓ **32비트**: 미지원 (PyTorch는 64비트 전용)

---

## 📋 다음 단계 (선택사항)

### 최적화 (필요시)
- [ ] PyTorch CPU 전용 버전 사용 (GPU 미사용 시)
- [ ] Whisper 모델 크기 선택 옵션 (tiny/base/small)
- [ ] 모델 동적 다운로드 옵션 추가

### 문서화
- [ ] 사용자 매뉴얼 업데이트 (Whisper 설명)
- [ ] FAQ 추가 (오프라인 사용, 모델 크기 등)
- [ ] 릴리스 노트 작성

---

## ✅ 최종 승인 체크

모든 검증 항목이 완료되면 체크하세요:

- [ ] 모든 빌드 전 검증 통과
- [ ] 모든 빌드 검증 통과
- [ ] 모든 런타임 검증 통과 (온라인/오프라인)
- [ ] 모든 회귀 테스트 통과
- [ ] 알려진 제약사항 문서화 완료
- [ ] BUILD_GUIDE.md 검토 완료

**승인자**: ___________
**날짜**: ___________

---

## 🎯 체크리스트 요약

### 필수 (MUST)
1. ✅ 코드 변경 완료
2. ✅ 빌드 설정 완료
3. ⏳ 모델 다운로드 및 빌드 포함
4. ⏳ 오프라인 실행 검증

### 권장 (SHOULD)
1. ✅ 문서화 (BUILD_GUIDE.md)
2. ⏳ 전체 회귀 테스트
3. ⏳ 다양한 환경 테스트

### 선택 (OPTIONAL)
1. 최적화
2. 추가 문서화
